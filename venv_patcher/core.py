"""Core git and package-resolution helpers for venv-patcher."""

from __future__ import annotations

import hashlib
import importlib
import os
import shlex
import subprocess
import sys
import sysconfig
import tomllib
from pathlib import Path

# Fixed fallback identity/date used when a patch entry in the toml does not
# specify author/email/date. Using a fixed value (instead of "now") keeps
# re-applying the same patch to the same environment reproducible: the
# resulting commit hash only changes if the patch content itself changes.
FALLBACK_AUTHOR_NAME = "venv-patcher"
FALLBACK_AUTHOR_EMAIL = "venv-patcher@localhost"
FALLBACK_DATE = "1970-01-01T00:00:00+00:00"

DEFAULT_APPLY_COMMAND = "git am"

# The only toml schema version venv-patcher currently understands. The toml's
# top-level "version" field is mandatory so future schema changes can be
# introduced without silently misinterpreting older/newer files.
SUPPORTED_VERSION = 1


class PyPatcherError(Exception):
    """Raised for expected, user-facing failures."""


def is_in_venv() -> bool:
    """Return whether the current interpreter is running inside a virtual environment."""
    return sys.prefix != sys.base_prefix


def ensure_running_in_venv() -> None:
    """Raise PyPatcherError unless the current interpreter is running inside a venv."""
    if not is_in_venv():
        raise PyPatcherError(
            "venv-patcher must be run from inside a virtual environment (none detected). "
            "Activate your venv (e.g. `source .venv/bin/activate`) and run venv-patcher "
            "with that venv's python/entry point."
        )


def get_site_packages_dir() -> Path:
    """Return the current environment's site-packages directory."""
    return Path(sysconfig.get_paths()["purelib"]).resolve()


def resolve_package_dir(package_name: str) -> Path:
    """Import ``package_name`` and return the on-disk directory backing it."""
    try:
        module = importlib.import_module(package_name)
    except ImportError as e:
        raise PyPatcherError(f"package {package_name!r} is not importable in the current environment: {e}") from e

    paths = getattr(module, "__path__", None)
    if paths:
        return Path(next(iter(paths))).resolve()

    file = getattr(module, "__file__", None)
    if file is None:
        raise PyPatcherError(f"cannot determine an on-disk location for package {package_name!r}")

    package_dir = Path(file).resolve().parent
    if package_dir == get_site_packages_dir():
        raise PyPatcherError(
            f"{package_name!r} is a single-file module directly in site-packages; "
            "venv-patcher can only patch package directories"
        )
    return package_dir


def _git_env(overrides: dict | None = None) -> dict:
    """Build the environment for a git subprocess invocation.

    Always disables git's own background maintenance/auto-gc. venv-patcher
    runs git repeatedly, in quick succession, against directories it doesn't
    own (a package's location inside someone else's site-packages), so git
    deciding on its own to spawn a detached "git maintenance run" there is
    pure downside: at best wasted work, at worst (observed on macOS CI) a
    maintenance.lock file that intermittently races whatever reads that
    .git dir next -- e.g. a caller's shutil.rmtree right after venv-patcher
    is done with the package.
    """
    env = os.environ.copy()
    env["GIT_CONFIG_COUNT"] = "2"
    env["GIT_CONFIG_KEY_0"] = "gc.auto"
    env["GIT_CONFIG_VALUE_0"] = "0"
    env["GIT_CONFIG_KEY_1"] = "maintenance.auto"
    env["GIT_CONFIG_VALUE_1"] = "false"
    if overrides:
        env.update(overrides)
    return env


def _run_git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=_git_env(env))


_GITIGNORE_LINES = ["__pycache__/", "*.pyc", "*.pyo"]


def _read_existing_gitignore_lines(gitignore: Path) -> list[str]:
    if not gitignore.is_file():
        return []
    return gitignore.read_text().splitlines()


def _ensure_gitignore(package_dir: Path) -> None:
    # Importing the package (to resolve its directory) can make the
    # interpreter (re)write __pycache__/*.pyc with a fresh mtime/hash.
    # Those aren't part of the patch and would otherwise make the resulting
    # commit non-deterministic across runs, so keep them out of tracking.
    gitignore = package_dir / ".gitignore"
    existing = _read_existing_gitignore_lines(gitignore)
    missing = [line for line in _GITIGNORE_LINES if line not in existing]
    if not missing:
        return
    with gitignore.open("a") as f:
        f.write("".join(line + "\n" for line in missing))


def ensure_git_initialized(package_dir: Path) -> str:
    """Snapshot the pristine package directory as an initial git commit.

    Returns the initial commit sha.
    """
    proc = _run_git(["init", "-q"], cwd=package_dir)
    if proc.returncode != 0:
        raise PyPatcherError(f"git init failed in {package_dir}: {proc.stderr.strip()}")

    _ensure_gitignore(package_dir)

    proc = _run_git(["add", "."], cwd=package_dir)
    if proc.returncode != 0:
        raise PyPatcherError(f"git add failed in {package_dir}: {proc.stderr.strip()}")

    env = _identity_env(FALLBACK_AUTHOR_NAME, FALLBACK_AUTHOR_EMAIL, FALLBACK_DATE)
    proc = _run_git(["commit", "-q", "-m", "initial", "--allow-empty"], cwd=package_dir, env=env)
    if proc.returncode != 0:
        raise PyPatcherError(f"git commit failed in {package_dir}: {proc.stderr.strip()}")

    proc = _run_git(["rev-parse", "HEAD"], cwd=package_dir)
    if proc.returncode != 0:
        raise PyPatcherError(f"git rev-parse failed in {package_dir}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _identity_env(name: str, email: str, date: str) -> dict:
    return {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
        "GIT_COMMITTER_DATE": date,
    }


def apply_patch_file(
    package_dir: Path,
    patch_file: Path,
    apply_command: str,
    author_name: str | None,
    author_email: str | None,
    date: str | None,
    commit_message: str,
) -> tuple[bool, str]:
    """Apply a patch, guaranteeing the result lands in a deterministic commit.

    The author/committer identity and date are pinned (from the toml, or a
    fixed fallback) so re-applying the same patch to the same starting state
    always produces the same commit hash. If ``apply_command`` already
    creates a commit itself (e.g. "git am"), the pinned committer identity
    takes effect there. If it only touches the working tree (e.g.
    "git apply"), venv-patcher creates the wrapping commit itself.
    """
    identity = _identity_env(
        author_name or FALLBACK_AUTHOR_NAME,
        author_email or FALLBACK_AUTHOR_EMAIL,
        date or FALLBACK_DATE,
    )
    env = _git_env(identity)

    cmd = [*shlex.split(apply_command), str(patch_file)]
    proc = subprocess.run(cmd, cwd=package_dir, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        return False, proc.stderr.strip()

    return _commit_pending_changes(package_dir, commit_message, env)


def _commit_pending_changes(package_dir: Path, commit_message: str, env: dict) -> tuple[bool, str]:
    """Wrap any uncommitted working tree changes in a deterministic commit.

    apply_command may leave uncommitted changes (e.g. plain "git apply"), in
    which case they still need wrapping in a commit ourselves; a command that
    already commits its own result (e.g. "git am") leaves nothing to do here.
    """
    status = _run_git(["status", "--porcelain"], cwd=package_dir)
    if not status.stdout.strip():
        return True, ""

    add_proc = _run_git(["add", "-A"], cwd=package_dir)
    if add_proc.returncode != 0:
        return False, add_proc.stderr.strip()

    commit_proc = _run_git(["commit", "-q", "-m", commit_message], cwd=package_dir, env=env)
    if commit_proc.returncode != 0:
        return False, commit_proc.stderr.strip()

    return True, ""


def sha256_of(path: Path) -> str:
    """Return the hex-encoded sha256 digest of path's contents."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reset_package(package_dir: Path, initial_commit: str) -> tuple[bool, str]:
    """Hard-reset package_dir back to initial_commit, discarding any patches applied on top."""
    proc = _run_git(["reset", "-q", "--hard", initial_commit], cwd=package_dir)
    if proc.returncode != 0:
        return False, proc.stderr.strip()

    proc = _run_git(["clean", "-q", "-fd"], cwd=package_dir)
    if proc.returncode != 0:
        return False, proc.stderr.strip()

    return True, ""


def _check_version(data: dict, toml_path: Path) -> None:
    if "version" not in data:
        raise PyPatcherError(f"{toml_path}: missing required top-level field: version")
    if data["version"] != SUPPORTED_VERSION:
        raise PyPatcherError(f"{toml_path}: unsupported version {data['version']!r} (expected {SUPPORTED_VERSION})")


def _check_patch_entry_fields(i: int, entry: dict, toml_path: Path) -> None:
    missing = [k for k in ("package", "path") if k not in entry]
    if missing:
        raise PyPatcherError(f"{toml_path}: patch #{i + 1} is missing required field(s): {', '.join(missing)}")


def _check_patch_entries(patches: list[dict], toml_path: Path) -> None:
    for i, entry in enumerate(patches):
        _check_patch_entry_fields(i, entry, toml_path)


def load_patch_entries(toml_path: Path) -> list[dict]:
    """Load and validate the patch entries described by toml_path."""
    with toml_path.open("rb") as f:
        data = tomllib.load(f)

    _check_version(data, toml_path)
    patches = data.get("patches") or []
    _check_patch_entries(patches, toml_path)
    return patches
