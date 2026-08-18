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


def _toml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    raise TypeError(f"unsupported TOML value: {value!r}")


def _toml_table_lines(table_name: str, entry: dict) -> list[str]:
    lines = ["", f"[[{table_name}]]"]
    lines.extend(f"{key} = {_toml_scalar(value)}" for key, value in entry.items())
    return lines


def _toml_lines_for(key: str, value: object) -> list[str]:
    if not isinstance(value, list):
        return [f"{key} = {_toml_scalar(value)}"]
    lines = []
    for entry in value:
        lines.extend(_toml_table_lines(key, entry))
    return lines


def dump_toml(data: dict) -> str:
    """Serialize a patches-manifest dict as TOML text.

    Handles exactly the shapes venv-patcher's tests need: top-level scalars
    (e.g. "version") and a top-level "patches" list of flat dicts, written
    out as [[patches]] array-of-tables blocks -- a minimal, hand-rolled
    stand-in for the tomllib.load side, since tomllib is read-only.
    """
    lines = []
    for key, value in data.items():
        lines.extend(_toml_lines_for(key, value))
    return "\n".join(lines) + "\n"


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
