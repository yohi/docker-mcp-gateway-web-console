from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_fake_docker(path: Path, log_path: Path, exec_log_path: Path) -> None:
    content = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        echo "$@" >> "{log_path}"

        # Handle docker --host unix:///path ps
        if [[ "${{1:-}}" == "--host" ]] || [[ "${{1:-}}" == --host=* ]]; then
          host_arg="${{1:-}}"
          shift || true
          host_value="${{host_arg#--host=}}"
          if [ "$host_arg" = "--host" ]; then
            host_value="${{1:-}}"
            shift || true
          fi
          echo "host:${{host_value}}:${{*}}" >> "{exec_log_path}"
          exit 0
        fi

        if [ "${{1:-}}" != "compose" ]; then
          exit 0
        fi

        shift
        compose_file="unknown"
        if [ "${{1:-}}" = "-f" ]; then
          compose_file="${{2:-}}"
          shift 2 || true
        fi

        action="${{1:-}}"
        if [ "$action" = "config" ]; then
          cat "${{compose_file}}"
          exit 0
        fi

        if [ "$action" = "exec" ]; then
          shift
          if [ "${{1:-}}" = "-T" ]; then
            shift
          fi
          service="${{1:-}}"
          shift || true
          cmd="${{1:-}}"
          shift || true
          echo "exec:${{compose_file}}:${{service}}:${{cmd}}:${{*}}" >> "{exec_log_path}"

          if [ "$service" = "backend" ] && [ "$cmd" = "curl" ]; then
            if [ "${{FAIL_HEALTH:-0}}" = "1" ]; then
              echo "unhealthy"
            else
              echo '{{"status":"ok"}}'
            fi
            exit 0
          fi

          if [ "$service" = "backend" ] && [ "$cmd" = "python3" ]; then
            if [ "${{FAIL_DOCKER_PING:-0}}" = "1" ]; then
              exit 1
            fi
            exit 0
          fi

          if [ "$service" = "workspace" ] && [ "$cmd" = "python3" ]; then
            if [ "${{FAIL_DOCKER_PING:-0}}" = "1" ]; then
              exit 1
            fi
            exit 0
          fi

          if [ "$service" = "frontend" ] && [ "$cmd" = "curl" ]; then
            echo '{{"api":"ok"}}'
            exit 0
          fi

          exit 0
        fi

        exit 0
        """
    )
    _write_executable(path, content)


def _prepare_repo(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()

    (tmp_path / "docker-compose.yml").write_text(
        "version: '3.8'\nservices:\n  backend:\n    image: dummy\n  frontend:\n    image: dummy\n",
        encoding="utf-8",
    )
    (devcontainer_dir / "docker-compose.devcontainer.yml").write_text(
        textwrap.dedent(
            """\
            version: '3.8'
            services:
              workspace:
                image: dummy
                volumes:
                  - dind-certs:/certs/client:ro
                environment:
                  - DOCKER_HOST=tcp://dind:2376
                  - DOCKER_TLS_VERIFY=1
                  - DOCKER_CERT_PATH=/certs/client
                depends_on:
                  - backend
                  - frontend
                  - dind
              dind:
                image: docker:dind
              backend:
                image: dummy
                volumes:
                  - dind-certs:/certs/client:ro
                environment:
                  - DOCKER_HOST=tcp://dind:2376
                  - DOCKER_TLS_VERIFY=1
                  - DOCKER_CERT_PATH=/certs/client
              frontend:
                image: dummy
            volumes:
              dind-certs:
            """
        ),
        encoding="utf-8",
    )


def test_verify_integration_script_exists_and_executable() -> None:
    script = _repo_root() / "scripts" / "verify-integration.sh"
    assert script.exists(), "Missing scripts/verify-integration.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/verify-integration.sh must be executable"


def test_verify_integration_script_runs_checks_with_dind_verification(tmp_path: Path) -> None:
    _prepare_repo(tmp_path)

    log_path = tmp_path / "docker-calls.log"
    exec_log_path = tmp_path / "docker-exec.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path, exec_log_path)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["CI"] = "true"

    script_under_test = _repo_root() / "scripts" / "verify-integration.sh"
    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=tmp_path,
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

    exec_calls = exec_log_path.read_text(encoding="utf-8").splitlines()
    assert any("backend:curl" in line and "docker-compose" in line for line in exec_calls), "backend health check not invoked"
    assert any("frontend:curl" in line and "docker-compose" in line for line in exec_calls), "frontend->backend check not invoked"
    assert any("backend:python3" in line and "docker-compose.devcontainer.yml" in line for line in exec_calls), "devcontainer backend docker check not invoked"
    assert any("workspace:python3" in line and "docker-compose.devcontainer.yml" in line for line in exec_calls), "devcontainer workspace docker check not invoked"
    assert any("frontend:npm" in line and "docker-compose.devcontainer.yml" in line for line in exec_calls), "devcontainer frontend check not invoked"
    assert not any("host:unix://" in line for line in exec_calls), "host socket based docker check should not run"


def test_verify_integration_script_fails_on_unhealthy_backend(tmp_path: Path) -> None:
    _prepare_repo(tmp_path)

    log_path = tmp_path / "docker-calls.log"
    exec_log_path = tmp_path / "docker-exec.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path, exec_log_path)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["FAIL_HEALTH"] = "1"
    env["CI"] = "true"

    script_under_test = _repo_root() / "scripts" / "verify-integration.sh"
    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "health" in combined_output.lower()


def test_verify_integration_script_fails_on_missing_dind_config(tmp_path: Path) -> None:
    _prepare_repo(tmp_path)
    # Mutate devcontainer compose to remove dind service
    dev_compose = tmp_path / ".devcontainer" / "docker-compose.devcontainer.yml"
    content = dev_compose.read_text(encoding="utf-8")
    
    import re
    # Locate the dind service definition and rename it to make it 'missing' for the script
    content = re.sub(r"(?m)^(\s*)dind:", r"\1dind_backup:", content)
    dev_compose.write_text(content, encoding="utf-8")

    log_path = tmp_path / "docker-calls.log"
    exec_log_path = tmp_path / "docker-exec.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path, exec_log_path)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["CI"] = "true"

    script_under_test = _repo_root() / "scripts" / "verify-integration.sh"
    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "dind service missing" in combined_output


def test_verify_integration_script_fails_on_dind_unreachable(tmp_path: Path) -> None:
    _prepare_repo(tmp_path)

    log_path = tmp_path / "docker-calls.log"
    exec_log_path = tmp_path / "docker-exec.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker", log_path, exec_log_path)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["FAIL_DOCKER_PING"] = "1"
    env["CI"] = "true"

    script_under_test = _repo_root() / "scripts" / "verify-integration.sh"
    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "could not connect to dind" in combined_output.lower()
