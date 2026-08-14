import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import venv_patcher.core as core


@pytest.fixture
def fake_venv(tmp_path, monkeypatch):
    """Simulate an active venv with its own site-packages directory."""
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    monkeypatch.setattr(core.sysconfig, "get_paths", lambda *a, **k: {"purelib": str(site_packages)})
    # is_in_venv() compares sys.prefix to sys.base_prefix.
    monkeypatch.setattr(core.sys, "prefix", str(tmp_path / "venv"))
    monkeypatch.setattr(core.sys, "base_prefix", str(tmp_path / "base"))

    monkeypatch.syspath_prepend(str(site_packages))
    return site_packages


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def make_package(fake_venv):
    """Create an importable package directory under the fake site-packages."""

    created = []

    def _make(name: str, init_contents: str = "VALUE = 1\n"):
        pkg_dir = fake_venv / name
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(init_contents)
        created.append(name)
        importlib.invalidate_caches()
        return pkg_dir

    yield _make

    for name in created:
        sys.modules.pop(name, None)


@pytest.fixture
def fail_git_subcommand(monkeypatch):
    """Make core._run_git fail for one specific git subcommand (e.g. "add"),
    while every other subcommand still runs for real. Used to reach the
    defensive error-handling branches around git failures without having to
    contrive a real failing git repository."""

    original = core._run_git

    def _apply(name: str, stderr: str = "boom"):
        def fake_run_git(args, cwd, env=None):
            if args and args[0] == name:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr=stderr)
            return original(args, cwd, env)

        monkeypatch.setattr(core, "_run_git", fake_run_git)

    return _apply


def make_plain_diff(old_line: str, new_line: str) -> str:
    return f"--- a/__init__.py\n+++ b/__init__.py\n@@ -1 +1 @@\n-{old_line}\n+{new_line}\n"


def make_am_patch(
    tmp_path: Path, pkg_dir: Path, old_line: str, new_line: str, author_name: str, author_email: str
) -> Path:
    """Build a real git-format-patch (mbox) style patch file."""
    scratch = tmp_path / "scratch_repo"
    scratch.mkdir()
    (scratch / "__init__.py").write_text(old_line + "\n")
    _git(["init", "-q"], cwd=scratch)
    _git(["add", "."], cwd=scratch)
    subprocess.run(
        ["git", "-c", "user.name=x", "-c", "user.email=x@x.com", "commit", "-q", "-m", "init"],
        cwd=scratch,
        check=True,
        capture_output=True,
        text=True,
    )
    (scratch / "__init__.py").write_text(new_line + "\n")
    _git(["add", "."], cwd=scratch)
    subprocess.run(
        [
            "git",
            "-c",
            f"user.name={author_name}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "-q",
            "-m",
            "bump value",
        ],
        cwd=scratch,
        check=True,
        capture_output=True,
        text=True,
    )
    out_dir = tmp_path / "patches_am"
    out_dir.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "format-patch", "-1", "-o", str(out_dir)],
        cwd=scratch,
        check=True,
        capture_output=True,
        text=True,
    )
    patch_files = sorted(out_dir.glob("*.patch"))
    assert patch_files
    return patch_files[-1]
