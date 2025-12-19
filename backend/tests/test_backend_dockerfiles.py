from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_backend_dockerfile_exists() -> None:
    dockerfile = _repo_root() / "backend" / "Dockerfile"
    assert dockerfile.exists(), "Missing backend/Dockerfile"


def test_backend_dockerfile_is_python_314_multistage_with_wheels() -> None:
    dockerfile = _repo_root() / "backend" / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")

    assert re.search(
        r"^FROM\s+python:3\.14\.2-slim\s+AS\s+builder\s*$",
        text,
        flags=re.M,
    ), "backend/Dockerfile must start builder stage with python:3.14.2-slim AS builder"

    for pkg in (
        "build-essential",
        "libffi-dev",
        "libssl-dev",
        "gcc",
        "make",
        "pkg-config",
        "python3-dev",
    ):
        assert re.search(rf"\b{re.escape(pkg)}\b", text), f"builder stage must install {pkg}"

    assert re.search(
        r"^FROM\s+python:3\.14\.2-slim\s+AS\s+runtime\s*$",
        text,
        flags=re.M,
    ), "backend/Dockerfile must define runtime stage with python:3.14.2-slim AS runtime"

    for pkg in ("libffi8", "libssl3"):
        assert re.search(rf"\b{re.escape(pkg)}\b", text), f"runtime stage must install {pkg}"

    assert "COPY --from=builder /wheels /wheels" in text


def test_backend_dockerfile_dev_exists_and_has_dev_stage() -> None:
    dockerfile = _repo_root() / "backend" / "Dockerfile.dev"
    assert dockerfile.exists(), "Missing backend/Dockerfile.dev"

    text = dockerfile.read_text(encoding="utf-8")
    assert re.search(
        r"^FROM\s+runtime\s+AS\s+dev\s*$",
        text,
        flags=re.M,
    ), "backend/Dockerfile.dev must define dev stage starting with FROM runtime AS dev"


def test_backend_requirements_dev_includes_expected_tools() -> None:
    requirements = _repo_root() / "backend" / "requirements-dev.txt"
    assert requirements.exists(), "Missing backend/requirements-dev.txt"

    text = requirements.read_text(encoding="utf-8")
    for pkg in ("debugpy", "ruff", "pytest", "pytest-cov"):
        assert re.search(rf"^\s*{re.escape(pkg)}\b", text, flags=re.M), (
            f"backend/requirements-dev.txt must include {pkg}"
        )
