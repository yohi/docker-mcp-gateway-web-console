from __future__ import annotations

import re
from pathlib import Path


def test_workspace_dockerfile_exists() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dockerfile = repo_root / ".devcontainer" / "Dockerfile.workspace"
    assert dockerfile.exists(), "Missing .devcontainer/Dockerfile.workspace"


def test_workspace_dockerfile_has_pinned_versions_and_tools() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dockerfile = repo_root / ".devcontainer" / "Dockerfile.workspace"
    text = dockerfile.read_text(encoding="utf-8")

    assert re.search(r"^FROM\s+python:3\.14\.2-slim\s*$", text, flags=re.M), (
        "Dockerfile.workspace must pin base image to python:3.14.2-slim"
    )

    assert "WORKDIR /workspace" in text
    assert 'CMD ["sleep", "infinity"]' in text

    for tool in ("git", "curl"):
        assert re.search(rf"\b{re.escape(tool)}\b", text), f"Must install {tool}"

    assert re.search(r"22\.21\.1", text), "Must pin Node.js to 22.21.1"

    assert re.search(
        r"(get\.docker\.com|docker-ce-cli|docker\.io)",
        text,
        flags=re.I,
    ), "Must install Docker CLI"
