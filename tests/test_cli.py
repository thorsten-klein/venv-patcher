import shutil
import subprocess

from venv_patcher import cli
from venv_patcher.manifest import load_manifest

from .conftest import dump_toml, make_plain_diff


def _write_toml(tmp_path, entries, name="patches.toml"):
    toml_path = tmp_path / name
    toml_path.write_text(dump_toml({"version": 1, "patches": entries}))
    return toml_path


def test_apply_list_reset_round_trip(fake_venv, make_package, tmp_path, capsys):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")

    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    toml_path = _write_toml(
        tmp_path,
        [
            {
                "path": "bump.patch",
                "package": "dummypkg",
                "author": "Test Author",
                "email": "test@example.com",
                "date": "2024-01-01T00:00:00+00:00",
                "apply-command": "git apply",
            }
        ],
    )

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 0
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 2\n"

    manifest = load_manifest()
    record = manifest["packages"]["dummypkg"]
    assert record["initial_commit"]
    assert len(record["patches"]) == 1
    assert record["patches"][0]["status"] == "applied"

    capsys.readouterr()
    rc = cli.main(["list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "dummypkg" in out
    assert "[OK]" in out

    rc = cli.main(["reset"])
    assert rc == 0
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 1\n"

    manifest = load_manifest()
    assert manifest["packages"]["dummypkg"]["patches"] == []

    capsys.readouterr()
    rc = cli.main(["list"])
    out = capsys.readouterr().out
    assert "no patches applied" in out


def test_apply_records_failure_for_missing_patch_file(fake_venv, make_package, tmp_path):
    make_package("dummypkg", "VALUE = 1\n")
    toml_path = _write_toml(tmp_path, [{"path": "does-not-exist.patch", "package": "dummypkg"}])

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1

    manifest = load_manifest()
    record = manifest["packages"]["dummypkg"]
    assert record["initial_commit"], "package should still be git-initialized"
    assert record["patches"][0]["status"] == "failed"
    assert "not found" in record["patches"][0]["error"]


def test_apply_records_failure_for_sha256_mismatch(fake_venv, make_package, tmp_path):
    make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    toml_path = _write_toml(
        tmp_path,
        [{"path": "bump.patch", "package": "dummypkg", "sha256sum": "0" * 64}],
    )

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1

    manifest = load_manifest()
    entry = manifest["packages"]["dummypkg"]["patches"][0]
    assert entry["status"] == "failed"
    assert "sha256 mismatch" in entry["error"]


def test_apply_records_failure_for_unknown_package(fake_venv, tmp_path):
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "does_not_exist_pkg"}])

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1

    manifest = load_manifest()
    entry = manifest["packages"]["does_not_exist_pkg"]["patches"][0]
    assert entry["status"] == "failed"
    assert "not importable" in entry["error"]


def test_apply_is_reapplyable_producing_same_commit(fake_venv, make_package, tmp_path):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(
        tmp_path,
        [
            {
                "path": "bump.patch",
                "package": "dummypkg",
                "author": "Test Author",
                "email": "test@example.com",
                "date": "2024-01-01T00:00:00+00:00",
                "apply-command": "git apply",
            }
        ],
    )

    assert cli.main(["apply", "-f", str(toml_path)]) == 0
    first = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=pkg_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    assert cli.main(["reset"]) == 0
    assert cli.main(["apply", "-f", str(toml_path)]) == 0
    second = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=pkg_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    assert first == second


def test_main_refuses_to_run_outside_venv(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "prefix", "/same")
    monkeypatch.setattr("venv_patcher.core.sys.base_prefix", "/same")
    monkeypatch.setattr("venv_patcher.core.sys.prefix", "/same")

    rc = cli.main(["list"])
    assert rc == 1
    assert "virtual environment" in capsys.readouterr().err


def test_apply_missing_toml_file_reports_error(fake_venv, tmp_path, capsys):
    rc = cli.main(["apply", "-f", str(tmp_path / "missing.toml")])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_apply_package_filter_only_applies_selected_packages(fake_venv, make_package, tmp_path):
    make_package("pkg_a", "VALUE = 1\n")
    make_package("pkg_b", "VALUE = 1\n")

    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    toml_path = _write_toml(
        tmp_path,
        [
            {"path": "bump.patch", "package": "pkg_a", "apply-command": "git apply"},
            {"path": "bump.patch", "package": "pkg_b", "apply-command": "git apply"},
        ],
    )

    rc = cli.main(["apply", "-f", str(toml_path), "-p", "pkg_a"])
    assert rc == 0

    manifest = load_manifest()
    assert "pkg_a" in manifest["packages"]
    assert "pkg_b" not in manifest["packages"]


def test_reset_package_filter_only_resets_selected_packages(fake_venv, make_package, tmp_path):
    pkg_a_dir = make_package("pkg_a", "VALUE = 1\n")
    pkg_b_dir = make_package("pkg_b", "VALUE = 1\n")

    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    toml_path = _write_toml(
        tmp_path,
        [
            {"path": "bump.patch", "package": "pkg_a", "apply-command": "git apply"},
            {"path": "bump.patch", "package": "pkg_b", "apply-command": "git apply"},
        ],
    )

    assert cli.main(["apply", "-f", str(toml_path)]) == 0
    assert (pkg_a_dir / "__init__.py").read_text() == "VALUE = 2\n"
    assert (pkg_b_dir / "__init__.py").read_text() == "VALUE = 2\n"

    rc = cli.main(["reset", "-p", "pkg_a"])
    assert rc == 0

    assert (pkg_a_dir / "__init__.py").read_text() == "VALUE = 1\n"
    assert (pkg_b_dir / "__init__.py").read_text() == "VALUE = 2\n"

    manifest = load_manifest()
    assert manifest["packages"]["pkg_a"]["patches"] == []
    assert len(manifest["packages"]["pkg_b"]["patches"]) == 1


def test_reapplying_an_already_applied_patch_is_skipped_with_a_warning(fake_venv, make_package, tmp_path, capsys):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])

    assert cli.main(["apply", "-f", str(toml_path)]) == 0
    head_after_first = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=pkg_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    capsys.readouterr()
    rc = cli.main(["apply", "-f", str(toml_path)])
    err = capsys.readouterr().err

    assert rc == 0
    assert "already applied" in err

    head_after_second = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=pkg_dir, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert head_after_first == head_after_second

    manifest = load_manifest()
    assert len(manifest["packages"]["dummypkg"]["patches"]) == 1


def test_apply_detects_edited_patch_content_and_errors_without_force(fake_venv, make_package, tmp_path, capsys):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])

    assert cli.main(["apply", "-f", str(toml_path)]) == 0
    manifest = load_manifest()
    assert manifest["packages"]["dummypkg"]["patches"][0]["patch_sha256"]

    head_after_first = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=pkg_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    # the patch is edited after being applied, without a pinned sha256sum
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 3"))

    capsys.readouterr()
    rc = cli.main(["apply", "-f", str(toml_path)])
    err = capsys.readouterr().err

    assert rc == 1
    assert "content has changed" in err
    assert "--force" in err

    # nothing was touched: neither the package nor its manifest history
    head_after_second = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=pkg_dir, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert head_after_first == head_after_second

    manifest = load_manifest()
    patches = manifest["packages"]["dummypkg"]["patches"]
    assert len(patches) == 2
    assert patches[0]["status"] == "applied"
    assert patches[1]["status"] == "failed"


def test_apply_reports_missing_patch_file_for_an_already_applied_entry(fake_venv, make_package, tmp_path):
    make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])

    assert cli.main(["apply", "-f", str(toml_path)]) == 0

    patch_file.unlink()

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1

    manifest = load_manifest()
    assert manifest["packages"]["dummypkg"]["patches"][-1]["error"] == f"patch file not found: {patch_file}"


def test_apply_force_reapplies_cleanly_after_content_drift(fake_venv, make_package, tmp_path):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])

    assert cli.main(["apply", "-f", str(toml_path)]) == 0

    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 3"))
    assert cli.main(["apply", "-f", str(toml_path)]) == 1  # detected drift, refuses

    assert cli.main(["apply", "-f", str(toml_path), "--force"]) == 0
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 3\n"


def test_apply_aborts_on_missing_package_by_default(fake_venv, make_package, tmp_path):
    make_package("pkg_a", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    toml_path = _write_toml(
        tmp_path,
        [
            {"path": "bump.patch", "package": "does_not_exist_pkg"},
            {"path": "bump.patch", "package": "pkg_a", "apply-command": "git apply"},
        ],
    )

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1

    manifest = load_manifest()
    assert manifest["packages"]["does_not_exist_pkg"]["patches"][0]["status"] == "failed"
    # aborted before reaching the second entry
    assert "pkg_a" not in manifest["packages"]


def test_apply_skip_missing_continues_past_missing_packages(fake_venv, make_package, tmp_path):
    pkg_dir = make_package("pkg_a", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))

    toml_path = _write_toml(
        tmp_path,
        [
            {"path": "bump.patch", "package": "does_not_exist_pkg"},
            {"path": "bump.patch", "package": "pkg_a", "apply-command": "git apply"},
        ],
    )

    rc = cli.main(["apply", "-f", str(toml_path), "--skip-missing"])
    assert rc == 1  # still non-zero: the missing package is a recorded failure

    manifest = load_manifest()
    assert manifest["packages"]["does_not_exist_pkg"]["patches"][0]["status"] == "failed"
    assert manifest["packages"]["pkg_a"]["patches"][0]["status"] == "applied"
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 2\n"


def test_apply_malformed_toml_reports_error(fake_venv, tmp_path, capsys):
    toml_path = tmp_path / "bad.toml"
    toml_path.write_text(dump_toml({"version": 1, "patches": [{"path": "x.patch"}]}))

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1
    assert "missing required field" in capsys.readouterr().err


def test_apply_records_failure_when_git_init_fails(fake_venv, make_package, tmp_path, fail_git_subcommand):
    make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg"}])

    fail_git_subcommand("init", "init boom")

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1

    manifest = load_manifest()
    entry = manifest["packages"]["dummypkg"]["patches"][0]
    assert entry["status"] == "failed"
    assert "could not initialize git tracking" in entry["error"]


def test_reset_skips_package_with_location_but_no_initial_commit(
    fake_venv, make_package, tmp_path, fail_git_subcommand, capsys
):
    # A package whose git init failed has its location recorded but never
    # gets an initial_commit; reset must skip it rather than crash.
    make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg"}])

    fail_git_subcommand("init", "init boom")
    cli.main(["apply", "-f", str(toml_path)])

    capsys.readouterr()
    rc = cli.main(["reset"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "dummypkg" not in out


def test_apply_records_failure_when_patch_content_is_invalid(fake_venv, make_package, tmp_path):
    make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bad.patch"
    patch_file.write_text("this is not a valid patch\n")
    toml_path = _write_toml(tmp_path, [{"path": "bad.patch", "package": "dummypkg", "apply-command": "git apply"}])

    rc = cli.main(["apply", "-f", str(toml_path)])
    assert rc == 1

    manifest = load_manifest()
    entry = manifest["packages"]["dummypkg"]["patches"][0]
    assert entry["status"] == "failed"
    assert entry["error"]


def test_list_reports_no_patches_on_a_fresh_environment(fake_venv, capsys):
    rc = cli.main(["list"])
    assert rc == 0
    assert "No patches applied in this environment." in capsys.readouterr().out


def test_list_prints_error_for_a_failed_patch(fake_venv, tmp_path, capsys):
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "does_not_exist_pkg"}])
    cli.main(["apply", "-f", str(toml_path)])

    capsys.readouterr()
    rc = cli.main(["list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[FAIL]" in out
    assert "error:" in out


def test_reset_reports_no_patches_on_a_fresh_environment(fake_venv, capsys):
    rc = cli.main(["reset"])
    assert rc == 0
    assert "No patches to reset." in capsys.readouterr().out


def test_reset_skips_package_that_was_never_git_initialized(fake_venv, tmp_path, capsys):
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "does_not_exist_pkg"}])
    cli.main(["apply", "-f", str(toml_path)])

    capsys.readouterr()
    rc = cli.main(["reset"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "does_not_exist_pkg" not in out


def test_reset_warns_when_package_location_no_longer_exists(fake_venv, make_package, tmp_path, capsys):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])
    assert cli.main(["apply", "-f", str(toml_path)]) == 0

    shutil.rmtree(pkg_dir)

    capsys.readouterr()
    rc = cli.main(["reset"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "no longer exists" in err


def test_reset_reports_failure_when_reset_package_fails(fake_venv, make_package, tmp_path, monkeypatch):
    make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])
    assert cli.main(["apply", "-f", str(toml_path)]) == 0

    monkeypatch.setattr(cli, "reset_package", lambda package_dir, initial_commit: (False, "boom"))

    rc = cli.main(["reset"])
    assert rc == 1


def test_apply_force_applies_normally_when_nothing_was_previously_applied(fake_venv, make_package, tmp_path):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])

    rc = cli.main(["apply", "-f", str(toml_path), "--force"])
    assert rc == 0
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 2\n"


def test_apply_force_resets_the_package_then_reapplies_edited_patch_content(fake_venv, make_package, tmp_path, capsys):
    pkg_dir = make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])

    assert cli.main(["apply", "-f", str(toml_path)]) == 0
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 2\n"

    # the patch is still under development: its content changes, but its
    # path (and thus its identity as far as venv-patcher is concerned) doesn't.
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 3"))

    capsys.readouterr()
    rc = cli.main(["apply", "-f", str(toml_path), "--force"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "reset dummypkg" in out
    assert (pkg_dir / "__init__.py").read_text() == "VALUE = 3\n"

    manifest = load_manifest()
    patches = manifest["packages"]["dummypkg"]["patches"]
    assert len(patches) == 1
    assert patches[0]["status"] == "applied"

    history = subprocess.run(
        ["git", "log", "--format=%s"], cwd=pkg_dir, check=True, capture_output=True, text=True
    ).stdout.split("\n")
    history = [line for line in history if line]
    assert len(history) == 2  # initial + the reapplied patch, no leftover commits


def test_apply_force_only_resets_the_given_package_with_dash_p(fake_venv, make_package, tmp_path):
    pkg_a_dir = make_package("pkg_a", "VALUE = 1\n")
    pkg_b_dir = make_package("pkg_b", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(
        tmp_path,
        [
            {"path": "bump.patch", "package": "pkg_a", "apply-command": "git apply"},
            {"path": "bump.patch", "package": "pkg_b", "apply-command": "git apply"},
        ],
    )

    assert cli.main(["apply", "-f", str(toml_path)]) == 0

    # only pkg_a is force-reapplied; pkg_b is untouched by the -p filter
    rc = cli.main(["apply", "-f", str(toml_path), "-p", "pkg_a", "--force"])
    assert rc == 0

    manifest = load_manifest()
    assert len(manifest["packages"]["pkg_a"]["patches"]) == 1
    assert len(manifest["packages"]["pkg_b"]["patches"]) == 1
    assert (pkg_a_dir / "__init__.py").read_text() == "VALUE = 2\n"
    assert (pkg_b_dir / "__init__.py").read_text() == "VALUE = 2\n"


def test_apply_force_without_dash_p_resets_every_tracked_package(fake_venv, make_package, tmp_path):
    pkg_a_dir = make_package("pkg_a", "VALUE = 1\n")
    pkg_b_dir = make_package("pkg_b", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "pkg_a", "apply-command": "git apply"}])
    other_toml_path = _write_toml(
        tmp_path,
        [{"path": "bump.patch", "package": "pkg_b", "apply-command": "git apply"}],
        name="other_patches.toml",
    )

    assert cli.main(["apply", "-f", str(toml_path)]) == 0
    assert cli.main(["apply", "-f", str(other_toml_path)]) == 0

    # --force with no -p resets every package tracked in the manifest, even
    # pkg_b which isn't mentioned in this run's toml file.
    rc = cli.main(["apply", "-f", str(toml_path), "--force"])
    assert rc == 0

    manifest = load_manifest()
    assert len(manifest["packages"]["pkg_a"]["patches"]) == 1
    assert manifest["packages"]["pkg_b"]["patches"] == []
    assert (pkg_a_dir / "__init__.py").read_text() == "VALUE = 2\n"
    assert (pkg_b_dir / "__init__.py").read_text() == "VALUE = 1\n"


def test_apply_force_records_failure_when_reset_fails(fake_venv, make_package, tmp_path, monkeypatch):
    make_package("dummypkg", "VALUE = 1\n")
    patch_file = tmp_path / "bump.patch"
    patch_file.write_text(make_plain_diff("VALUE = 1", "VALUE = 2"))
    toml_path = _write_toml(tmp_path, [{"path": "bump.patch", "package": "dummypkg", "apply-command": "git apply"}])
    assert cli.main(["apply", "-f", str(toml_path)]) == 0

    monkeypatch.setattr(cli, "reset_package", lambda package_dir, initial_commit: (False, "boom"))

    rc = cli.main(["apply", "-f", str(toml_path), "--force"])
    assert rc == 1

    manifest = load_manifest()
    # the failed reset shouldn't have wiped the previously recorded patch
    assert len(manifest["packages"]["dummypkg"]["patches"]) == 1
