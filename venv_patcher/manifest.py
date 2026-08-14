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
    """Return the path to the current environment's manifest file."""
    return get_site_packages_dir() / MANIFEST_FILENAME


def load_manifest() -> dict:
    """Load the current environment's manifest, or an empty one if none exists yet."""
    path = get_manifest_path()
    if not path.is_file():
        return {"packages": {}}
    with path.open() as f:
        data = json.load(f)
    data.setdefault("packages", {})
    return data


def save_manifest(manifest: dict) -> None:
    """Write manifest to disk atomically."""
    path = get_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp_path.replace(path)


def get_package_record(manifest: dict, package: str) -> dict:
    """Return package's record in manifest, creating an empty one if it doesn't exist yet."""
    return manifest["packages"].setdefault(package, {"location": None, "initial_commit": None, "patches": []})
