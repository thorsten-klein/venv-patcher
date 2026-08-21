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
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the venv-patcher command line interface."""
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
    """Entry point for the venv-patcher command line interface."""
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
    """Apply the patches described in files, honoring packages/skip_missing/force."""
    manifest = load_manifest()
    package_filter = set(packages) if packages else None
    exit_code = 0

    if force:
        exit_code = _reset_packages(manifest, package_filter) or exit_code

    try:
        exit_code = _apply_all_files(manifest, files, package_filter, skip_missing) or exit_code
    except _PackageNotFound:
        return 1

    return exit_code


def _apply_all_files(
    manifest: dict,
    files: list[str],
    package_filter: set[str] | None,
    skip_missing: bool,
) -> int:
    exit_code = 0
    for file in files:
        exit_code = _apply_from_file(manifest, file, package_filter, skip_missing) or exit_code
    return exit_code


def _resolve_yaml_file(file: str) -> Path | None:
    yaml_path = Path(file).resolve()
    if not yaml_path.is_file():
        print(f"error: patch file not found: {file}", file=sys.stderr)
        return None
    return yaml_path


def _load_entries_or_none(yaml_path: Path) -> list[dict] | None:
    try:
        return load_patch_entries(yaml_path)
    except PyPatcherError as e:
        print(f"error: {e}", file=sys.stderr)
        return None


def _iter_matching_entries(entries: list[dict], package_filter: set[str] | None):
    for patch_info in entries:
        if package_filter is None or patch_info["package"] in package_filter:
            yield patch_info


def _apply_matching_entries(
    manifest: dict,
    yaml_path: Path,
    entries: list[dict],
    package_filter: set[str] | None,
    skip_missing: bool,
) -> int:
    exit_code = 0
    for patch_info in _iter_matching_entries(entries, package_filter):
        if not _apply_one(manifest, yaml_path, patch_info, skip_missing):
            exit_code = 1
    return exit_code


def _apply_from_file(
    manifest: dict,
    file: str,
    package_filter: set[str] | None,
    skip_missing: bool,
) -> int:
    """Apply every patch entry in file that matches package_filter.

    Returns 0 if every matching entry applied successfully, 1 if any of them
    (or the file itself) failed. Lets _PackageNotFound propagate so cmd_apply
    can abort immediately, as required when skip_missing is False.
    """
    yaml_path = _resolve_yaml_file(file)
    if yaml_path is None:
        return 1

    entries = _load_entries_or_none(yaml_path)
    if entries is None:
        return 1

    return _apply_matching_entries(manifest, yaml_path, entries, package_filter, skip_missing)


def _make_patch_entry(yaml_path: Path, rel_path: str, patch_file: Path, apply_command: str) -> dict:
    return {
        "source_yaml": str(yaml_path),
        "path": rel_path,
        "resolved_path": str(patch_file),
        "apply_command": apply_command,
        "applied_at": now_iso(),
    }


def _record_failure(manifest: dict, pkg_record: dict, entry: dict, message: str) -> bool:
    entry["status"] = "failed"
    entry["error"] = message
    pkg_record["patches"].append(entry)
    save_manifest(manifest)
    print(f"error: {message}", file=sys.stderr)
    return False


def _find_existing_entry(pkg_record: dict, patch_file: Path) -> dict | None:
    return next(
        (
            p
            for p in pkg_record["patches"]
            if p.get("status") == "applied" and p.get("resolved_path") == str(patch_file)
        ),
        None,
    )


def _handle_already_applied(
    manifest: dict,
    pkg_record: dict,
    entry: dict,
    existing_entry: dict,
    patch_file: Path,
    rel_path: str,
    package: str,
) -> bool:
    """Handle a patch entry already recorded as applied to package.

    Returns True if it's an unchanged repeat (skipped as a no-op), False if
    the patch file has since disappeared or its content has drifted (both
    recorded as failures).
    """
    if not patch_file.is_file():
        return _record_failure(manifest, pkg_record, entry, f"patch file not found: {patch_file}")

    current_sha = sha256_of(patch_file)
    if current_sha == existing_entry.get("patch_sha256"):
        print(f"warning: {rel_path} already applied to {package}, skipping", file=sys.stderr)
        return True

    return _record_failure(
        manifest,
        pkg_record,
        entry,
        f"{rel_path} was already applied to {package} but its content has changed since "
        f"then; use --force to reset {package} and apply it again",
    )


def _resolve_or_fail(
    manifest: dict,
    pkg_record: dict,
    entry: dict,
    package: str,
    skip_missing: bool,
) -> Path | None:
    """Resolve package's on-disk directory, recording+raising/returning on failure.

    Raises _PackageNotFound if resolution failed and skip_missing is False.
    """
    try:
        package_dir = resolve_package_dir(package)
    except PyPatcherError as e:
        _record_failure(manifest, pkg_record, entry, str(e))
        if not skip_missing:
            raise _PackageNotFound(str(e)) from e
        return None

    pkg_record["location"] = str(package_dir)
    return package_dir


def _ensure_git_tracking(manifest: dict, pkg_record: dict, entry: dict, package: str, package_dir: Path) -> bool:
    if pkg_record["initial_commit"] is not None:
        return True

    try:
        initial_commit = ensure_git_initialized(package_dir)
    except PyPatcherError as e:
        _record_failure(manifest, pkg_record, entry, f"could not initialize git tracking for {package}: {e}")
        return False

    pkg_record["initial_commit"] = initial_commit
    save_manifest(manifest)
    print(f"initialized git tracking for {package} at {package_dir} ({initial_commit[:8]})")
    return True


def _ensure_tracked_package_dir(
    manifest: dict,
    pkg_record: dict,
    entry: dict,
    package: str,
    skip_missing: bool,
) -> Path | None:
    """Resolve package's on-disk directory and make sure git tracking is initialized for it.

    Returns the resolved directory, or None if resolution/initialization
    failed (already recorded as a failure). Raises _PackageNotFound if
    resolution failed and skip_missing is False.
    """
    package_dir = _resolve_or_fail(manifest, pkg_record, entry, package, skip_missing)
    if package_dir is None:
        return None

    if not _ensure_git_tracking(manifest, pkg_record, entry, package, package_dir):
        return None

    return package_dir


def _verify_patch_sha(
    manifest: dict,
    pkg_record: dict,
    entry: dict,
    patch_file: Path,
    patch_info: dict,
    rel_path: str,
) -> str | None:
    """Verify patch_file exists and matches its pinned sha256sum, if any.

    Returns the patch file's actual sha256, or None if verification failed
    (already recorded as a failure).
    """
    if not patch_file.is_file():
        _record_failure(manifest, pkg_record, entry, f"patch file not found: {patch_file}")
        return None

    actual_sha = sha256_of(patch_file)
    expected_sha = patch_info.get("sha256sum")
    if expected_sha and actual_sha != expected_sha:
        _record_failure(
            manifest, pkg_record, entry, f"sha256 mismatch for {rel_path} (expected {expected_sha}, got {actual_sha})"
        )
        return None

    return actual_sha


def _resolve_patch_file(yaml_path: Path, rel_path: str) -> Path:
    patch_file = Path(rel_path)
    if not patch_file.is_absolute():
        patch_file = yaml_path.parent / patch_file
    return patch_file.resolve()


def _record_apply_result(entry: dict, ok: bool, actual_sha: str, stderr: str) -> None:
    entry["status"] = "applied" if ok else "failed"
    if ok:
        entry["patch_sha256"] = actual_sha
    else:
        entry["error"] = stderr


def _report_apply_result(
    ok: bool, rel_path: str, package: str, package_dir: Path, apply_command: str, stderr: str
) -> None:
    if ok:
        print(f"applied {rel_path} to {package}")
        return

    indented_error = "\n".join(f"    {line}" for line in stderr.splitlines()) or "    (no output)"
    print(
        "error: failed to apply patch\n"
        f"  command:     {apply_command}\n"
        f"  package:     {package}\n"
        f"  patch:       {rel_path}\n"
        f"  package-dir: {package_dir}\n"
        f"  stderr:\n{indented_error}",
        file=sys.stderr,
    )


def _finalize_apply(
    manifest: dict,
    pkg_record: dict,
    entry: dict,
    package_dir: Path,
    patch_file: Path,
    patch_info: dict,
    package: str,
    rel_path: str,
    apply_command: str,
    date_str: str | None,
    actual_sha: str,
) -> bool:
    """Run apply_command, record the resulting entry in manifest, and report the outcome."""
    author = patch_info.get("author")
    email = patch_info.get("email")
    commit_message = patch_info.get("comments") or f"venv-patcher: apply {patch_file.name}"
    ok, stderr = apply_patch_file(package_dir, patch_file, apply_command, author, email, date_str, commit_message)

    _record_apply_result(entry, ok, actual_sha, stderr)
    pkg_record["patches"].append(entry)
    save_manifest(manifest)
    _report_apply_result(ok, rel_path, package, package_dir, apply_command, stderr)

    return ok


def _apply_one(
    manifest: dict,
    yaml_path: Path,
    patch_info: dict,
    skip_missing: bool = False,
) -> bool:
    """Apply a single patch entry, recording the outcome in manifest."""
    package = patch_info["package"]
    rel_path = patch_info["path"]
    apply_command = patch_info.get("apply-command", DEFAULT_APPLY_COMMAND)
    date = patch_info.get("date")
    date_str = str(date) if date is not None else None
    patch_file = _resolve_patch_file(yaml_path, rel_path)

    pkg_record = get_package_record(manifest, package)
    entry = _make_patch_entry(yaml_path, rel_path, patch_file, apply_command)

    existing_entry = _find_existing_entry(pkg_record, patch_file)
    if existing_entry is not None:
        return _handle_already_applied(manifest, pkg_record, entry, existing_entry, patch_file, rel_path, package)

    package_dir = _ensure_tracked_package_dir(manifest, pkg_record, entry, package, skip_missing)
    if package_dir is None:
        return False

    actual_sha = _verify_patch_sha(manifest, pkg_record, entry, patch_file, patch_info, rel_path)
    if actual_sha is None:
        return False

    return _finalize_apply(
        manifest,
        pkg_record,
        entry,
        package_dir,
        patch_file,
        patch_info,
        package,
        rel_path,
        apply_command,
        date_str,
        actual_sha,
    )


def _print_patch_status(p: dict) -> None:
    status = p.get("status", "unknown")
    marker = "OK" if status == "applied" else "FAIL"
    print(f"  [{marker}] {p['path']}  (from {p['source_yaml']}, {p['applied_at']})")
    if status != "applied" and p.get("error"):
        print(f"        error: {p['error']}")


def _print_package_status(package: str, record: dict) -> None:
    print(f"{package} ({record.get('location')})")
    initial_commit = record.get("initial_commit")
    if initial_commit:
        print(f"  initial commit: {initial_commit[:8]}")
    patches = record.get("patches", [])
    if not patches:
        print("  (no patches applied)")
    for p in patches:
        _print_patch_status(p)


def cmd_list() -> int:  # NOSONAR -- always 0 by design (listing never fails); kept int to
    # match cmd_apply/cmd_reset's shared "return cmd_x(...)" dispatch in main().
    """Print every package with applied patches in the current environment."""
    manifest = load_manifest()
    packages = manifest.get("packages", {})
    if not packages:
        print("No patches applied in this environment.")
        return 0

    for package, record in sorted(packages.items()):
        _print_package_status(package, record)

    return 0


def cmd_reset(packages: list[str] | None = None) -> int:
    """Revert all patches applied in the current environment."""
    manifest = load_manifest()
    if not manifest.get("packages"):
        print("No patches to reset.")
        return 0

    package_filter = set(packages) if packages else None
    return _reset_packages(manifest, package_filter)


def _reset_one_package(manifest: dict, package: str, record: dict) -> bool | None:
    """Hard-reset a single package back to its recorded initial commit.

    Returns True/False for success/failure, or None if record has nothing to
    reset (no location or initial commit recorded yet, or the location no
    longer exists on disk).
    """
    location = record.get("location")
    initial_commit = record.get("initial_commit")
    if not location or not initial_commit:
        return None

    package_dir = Path(location)
    if not package_dir.is_dir():
        print(f"warning: {package} location no longer exists: {package_dir}", file=sys.stderr)
        return None

    ok, stderr = reset_package(package_dir, initial_commit)
    if not ok:
        print(f"error: failed to reset {package}: {stderr}", file=sys.stderr)
        return False

    record["patches"] = []
    save_manifest(manifest)
    print(f"reset {package} to initial state ({initial_commit[:8]})")
    return True


def _iter_filtered_packages(manifest: dict, package_filter: set[str] | None):
    for package, record in manifest.get("packages", {}).items():
        if package_filter is None or package in package_filter:
            yield package, record


def _reset_packages(manifest: dict, package_filter: set[str] | None) -> int:
    """Hard-reset packages back to their recorded initial commit.

    Resets every package matching package_filter (or every tracked package,
    if package_filter is None) back to its recorded initial commit, and
    clears its patch history. Returns 0 if every reset succeeded, 1 if any
    package failed to reset.
    """
    exit_code = 0
    for package, record in _iter_filtered_packages(manifest, package_filter):
        if _reset_one_package(manifest, package, record) is False:
            exit_code = 1

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
