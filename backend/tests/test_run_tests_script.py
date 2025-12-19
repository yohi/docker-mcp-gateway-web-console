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


def _write_fake_docker(
    path: Path,
    log_path: Path,
    exec_log_path: Path,
    *,
    running_services: tuple[str, ...],
    fail_service: str | None = None,
) -> None:
    services_echo = (
        "printf '%s\\n' " + " ".join(f'"{svc}"' for svc in running_services)
        if running_services
        else ":"
    )
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
          shift 2 || break
        done

        action="${{1:-}}"

        if [ "$action" = "ps" ]; then
          {services_echo}
          exit 0
        fi

        if [ "$action" = "exec" ]; then
          shift
          if [ "${{1:-}}" = "-T" ]; then
            shift
          fi

          service="${{1:-}}"
          shift || true
          echo "exec:${{service}}:${{*}}" >> "{exec_log_path}"

          if [ "{fail_service or ''}" != "" ] && [ "$service" = "{fail_service}" ]; then
            exit 1
          fi

          exit 0
        fi

        exit 0
        """
    )
    _write_executable(path, content)


def _write_fake_timeout(path: Path, log_path: Path) -> None:
    content = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        echo "timeout:$@" >> "{log_path}"
        shift || true
        if [ "${{FAIL_TIMEOUT:-0}}" = "1" ]; then
          exit 124
        fi
        "$@"
        """
    )
    _write_executable(path, content)


def test_run_tests_script_exists_and_executable() -> None:
    script = _repo_root() / "scripts" / "run-tests.sh"
    assert script.exists(), "Missing scripts/run-tests.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/run-tests.sh must be executable"


def test_backend_mode_invokes_pytest_with_timeout_and_ci_flag(tmp_path: Path) -> None:
    repo_root = _repo_root()
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        "version: '3.8'\nservices:\n  backend:\n    image: dummy\n  frontend:\n    image: dummy\n",
        encoding="utf-8",
    )

    log_path = tmp_path / "docker.log"
    exec_log = tmp_path / "exec.log"
    timeout_log = tmp_path / "timeout.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(
        fake_bin / "docker",
        log_path,
        exec_log,
        running_services=("backend",),
    )
    _write_fake_timeout(fake_bin / "timeout", timeout_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = str(compose_file)
    env["CI"] = "true"

    script_under_test = repo_root / "scripts" / "run-tests.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "backend"],
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

    docker_calls = log_path.read_text(encoding="utf-8").splitlines()
    assert any("compose" in call and "ps" in call for call in docker_calls), "docker compose ps should run"
    assert any("-T" in call and "backend" in call for call in docker_calls), "-T flag expected in CI"

    exec_calls = exec_log.read_text(encoding="utf-8").splitlines()
    assert any("exec:backend:pytest" in call for call in exec_calls), "backend pytest not invoked"
    assert any("--json-report-file=/tmp/pytest-results.json" in call for call in exec_calls), "pytest JSON report missing"

    timeout_calls = timeout_log.read_text(encoding="utf-8").splitlines()
    assert timeout_calls, "timeout should be invoked"
    first_timeout = timeout_calls[0]
    assert "timeout:300" in first_timeout, "backend default timeout should be 300 seconds"


def test_all_mode_stops_on_failure_and_skips_later_stages(tmp_path: Path) -> None:
    repo_root = _repo_root()
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("version: '3.8'\nservices:\n  backend:\n  frontend:\n", encoding="utf-8")

    log_path = tmp_path / "docker.log"
    exec_log = tmp_path / "exec.log"
    timeout_log = tmp_path / "timeout.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(
        fake_bin / "docker",
        log_path,
        exec_log,
        running_services=("backend", "frontend"),
        fail_service="frontend",
    )
    _write_fake_timeout(fake_bin / "timeout", timeout_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = str(compose_file)
    env["CI"] = "true"

    script_under_test = repo_root / "scripts" / "run-tests.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "all"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, "should propagate test failure as exit code 1"
    exec_calls = exec_log.read_text(encoding="utf-8").splitlines()
    assert any("exec:backend:pytest" in call for call in exec_calls), "backend tests should run first"
    assert any("exec:frontend:npm test" in call for call in exec_calls), "frontend tests should run after backend"
    assert not any("test:e2e" in call for call in exec_calls), "e2e tests should be skipped after failure"


def test_missing_compose_file_returns_exit_code_3(tmp_path: Path) -> None:
    repo_root = _repo_root()
    missing_compose = tmp_path / "nope.yml"

    log_path = tmp_path / "docker.log"
    exec_log = tmp_path / "exec.log"
    timeout_log = tmp_path / "timeout.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(
        fake_bin / "docker",
        log_path,
        exec_log,
        running_services=(),
    )
    _write_fake_timeout(fake_bin / "timeout", timeout_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = str(missing_compose)

    script_under_test = repo_root / "scripts" / "run-tests.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "backend"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 3
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "Compose file not found" in combined_output


def test_compose_file_order_preserves_override_priority(tmp_path: Path) -> None:
    repo_root = _repo_root()
    base_compose = tmp_path / "docker-compose.yml"
    override_compose = tmp_path / "docker-compose.override.yml"
    base_compose.write_text("version: '3.8'\nservices:\n  backend:\n    image: dummy\n", encoding="utf-8")
    override_compose.write_text("version: '3.8'\nservices:\n  backend:\n    image: override\n", encoding="utf-8")

    log_path = tmp_path / "docker.log"
    exec_log = tmp_path / "exec.log"
    timeout_log = tmp_path / "timeout.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(
        fake_bin / "docker",
        log_path,
        exec_log,
        running_services=("backend",),
    )
    _write_fake_timeout(fake_bin / "timeout", timeout_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = f"{base_compose}:{override_compose}"
    env["CI"] = "true"

    script_under_test = repo_root / "scripts" / "run-tests.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "backend"],
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

    docker_calls = log_path.read_text(encoding="utf-8").splitlines()
    ps_call = next((line for line in docker_calls if "compose" in line and "ps" in line), "")
    exec_call = next((line for line in docker_calls if "compose" in line and "exec" in line), "")
    assert ps_call, "docker compose ps should be invoked"
    assert exec_call, "docker compose exec should be invoked"

    def _is_order_correct(call: str) -> bool:
        parts = call.split()
        return parts.index(str(base_compose)) < parts.index(str(override_compose))

    assert _is_order_correct(ps_call), "compose files should keep base before override for priority resolution"
    assert _is_order_correct(exec_call), "compose exec should keep base before override for priority resolution"


def test_invalid_mode_returns_exit_code_2(tmp_path: Path) -> None:
    repo_root = _repo_root()
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("version: '3.8'\nservices:\n  backend:\n", encoding="utf-8")

    log_path = tmp_path / "docker.log"
    exec_log = tmp_path / "exec.log"
    timeout_log = tmp_path / "timeout.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(
        fake_bin / "docker",
        log_path,
        exec_log,
        running_services=("backend",),
    )
    _write_fake_timeout(fake_bin / "timeout", timeout_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = str(compose_file)

    script_under_test = repo_root / "scripts" / "run-tests.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "invalid-mode"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "Usage" in combined_output


def test_backend_mode_fails_when_service_not_running(tmp_path: Path) -> None:
    repo_root = _repo_root()
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("version: '3.8'\nservices:\n  backend:\n", encoding="utf-8")

    log_path = tmp_path / "docker.log"
    exec_log = tmp_path / "exec.log"
    timeout_log = tmp_path / "timeout.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(
        fake_bin / "docker",
        log_path,
        exec_log,
        running_services=(),
    )
    _write_fake_timeout(fake_bin / "timeout", timeout_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = str(compose_file)
    env["CI"] = "true"

    script_under_test = repo_root / "scripts" / "run-tests.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "backend"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 3
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "backend service is not running" in combined_output.lower()


def test_timeout_exit_code_is_mapped_to_four(tmp_path: Path) -> None:
    repo_root = _repo_root()
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("version: '3.8'\nservices:\n  backend:\n", encoding="utf-8")

    log_path = tmp_path / "docker.log"
    exec_log = tmp_path / "exec.log"
    timeout_log = tmp_path / "timeout.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(
        fake_bin / "docker",
        log_path,
        exec_log,
        running_services=("backend",),
    )
    _write_fake_timeout(fake_bin / "timeout", timeout_log)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COMPOSE_FILE"] = str(compose_file)
    env["FAIL_TIMEOUT"] = "1"
    env["CI"] = "true"

    script_under_test = repo_root / "scripts" / "run-tests.sh"
    result = subprocess.run(
        ["bash", str(script_under_test), "backend"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 4
    assert timeout_log.read_text(encoding="utf-8").strip(), "timeout should be called even on failure"
