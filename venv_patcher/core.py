"""Core git and package-resolution helpers for venv-patcher."""

from __future__ import annotations

import hashlib
import importlib
import shlex
import subprocess
import sys
import sysconfig
from pathlib import Path

# Fixed fallback identity/date used when a patch entry in the yaml does not
# specify author/email/date. Using a fixed value (instead of "now") keeps
# re-applying the same patch to the same environment reproducible: the
# resulting commit hash only changes if the patch content itself changes.
FALLBACK_AUTHOR_NAME = "venv-patcher"
FALLBACK_AUTHOR_EMAIL = "venv-patcher@localhost"
FALLBACK_DATE = "1970-01-01T00:00:00+00:00"

DEFAULT_APPLY_COMMAND = "git am"


class PyPatcherError(Exception):
    """Raised for expected, user-facing failures."""


def is_in_venv() -> bool:
    return sys.prefix != sys.base_prefix


def ensure_running_in_venv() -> None:
    if not is_in_venv():
        raise PyPatcherError(
            "venv-patcher must be run from inside a virtual environment (none detected). "
            "Activate your venv (e.g. `source .venv/bin/activate`) and run venv-patcher "
            "with that venv's python/entry point."
        )


def get_site_packages_dir() -> Path:
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


def _run_git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)


_GITIGNORE_LINES = ["__pycache__/", "*.pyc", "*.pyo"]


def _ensure_gitignore(package_dir: Path) -> None:
    # Importing the package (to resolve its directory) can make the
    # interpreter (re)write __pycache__/*.pyc with a fresh mtime/hash.
    # Those aren't part of the patch and would otherwise make the resulting
    # commit non-deterministic across runs, so keep them out of tracking.
    gitignore = package_dir / ".gitignore"
    existing = gitignore.read_text().splitlines() if gitignore.is_file() else []
    missing = [line for line in _GITIGNORE_LINES if line not in existing]
    if missing:
        with open(gitignore, "a") as f:
            for line in missing:
                f.write(line + "\n")


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
    import os

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_AUTHOR_DATE"] = date
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    env["GIT_COMMITTER_DATE"] = date
    return env


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

    The author/committer identity and date are pinned (from the yaml, or a
    fixed fallback) so re-applying the same patch to the same starting state
    always produces the same commit hash. If ``apply_command`` already
    creates a commit itself (e.g. "git am"), the pinned committer identity
    takes effect there. If it only touches the working tree (e.g.
    "git apply"), venv-patcher creates the wrapping commit itself.
    """
    env = _identity_env(
        author_name or FALLBACK_AUTHOR_NAME,
        author_email or FALLBACK_AUTHOR_EMAIL,
        date or FALLBACK_DATE,
    )

    cmd = shlex.split(apply_command) + [str(patch_file)]
    proc = subprocess.run(cmd, cwd=package_dir, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        return False, proc.stderr.strip()

    status = _run_git(["status", "--porcelain"], cwd=package_dir)
    if status.stdout.strip():
        # apply_command left uncommitted changes (e.g. plain "git apply") -
        # wrap them in a deterministic commit ourselves.
        add_proc = _run_git(["add", "-A"], cwd=package_dir)
        if add_proc.returncode != 0:
            return False, add_proc.stderr.strip()

        commit_proc = _run_git(["commit", "-q", "-m", commit_message], cwd=package_dir, env=env)
        if commit_proc.returncode != 0:
            return False, commit_proc.stderr.strip()

    return True, ""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reset_package(package_dir: Path, initial_commit: str) -> tuple[bool, str]:
    proc = _run_git(["reset", "-q", "--hard", initial_commit], cwd=package_dir)
    if proc.returncode != 0:
        return False, proc.stderr.strip()

    proc = _run_git(["clean", "-q", "-fd"], cwd=package_dir)
    if proc.returncode != 0:
        return False, proc.stderr.strip()

    return True, ""


def load_patch_entries(yaml_path: Path) -> list[dict]:
    import yaml

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    patches = data.get("patches") or []
    for i, entry in enumerate(patches):
        missing = [k for k in ("package", "path") if k not in entry]
        if missing:
            raise PyPatcherError(f"{yaml_path}: patch #{i + 1} is missing required field(s): {', '.join(missing)}")
    return patches
