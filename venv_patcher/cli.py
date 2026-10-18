"""venv-patcher command line interface."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from venv_patcher.core import (
    DEFAULT_APPLY_COMMAND,
    PyPatcherError,
    apply_patch_file,
    ensure_git_initialized,
    ensure_running_in_venv,
    git_date,
    has_outside_changes,
    load_patch_entries,
    reset_package,
    resolve_package_dir,
    sha256_of,
)
from venv_patcher.manifest import get_package_record, load_manifest, save_manifest


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the venv-patcher command line interface."""
    parser = argparse.ArgumentParser(
        prog="venv-patcher",
        description="Apply and track patches to packages installed in a Python virtual environment.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    apply_p = sub.add_parser("apply", help="Apply patches described in one or more YAML or TOML files")
    apply_p.add_argument(
        "-f",
        "--file",
        dest="files",
        action="append",
        required=True,
        metavar="FILE",
        help="YAML or TOML file describing patches to apply (may be given multiple times; "
        "TOML needs Python 3.11 or newer)",
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
        for file in files:
            exit_code = _apply_from_file(manifest, file, package_filter, skip_missing) or exit_code
    except _PackageNotFound:
        return 1

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
    patches_path = Path(file).resolve()
    if not patches_path.is_file():
        print(f"error: patch file not found: {file}", file=sys.stderr)
        return 1

    try:
        entries = load_patch_entries(patches_path)
    except PyPatcherError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    exit_code = 0
    for patch_info in entries:
        if package_filter is not None and patch_info["package"] not in package_filter:
            continue
        if not _apply_one(manifest, patches_path, patch_info, skip_missing):
            exit_code = 1
    return exit_code


def _apply_one(manifest: dict, patches_path: Path, patch_info: dict, skip_missing: bool) -> bool:
    """Apply one entry. An entry without a path only sets up git."""
    if "path" not in patch_info:
        return _track_only(manifest, patch_info["package"], skip_missing)
    return _apply_patch_entry(manifest, patches_path, patch_info, skip_missing)


def _record_failure(manifest: dict, pkg_record: dict, entry: dict, message: str) -> bool:
    entry["status"] = "failed"
    entry["error"] = message
    pkg_record["patches"].append(entry)
    save_manifest(manifest)
    print(f"error: {message}", file=sys.stderr)
    return False


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


def _start_tracking(manifest: dict, pkg_record: dict, package: str, package_dir: Path) -> str | None:
    """Make the initial commit of package, the first time. Returns an error, or None."""
    if pkg_record["initial_commit"] is not None:
        return None

    try:
        initial_commit = ensure_git_initialized(package_dir)
    except PyPatcherError as e:
        return f"could not initialize git tracking for {package}: {e}"

    pkg_record["initial_commit"] = initial_commit
    save_manifest(manifest)
    print(f"initialized git tracking for {package} at {package_dir} ({initial_commit[:8]})")
    return None


def _track_only(manifest: dict, package: str, skip_missing: bool) -> bool:
    """Set up git tracking for a package that is listed without a patch.

    Then you can change its files, commit, and save that as a patch.
    """
    try:
        package_dir = resolve_package_dir(package)
    except PyPatcherError as e:
        print(f"error: {e}", file=sys.stderr)
        if not skip_missing:
            raise _PackageNotFound(str(e)) from e
        return False

    pkg_record = get_package_record(manifest, package)
    pkg_record["location"] = str(package_dir)
    error = _start_tracking(manifest, pkg_record, package, package_dir)
    if error is not None:
        print(f"error: {error}", file=sys.stderr)
        return False
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

    error = _start_tracking(manifest, pkg_record, package, package_dir)
    if error is not None:
        _record_failure(manifest, pkg_record, entry, error)
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

    entry["status"] = "applied" if ok else "failed"
    if ok:
        entry["patch_sha256"] = actual_sha
    else:
        entry["error"] = stderr
    pkg_record["patches"].append(entry)
    save_manifest(manifest)

    if ok:
        print(f"applied {rel_path} to {package}")
        return True

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
    return False


def _apply_patch_entry(manifest: dict, patches_path: Path, patch_info: dict, skip_missing: bool) -> bool:
    """Apply an entry that names a patch file."""
    package = patch_info["package"]
    rel_path = patch_info["path"]
    apply_command = patch_info.get("apply-command", DEFAULT_APPLY_COMMAND)
    date = patch_info.get("date")
    date_str = git_date(date) if date is not None else None
    # a relative path is relative to the patches file
    patch_file = (patches_path.parent / rel_path).resolve()

    pkg_record = get_package_record(manifest, package)
    entry = {
        "source_file": str(patches_path),
        "path": rel_path,
        "resolved_path": str(patch_file),
        "apply_command": apply_command,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }

    if _changed_outside(pkg_record):
        return _record_failure(
            manifest,
            pkg_record,
            entry,
            f"{package} changed since venv-patcher patched it, for example by a pip upgrade; "
            f"use --force -p {package} to start again from the installed files",
        )

    existing_entry = next(
        (
            p
            for p in pkg_record["patches"]
            if p.get("status") == "applied" and p.get("resolved_path") == str(patch_file)
        ),
        None,
    )
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


def _changed_outside(record: dict) -> bool:
    """Whether a tracked package changed without venv-patcher, e.g. by pip."""
    location = record.get("location")
    if not location or not record.get("initial_commit") or not Path(location).is_dir():
        return False
    return has_outside_changes(Path(location))


def _print_patch_status(p: dict) -> None:
    status = p.get("status", "unknown")
    marker = "OK" if status == "applied" else "FAIL"
    # manifests written before TOML support call the field "source_yaml"
    source = p.get("source_file") or p.get("source_yaml")
    print(f"  [{marker}] {p['path']}  (from {source}, {p['applied_at']})")
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

    if has_outside_changes(package_dir):
        return _start_over(manifest, package, record, package_dir)

    ok, stderr = reset_package(package_dir, initial_commit)
    if not ok:
        print(f"error: failed to reset {package}: {stderr}", file=sys.stderr)
        return False

    record["patches"] = []
    save_manifest(manifest)
    print(f"reset {package} to initial state ({initial_commit[:8]})")
    return True


def _start_over(manifest: dict, package: str, record: dict, package_dir: Path) -> bool:
    """Forget a package that changed without venv-patcher, e.g. by a pip upgrade.

    A hard reset would put back the files of the old version. So keep the
    installed files, and drop the git history and the patch list instead.
    The next apply starts again with a new initial commit.
    """
    shutil.rmtree(package_dir / ".git")
    record["initial_commit"] = None
    record["patches"] = []
    save_manifest(manifest)
    print(f"warning: {package} changed since venv-patcher patched it; kept the installed files", file=sys.stderr)
    return True


def _reset_packages(manifest: dict, package_filter: set[str] | None) -> int:
    """Hard-reset packages back to their recorded initial commit.

    Resets every package matching package_filter (or every tracked package,
    if package_filter is None) back to its recorded initial commit, and
    clears its patch history. Returns 0 if every reset succeeded, 1 if any
    package failed to reset.
    """
    exit_code = 0
    for package, record in manifest.get("packages", {}).items():
        if package_filter is not None and package not in package_filter:
            continue
        if _reset_one_package(manifest, package, record) is False:
            exit_code = 1

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
