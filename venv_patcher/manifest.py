"""Manifest of patches applied within the current environment.

The manifest lives in the venv's site-packages directory so that
"venv-patcher list" and "venv-patcher reset" always reflect the currently active
environment, without needing any extra bookkeeping arguments.
"""

from __future__ import annotations

import json
from pathlib import Path

from venv_patcher.core import get_site_packages_dir

MANIFEST_FILENAME = ".venv-patcher-manifest.json"


def get_manifest_path() -> Path:
    return get_site_packages_dir() / MANIFEST_FILENAME


def load_manifest() -> dict:
    path = get_manifest_path()
    if not path.is_file():
        return {"packages": {}}
    with open(path) as f:
        data = json.load(f)
    data.setdefault("packages", {})
    return data


def save_manifest(manifest: dict) -> None:
    path = get_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp_path.replace(path)


def get_package_record(manifest: dict, package: str) -> dict:
    return manifest["packages"].setdefault(package, {"location": None, "initial_commit": None, "patches": []})
