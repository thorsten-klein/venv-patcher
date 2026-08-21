import subprocess
import sys

import pytest

from venv_patcher.core import (
    PyPatcherError,
    apply_patch_file,
    ensure_git_initialized,
    ensure_running_in_venv,
    is_in_venv,
    load_patch_entries,
    reset_package,
    resolve_package_dir,
    sha256_of,
)

from .conftest import dump_toml, make_am_patch, make_plain_diff


def _git_log(pkg_dir, fmt="%H"):
    proc = subprocess.run(["git", "log", f"--format={fmt}"], cwd=pkg_dir, check=True, capture_output=True, text=True)
    return proc.stdout.strip().splitlines()


def test_resolve_package_dir_returns_import_path(make_package):
    pkg_dir = make_package("dummypkg")
    assert resolve_package_dir("dummypkg") == pkg_dir.resolve()


def test_resolve_package_dir_missing_package_raises(fake_venv):
    with pytest.raises(PyPatcherError, match="not importable"):
        resolve_package_dir("does_not_exist_pkg")


def test_resolve_package_dir_rejects_single_file_module_at_site_packages_root(fake_venv):
    (fake_venv / "loose_module_at_root.py").write_text("X = 1\n")
    try:
        with pytest.raises(PyPatcherError, match="single-file module"):
            resolve_package_dir("loose_module_at_root")
    finally:
        sys.modules.pop("loose_module_at_root", None)


def test_is_in_venv_and_guard(fake_venv):
    assert is_in_venv() is True
    ensure_running_in_venv()  # should not raise


def test_ensure_running_in_venv_raises_outside_venv(monkeypatch):
    monkeypatch.setattr("venv_patcher.core.sys.prefix", "/same")
    monkeypatch.setattr("venv_patcher.core.sys.base_prefix", "/same")
    with pytest.raises(PyPatcherError, match="virtual environment"):
        ensure_running_in_venv()


def test_ensure_git_initialized_creates_commit_and_ignores_pycache(make_package):
    pkg_dir = make_package("dummypkg")
    (pkg_dir / "__pycache__").mkdir()
    (pkg_dir / "__pycache__" / "stray.pyc").write_bytes(b"\x00\x01")

    initial_commit = ensure_git_initialized(pkg_dir)

    assert (pkg_dir / ".git").is_dir()
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        cwd=pkg_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = proc.stdout.split()
    assert "__init__.py" in tracked
    assert not any("pycache" in p or p.endswith(".pyc") for p in tracked)
    assert _git_log(pkg_dir) == [initial_commit]


def test_ensure_git_initialized_reuses_existing_gitignore_without_duplicating_it(make_package):
    pkg_dir = make_package("dummypkg")

    ensure_git_initialized(pkg_dir)
    gitignore_after_first = (pkg_dir / ".gitignore").read_text()
    assert gitignore_after_first.splitlines() == ["__pycache__/", "*.pyc", "*.pyo"]

    # Re-running against an already-tracked package dir must read the
    # existing .gitignore rather than assume it's missing, and leave it
    # untouched once every required line is already present.
    ensure_git_initialized(pkg_dir)
    gitignore_after_second = (pkg_dir / ".gitignore").read_text()
    assert gitignore_after_second == gitignore_after_first


def test_ensure_git_initialized_is_deterministic_across_independent_repos(make_package, tmp_path):
    pkg_dir_a = make_package("pkg_a", "VALUE = 1\n")
    other_site_packages = tmp_path / "other-site-packages"
    other_site_packages.mkdir()
    pkg_dir_b = other_site_packages / "pkg_a"
    pkg_dir_b.mkdir()
    (pkg_dir_b / "__init__.py").write_text("VALUE = 1\n")

    commit_a = ensure_git_initialized(pkg_dir_a)
    commit_b = ensure_git_initialized(pkg_dir_b)

    assert commit_a == commit_b


def test_apply_patch_file_with_plain_diff_creates_deterministic_commit(make_package, tmp_path):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    initial_commit = ensure_git_initialized(pkg_dir)

    patch_file = tmp_path / "plain.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    ok, err = apply_patch_file(
        pkg_dir,
        patch_file,
        "git apply",
        "Test Author",
        "test@example.com",
        "2024-01-01T00:00:00+00:00",
        "bump value",
    )
    assert ok, err
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 2\n"
    first_commit = _git_log(pkg_dir)[0]

    ok, err = reset_package(pkg_dir, initial_commit)
    assert ok, err
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 1\n"

    ok, err = apply_patch_file(
        pkg_dir,
        patch_file,
        "git apply",
        "Test Author",
        "test@example.com",
        "2024-01-01T00:00:00+00:00",
        "bump value",
    )
    assert ok, err
    second_commit = _git_log(pkg_dir)[0]

    assert first_commit == second_commit


def test_apply_patch_file_with_git_am(make_package, tmp_path):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    ensure_git_initialized(pkg_dir)

    patch_file = make_am_patch(tmp_path, pkg_dir, "VALUE = 1", "VALUE = 3", "Patch Author", "patch@example.com")

    ok, err = apply_patch_file(pkg_dir, patch_file, "git am", None, None, None, "unused")
    assert ok, err
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 3\n"

    author = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae>"],
        cwd=pkg_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert author == "Patch Author <patch@example.com>"


def test_apply_patch_file_reports_failure_without_raising(make_package, tmp_path):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    ensure_git_initialized(pkg_dir)

    bad_patch = tmp_path / "bad.patch"
    bad_patch.write_text("not a valid patch\n")

    ok, err = apply_patch_file(pkg_dir, bad_patch, "git apply", None, None, None, "bump value")
    assert ok is False
    assert err


def test_sha256_of(tmp_path):
    f = tmp_path / "x.txt"
    f.write_bytes(b"hello world")
    import hashlib

    assert sha256_of(f) == hashlib.sha256(b"hello world").hexdigest()


def test_reset_package_removes_untracked_files(make_package):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    initial_commit = ensure_git_initialized(pkg_dir)

    (pkg_dir / "extra.py").write_text("Y = 1\n")
    (pkg_dir / "__init__.py").write_text("VALUE = 999\n")

    ok, err = reset_package(pkg_dir, initial_commit)
    assert ok, err
    assert not (pkg_dir / "extra.py").exists()
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 1\n"


def test_load_patch_entries_requires_package_and_path(tmp_path):
    toml_path = tmp_path / "bad.toml"
    toml_path.write_text(dump_toml({"version": 1, "patches": [{"path": "x.patch"}]}))
    with pytest.raises(PyPatcherError, match="package"):
        load_patch_entries(toml_path)


def test_load_patch_entries_parses_valid_file(tmp_path):
    toml_path = tmp_path / "good.toml"
    toml_path.write_text(dump_toml({"version": 1, "patches": [{"path": "x.patch", "package": "foo"}]}))
    entries = load_patch_entries(toml_path)
    assert entries == [{"path": "x.patch", "package": "foo"}]


def test_load_patch_entries_requires_version(tmp_path):
    toml_path = tmp_path / "no_version.toml"
    toml_path.write_text(dump_toml({"patches": [{"path": "x.patch", "package": "foo"}]}))
    with pytest.raises(PyPatcherError, match="version"):
        load_patch_entries(toml_path)


def test_load_patch_entries_rejects_unsupported_version(tmp_path):
    toml_path = tmp_path / "bad_version.toml"
    toml_path.write_text(dump_toml({"version": 2, "patches": [{"path": "x.patch", "package": "foo"}]}))
    with pytest.raises(PyPatcherError, match="unsupported version"):
        load_patch_entries(toml_path)


def test_resolve_package_dir_raises_for_module_without_path_or_file(fake_venv):
    # Built-in modules like "sys" have neither __path__ nor __file__.
    with pytest.raises(PyPatcherError, match="cannot determine an on-disk location"):
        resolve_package_dir("sys")


def test_resolve_package_dir_accepts_single_file_module_in_a_subdirectory(fake_venv, monkeypatch):
    subdir = fake_venv / "somedir"
    subdir.mkdir()
    (subdir / "loose_module_in_subdir.py").write_text("X = 1\n")
    monkeypatch.syspath_prepend(str(subdir))

    try:
        assert resolve_package_dir("loose_module_in_subdir") == subdir.resolve()
    finally:
        sys.modules.pop("loose_module_in_subdir", None)


def test_ensure_git_initialized_raises_on_init_failure(make_package, fail_git_subcommand):
    pkg_dir = make_package("dummypkg")
    fail_git_subcommand("init", "init boom")

    with pytest.raises(PyPatcherError, match="git init failed"):
        ensure_git_initialized(pkg_dir)


def test_ensure_git_initialized_raises_on_add_failure(make_package, fail_git_subcommand):
    pkg_dir = make_package("dummypkg")
    fail_git_subcommand("add", "add boom")

    with pytest.raises(PyPatcherError, match="git add failed"):
        ensure_git_initialized(pkg_dir)


def test_ensure_git_initialized_raises_on_commit_failure(make_package, fail_git_subcommand):
    pkg_dir = make_package("dummypkg")
    fail_git_subcommand("commit", "commit boom")

    with pytest.raises(PyPatcherError, match="git commit failed"):
        ensure_git_initialized(pkg_dir)


def test_ensure_git_initialized_raises_on_rev_parse_failure(make_package, fail_git_subcommand):
    pkg_dir = make_package("dummypkg")
    fail_git_subcommand("rev-parse", "rev-parse boom")

    with pytest.raises(PyPatcherError, match="git rev-parse failed"):
        ensure_git_initialized(pkg_dir)


def test_apply_patch_file_reports_git_add_failure(make_package, tmp_path, fail_git_subcommand):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    ensure_git_initialized(pkg_dir)

    patch_file = tmp_path / "plain.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    fail_git_subcommand("add", "add boom")

    ok, err = apply_patch_file(pkg_dir, patch_file, "git apply", None, None, None, "msg")
    assert ok is False
    assert "add boom" in err


def test_apply_patch_file_reports_git_commit_failure(make_package, tmp_path, fail_git_subcommand):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    ensure_git_initialized(pkg_dir)

    patch_file = tmp_path / "plain.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    fail_git_subcommand("commit", "commit boom")

    ok, err = apply_patch_file(pkg_dir, patch_file, "git apply", None, None, None, "msg")
    assert ok is False
    assert "commit boom" in err


def test_reset_package_reports_failure_for_invalid_commit(make_package):
    pkg_dir = make_package("dummypkg")
    ensure_git_initialized(pkg_dir)

    ok, err = reset_package(pkg_dir, "0" * 40)
    assert ok is False
    assert err


def test_reset_package_reports_git_clean_failure(make_package, fail_git_subcommand):
    pkg_dir = make_package("dummypkg")
    initial_commit = ensure_git_initialized(pkg_dir)

    fail_git_subcommand("clean", "clean boom")

    ok, err = reset_package(pkg_dir, initial_commit)
    assert ok is False
    assert "clean boom" in err
