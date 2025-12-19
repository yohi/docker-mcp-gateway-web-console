from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_fake_docker(
    script_path: Path,
    log_path: Path,
    *,
    node_version: str = "v22.12.0",
    health_body: str = "ok",
    fail_health: bool = False,
) -> None:
    """Create a fake docker executable that logs invocations for assertions."""
    content = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        echo "$@" >> "{log_path}"

        if [ "${{1:-}}" != "compose" ]; then
          exit 0
        fi

        shift
        while [ "${{1:-}}" = "-f" ]; do
          shift 2 || true
        done

        action="${{1:-}}"

        case "$action" in
          build|up|stop|down|logs)
            exit 0
            ;;
          exec)
            shift
            if [ "${{1:-}}" = "-T" ]; then
              shift
            fi
            service="${{1:-}}"
            shift
            cmd="${{1:-}}"
            shift

            if [ "$service" = "frontend" ] && [ "$cmd" = "node" ] && [ "${{1:-}}" = "--version" ]; then
              echo "{node_version}"
              exit 0
            fi

            if [ "$service" = "frontend" ] && [ "$cmd" = "curl" ]; then
              if [ "{1 if fail_health else 0}" = "1" ]; then
                echo "curl: (7) failed to connect" >&2
                exit 1
              fi
              echo '{health_body}'
              exit 0
            fi
            ;;
        esac

        exit 1
        """
    )
    script_path.write_text(content, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)


def test_verify_frontend_build_script_exists_and_executable() -> None:
    script = _repo_root() / "scripts" / "verify-frontend-build.sh"
    assert script.exists(), "Missing scripts/verify-frontend-build.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/verify-frontend-build.sh must be executable"


def test_verify_frontend_build_script_passes_with_fake_docker(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "frontend").mkdir()
    (repo_root / "docker-compose.yml").write_text(
        "version: '3.8'\nservices:\n  frontend:\n    image: frontend:dev\n",
        encoding="utf-8",
    )

    log_path = repo_root / "docker-calls.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    script_under_test = _repo_root() / "scripts" / "verify-frontend-build.sh"
    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, textwrap.dedent(
        f"""
        Expected success but got exit code {result.returncode}
        --- stdout ---
        {result.stdout}
        --- stderr ---
        {result.stderr}
        """
    )

    commands = log_path.read_text(encoding="utf-8").splitlines()
    assert any("build" in cmd and "frontend" in cmd for cmd in commands), "docker compose build not invoked"
    assert any("up" in cmd and "frontend" in cmd for cmd in commands), "docker compose up not invoked"
    assert any("node --version" in cmd for cmd in commands), "node version check not invoked"
    assert any("curl -fsSL http://localhost:3000" in cmd for cmd in commands), "health check not invoked"


def test_verify_frontend_build_script_fails_on_wrong_node_version(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "frontend").mkdir()
    (repo_root / "docker-compose.yml").write_text(
        "version: '3.8'\nservices:\n  frontend:\n    image: frontend:dev\n",
        encoding="utf-8",
    )

    log_path = repo_root / "docker-calls.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path, node_version="v21.9.0")

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    script_under_test = _repo_root() / "scripts" / "verify-frontend-build.sh"
    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "v22.12" in combined_output, "Expected error mentioning required Node.js version"
    commands = log_path.read_text(encoding="utf-8").splitlines()
    assert any("node --version" in cmd for cmd in commands), "node version check not invoked before failure"
    assert any("logs frontend" in cmd for cmd in commands), "docker compose logs should be emitted on failure"
