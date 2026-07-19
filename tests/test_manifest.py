from venv_patcher.manifest import get_manifest_path, get_package_record, load_manifest, save_manifest


def test_load_manifest_defaults_when_missing(fake_venv):
    manifest = load_manifest()
    assert manifest == {"packages": {}}


def test_save_and_load_manifest_round_trip(fake_venv):
    manifest = load_manifest()
    record = get_package_record(manifest, "dummypkg")
    record["location"] = "/some/path"
    record["initial_commit"] = "abc123"
    record["patches"].append({"path": "x.patch", "status": "applied"})
    save_manifest(manifest)

    assert get_manifest_path().is_file()

    reloaded = load_manifest()
    assert reloaded["packages"]["dummypkg"]["location"] == "/some/path"
    assert reloaded["packages"]["dummypkg"]["initial_commit"] == "abc123"
    assert reloaded["packages"]["dummypkg"]["patches"] == [{"path": "x.patch", "status": "applied"}]


def test_get_package_record_creates_default_shape(fake_venv):
    manifest = {"packages": {}}
    record = get_package_record(manifest, "newpkg")
    assert record == {"location": None, "initial_commit": None, "patches": []}
    assert manifest["packages"]["newpkg"] is record
