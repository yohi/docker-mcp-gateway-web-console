from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_manifest() -> Dict[str, str]:
    manifest = _repo_root() / ".kiro" / "specs" / "tech-stack-devcontainer" / "version-manifest.json"
    assert manifest.exists(), "Missing version-manifest.json for tech-stack-devcontainer"

    data = json.loads(manifest.read_text(encoding="utf-8"))
    required_keys = {"python", "node", "next", "react"}
    missing = required_keys.difference(data.keys())
    assert not missing, f"Manifest is missing keys: {sorted(missing)}"

    pins: Dict[str, str] = {}
    for key in required_keys:
        value = str(data[key])
        assert re.match(r"^\d+\.\d+\.\d+$", value), f"{key} version must be pinned to patch level (got {value})"
        pins[key] = value

    assert pins["python"].startswith("3.14."), "python pin must be for the 3.14.x line"
    assert pins["node"].startswith("22.12."), "node pin must be for the 22.12.x line"
    assert pins["next"].startswith("15.5."), "next pin must be for the 15.5.x line"
    assert pins["react"].startswith("19.2."), "react pin must be for the 19.2.x line"

    return pins


def test_version_manifest_exists_and_has_expected_pins() -> None:
    pins = _load_manifest()
    assert pins["python"].count(".") == 2
    assert pins["node"].count(".") == 2
    assert pins["next"].count(".") == 2
    assert pins["react"].count(".") == 2


def test_versions_are_consistent_across_repo_files() -> None:
    pins = _load_manifest()
    repo = _repo_root()

    python_image = f"python:{pins['python']}-slim"
    for dockerfile in (
        repo / ".devcontainer" / "Dockerfile.workspace",
        repo / "backend" / "Dockerfile",
        repo / "backend" / "Dockerfile.dev",
    ):
        assert dockerfile.exists(), f"Missing {dockerfile}"
        text = dockerfile.read_text(encoding="utf-8")
        assert python_image in text, f"{dockerfile} must pin {python_image}"

    node_image = f"node:{pins['node']}-alpine"
    for dockerfile in (
        repo / "frontend" / "Dockerfile",
    ):
        assert dockerfile.exists(), f"Missing {dockerfile}"
        text = dockerfile.read_text(encoding="utf-8")
        assert node_image in text, f"{dockerfile} must pin {node_image}"

    node_dev_image = f"node:{pins['node']}-bookworm"
    for dockerfile in (
        repo / "frontend" / "Dockerfile.dev",
    ):
        assert dockerfile.exists(), f"Missing {dockerfile}"
        text = dockerfile.read_text(encoding="utf-8")
        assert node_dev_image in text, f"{dockerfile} must pin {node_dev_image}"

    pkg_json_path = repo / "frontend" / "package.json"
    assert pkg_json_path.exists(), "Missing frontend/package.json"
    pkg_json = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    dependencies: Dict[str, Any] = pkg_json.get("dependencies", {})
    assert dependencies.get("next") == pins["next"], "package.json next version must match manifest"
    assert dependencies.get("react") == pins["react"], "package.json react version must match manifest"
    assert dependencies.get("react-dom") == pins["react"], "package.json react-dom version must match manifest"

    requirements = repo / "backend" / "requirements.txt"
    assert requirements.exists(), "backend/requirements.txt must be committed"
    assert requirements.stat().st_size > 0, "backend/requirements.txt must not be empty"

    package_lock = repo / "frontend" / "package-lock.json"
    assert package_lock.exists(), "frontend/package-lock.json must be committed"
    assert package_lock.stat().st_size > 0, "frontend/package-lock.json must not be empty"

    lock_data = json.loads(package_lock.read_text(encoding="utf-8"))
    lock_packages: Dict[str, Any] = lock_data.get("packages", {})
    root_package = lock_packages.get("", {})
    root_deps: Dict[str, Any] = root_package.get("dependencies", {})
    assert root_deps.get("next") == pins["next"], "package-lock root dependencies must pin next to manifest version"

    next_package = lock_packages.get("node_modules/next")
    assert isinstance(next_package, dict), "package-lock.json must include node_modules/next entry"
    assert next_package.get("version") == pins["next"], "package-lock next package version must match manifest"
