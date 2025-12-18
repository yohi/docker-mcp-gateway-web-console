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
    python_version: str = "Python 3.14.0",
    fail_import: bool = False,
    health_payload: str = '{"status":"healthy"}',
) -> None:
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
        if [ "$action" = "build" ] || [ "$action" = "up" ] || [ "$action" = "stop" ] || [ "$action" = "down" ]; then
          exit 0
        fi

        if [ "$action" = "exec" ]; then
          shift
          if [ "${{1:-}}" = "-T" ]; then
            shift
          fi

          shift # service name
          cmd="${{1:-}}"

          if [ "$cmd" = "python" ] && [ "${{2:-}}" = "--version" ]; then
            echo "{python_version}"
            exit 0
          fi

          if [ "$cmd" = "python" ] && [ "${{2:-}}" = "-" ]; then
            cat >/dev/null
            if [ "{1 if fail_import else 0}" = "1" ]; then
              echo "FAILED:cryptography:boom" >&2
              exit 1
            fi
            exit 0
          fi

          if [ "$cmd" = "curl" ]; then
            echo '{health_payload}'
            exit 0
          fi
        fi

        exit 1
        """
    )
    script_path.write_text(content, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)


def test_verify_backend_build_script_exists_and_executable() -> None:
    script = _repo_root() / "scripts" / "verify-backend-build.sh"
    assert script.exists(), "Missing scripts/verify-backend-build.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/verify-backend-build.sh must be executable"


def test_verify_backend_build_script_passes_with_fake_docker(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "backend").mkdir()
    (repo_root / "backend" / "Dockerfile").write_text("# dummy\n", encoding="utf-8")
    (repo_root / "docker-compose.yml").write_text(
        "version: '3.8'\nservices:\n  backend:\n    image: backend:dev\n",
        encoding="utf-8",
    )

    log_path = repo_root / "docker-calls.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    script_under_test = _repo_root() / "scripts" / "verify-backend-build.sh"
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
    assert any("build" in cmd and "backend" in cmd for cmd in commands), "docker compose build not invoked"
    assert any("up" in cmd and "backend" in cmd for cmd in commands), "docker compose up not invoked"
    assert any("python --version" in cmd for cmd in commands), "python version check not invoked"
    assert any("python -" in cmd for cmd in commands), "C extension import check not invoked"
    assert any("curl -fsSL http://localhost:8000/health" in cmd for cmd in commands), "health check not invoked"


def test_verify_backend_build_script_fails_on_wrong_python_version(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "backend").mkdir()
    (repo_root / "backend" / "Dockerfile").write_text("# dummy\n", encoding="utf-8")
    (repo_root / "docker-compose.yml").write_text(
        "version: '3.8'\nservices:\n  backend:\n    image: backend:dev\n",
        encoding="utf-8",
    )

    log_path = repo_root / "docker-calls.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path, python_version="Python 3.13.9")

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

    script_under_test = _repo_root() / "scripts" / "verify-backend-build.sh"
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
    assert "Python 3.14" in combined_output
    commands = log_path.read_text(encoding="utf-8").splitlines()
    assert any("python --version" in cmd for cmd in commands), "python version check not invoked before failure"
