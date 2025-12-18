from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_devcontainer_json_exists() -> None:
    devcontainer_json = _repo_root() / ".devcontainer" / "devcontainer.json"
    assert devcontainer_json.exists(), "Missing .devcontainer/devcontainer.json"


def test_devcontainer_json_meets_minimum_requirements() -> None:
    devcontainer_json = _repo_root() / ".devcontainer" / "devcontainer.json"
    data = json.loads(devcontainer_json.read_text(encoding="utf-8"))

    assert isinstance(data.get("name"), str) and data["name"]
    assert data.get("service") == "workspace"
    assert data.get("workspaceFolder") == "/workspace"

    docker_compose_files = data.get("dockerComposeFile")
    assert isinstance(docker_compose_files, list)
    assert "../docker-compose.yml" in docker_compose_files
    assert "docker-compose.devcontainer.yml" in docker_compose_files

    customizations = data.get("customizations", {})
    vscode = customizations.get("vscode", {})
    extensions = vscode.get("extensions")
    assert isinstance(extensions, list)

    required_extensions = {
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "bradlc.vscode-tailwindcss",
    }
    assert required_extensions.issubset(set(extensions))
    assert len(extensions) >= 6

    forward_ports = data.get("forwardPorts")
    assert isinstance(forward_ports, list)
    assert 3000 in forward_ports
    assert 8000 in forward_ports

    post_create = data.get("postCreateCommand")
    assert isinstance(post_create, str) and post_create.strip()
