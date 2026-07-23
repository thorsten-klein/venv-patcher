"""venv-patcher command line interface."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from venv_patcher.core import (
    DEFAULT_APPLY_COMMAND,
    PyPatcherError,
    apply_patch_file,
    ensure_git_initialized,
    ensure_running_in_venv,
    load_patch_entries,
    reset_package,
    resolve_package_dir,
    sha256_of,
)
from venv_patcher.manifest import get_package_record, load_manifest, save_manifest


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="venv-patcher",
        description="Apply and track patches to packages installed in a Python virtual environment.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    apply_p = sub.add_parser("apply", help="Apply patches described in one or more YAML files")
    apply_p.add_argument(
        "-f",
        "--file",
        dest="files",
        action="append",
        required=True,
        metavar="FILE",
        help="YAML file describing patches to apply (may be given multiple times)",
    )
    apply_p.add_argument(
        "-p",
        "--package",
        dest="packages",
        action="append",
        metavar="PACKAGE",
        help="Only apply patches targeting this package (may be given multiple times; "
        "default: apply patches for all packages)",
    )
    apply_p.add_argument(
        "--skip-missing",
        dest="skip_missing",
        action="store_true",
        default=False,
        help="Skip patches whose package is not importable instead of aborting "
        "(default: abort as soon as one is encountered)",
    )
    apply_p.add_argument(
        "--force",
        dest="force",
        action="store_true",
        default=False,
        help="Before applying, reset the packages targeted by -p (or every tracked package, "
        "if -p is not given) back to their initial state, discarding any patches previously "
        "applied to them. Useful while iterating on a patch that doesn't have a sha256sum "
        "pinned yet.",
    )

    sub.add_parser("list", help="List patches applied in the current environment")

    reset_p = sub.add_parser("reset", help="Revert all patches applied in the current environment")
    reset_p.add_argument(
        "-p",
        "--package",
        dest="packages",
        action="append",
        metavar="PACKAGE",
        help="Only reset this package (may be given multiple times; default: reset all packages)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ensure_running_in_venv()
    except PyPatcherError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.command == "apply":
        return cmd_apply(args.files, args.packages, args.skip_missing, args.force)
    if args.command == "list":
        return cmd_list()
    return cmd_reset(args.packages)


class _PackageNotFound(Exception):
    """Signals cmd_apply to abort immediately (unless --skip-missing is set)."""


def cmd_apply(
    files: list[str],
    packages: list[str] | None = None,
    skip_missing: bool = False,
    force: bool = False,
) -> int:
    manifest = load_manifest()
    package_filter = set(packages) if packages else None
    exit_code = 0

    if force:
        exit_code = _reset_packages(manifest, package_filter) or exit_code

    for file in files:
        yaml_path = Path(file).resolve()
        if not yaml_path.is_file():
            print(f"error: patch file not found: {file}", file=sys.stderr)
            exit_code = 1
            continue

        try:
            entries = load_patch_entries(yaml_path)
        except PyPatcherError as e:
            print(f"error: {e}", file=sys.stderr)
            exit_code = 1
            continue

        for patch_info in entries:
            if package_filter is not None and patch_info["package"] not in package_filter:
                continue
            try:
                ok = _apply_one(manifest, yaml_path, patch_info, skip_missing)
            except _PackageNotFound:
                return 1
            if not ok:
                exit_code = 1

    return exit_code


def _apply_one(
    manifest: dict,
    yaml_path: Path,
    patch_info: dict,
    skip_missing: bool = False,
) -> bool:
    package = patch_info["package"]
    rel_path = patch_info["path"]
    apply_command = patch_info.get("apply-command", DEFAULT_APPLY_COMMAND)
    author = patch_info.get("author")
    email = patch_info.get("email")
    date = patch_info.get("date")
    date_str = str(date) if date is not None else None

    patch_file = Path(rel_path)
    if not patch_file.is_absolute():
        patch_file = yaml_path.parent / patch_file
    patch_file = patch_file.resolve()

    pkg_record = get_package_record(manifest, package)

    entry = {
        "source_yaml": str(yaml_path),
        "path": rel_path,
        "resolved_path": str(patch_file),
        "apply_command": apply_command,
        "applied_at": now_iso(),
    }

    def fail(message: str) -> bool:
        entry["status"] = "failed"
        entry["error"] = message
        pkg_record["patches"].append(entry)
        save_manifest(manifest)
        print(f"error: {message}", file=sys.stderr)
        return False

    existing_entry = next(
        (
            p
            for p in pkg_record["patches"]
            if p.get("status") == "applied" and p.get("resolved_path") == str(patch_file)
        ),
        None,
    )
    if existing_entry is not None:
        if not patch_file.is_file():
            return fail(f"patch file not found: {patch_file}")

        current_sha = sha256_of(patch_file)
        if current_sha == existing_entry.get("patch_sha256"):
            print(f"warning: {rel_path} already applied to {package}, skipping", file=sys.stderr)
            return True

        return fail(
            f"{rel_path} was already applied to {package} but its content has changed since "
            f"then; use --force to reset {package} and apply it again"
        )

    try:
        package_dir = resolve_package_dir(package)
    except PyPatcherError as e:
        fail(str(e))
        if not skip_missing:
            raise _PackageNotFound(str(e)) from e
        return False

    pkg_record["location"] = str(package_dir)

    if pkg_record["initial_commit"] is None:
        try:
            initial_commit = ensure_git_initialized(package_dir)
        except PyPatcherError as e:
            return fail(f"could not initialize git tracking for {package}: {e}")
        pkg_record["initial_commit"] = initial_commit
        save_manifest(manifest)
        print(f"initialized git tracking for {package} at {package_dir} ({initial_commit[:8]})")

    if not patch_file.is_file():
        return fail(f"patch file not found: {patch_file}")

    actual_sha = sha256_of(patch_file)
    expected_sha = patch_info.get("sha256sum")
    if expected_sha and actual_sha != expected_sha:
        return fail(f"sha256 mismatch for {rel_path} (expected {expected_sha}, got {actual_sha})")

    commit_message = patch_info.get("comments") or f"venv-patcher: apply {patch_file.name}"
    ok, stderr = apply_patch_file(package_dir, patch_file, apply_command, author, email, date_str, commit_message)

    entry["status"] = "applied" if ok else "failed"
    if ok:
        entry["patch_sha256"] = actual_sha
    else:
        entry["error"] = stderr
    pkg_record["patches"].append(entry)
    save_manifest(manifest)

    if ok:
        print(f"applied {rel_path} to {package}")
    else:
        print(f"error: failed to apply {rel_path} to {package}: {stderr}", file=sys.stderr)

    return ok


def cmd_list() -> int:
    manifest = load_manifest()
    packages = manifest.get("packages", {})
    if not packages:
        print("No patches applied in this environment.")
        return 0

    for package, record in sorted(packages.items()):
        print(f"{package} ({record.get('location')})")
        initial_commit = record.get("initial_commit")
        if initial_commit:
            print(f"  initial commit: {initial_commit[:8]}")
        patches = record.get("patches", [])
        if not patches:
            print("  (no patches applied)")
        for p in patches:
            status = p.get("status", "unknown")
            marker = "OK" if status == "applied" else "FAIL"
            print(f"  [{marker}] {p['path']}  (from {p['source_yaml']}, {p['applied_at']})")
            if status != "applied" and p.get("error"):
                print(f"        error: {p['error']}")

    return 0


def cmd_reset(packages: list[str] | None = None) -> int:
    manifest = load_manifest()
    if not manifest.get("packages"):
        print("No patches to reset.")
        return 0

    package_filter = set(packages) if packages else None
    return _reset_packages(manifest, package_filter)


def _reset_packages(manifest: dict, package_filter: set[str] | None) -> int:
    """Hard-reset every package matching package_filter (or every tracked
    package, if package_filter is None) back to its recorded initial commit,
    and clear its patch history. Returns 0 if every reset succeeded, 1 if any
    package failed to reset."""
    exit_code = 0
    for package, record in manifest.get("packages", {}).items():
        if package_filter is not None and package not in package_filter:
            continue

        location = record.get("location")
        if not location:
            continue
        initial_commit = record.get("initial_commit")
        if not initial_commit:
            continue

        package_dir = Path(location)
        if not package_dir.is_dir():
            print(f"warning: {package} location no longer exists: {package_dir}", file=sys.stderr)
            continue

        ok, stderr = reset_package(package_dir, initial_commit)
        if not ok:
            print(f"error: failed to reset {package}: {stderr}", file=sys.stderr)
            exit_code = 1
            continue

        record["patches"] = []
        save_manifest(manifest)
        print(f"reset {package} to initial state ({initial_commit[:8]})")

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
