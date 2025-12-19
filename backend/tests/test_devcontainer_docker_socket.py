import os
import subprocess
from pathlib import Path


def _create_placeholder_socket_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")


def _run_init_script(*, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / ".devcontainer" / "init-docker-socket.sh"
    return subprocess.run(
        [str(script_path)],
        env=env,
        cwd=str(repo_root),
        text=True,
        capture_output=True,
    )


def test_init_docker_socket_prefers_xdg_runtime_dir(tmp_path: Path) -> None:
    xdg_dir = tmp_path / "xdg"
    xdg_socket = xdg_dir / "docker.sock"
    _create_placeholder_socket_file(xdg_socket)

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(xdg_dir)
    env["RUN_USER_DIR_BASE"] = str(tmp_path / "run-user")
    env["ROOTFUL_DOCKER_SOCK"] = str(tmp_path / "var-run" / "docker.sock")
    env["DOCKER_SOCKET_TEST_FILE_OK"] = "1"

    result = _run_init_script(env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"DOCKER_SOCKET={xdg_socket}"


def test_init_docker_socket_falls_back_to_run_user_uid(tmp_path: Path) -> None:
    uid = os.getuid()
    run_user_base = tmp_path / "run-user"
    run_user_socket = run_user_base / str(uid) / "docker.sock"
    _create_placeholder_socket_file(run_user_socket)

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(tmp_path / "xdg-no-sock")
    env["RUN_USER_DIR_BASE"] = str(run_user_base)
    env["ROOTFUL_DOCKER_SOCK"] = str(tmp_path / "var-run" / "docker.sock")
    env["DOCKER_SOCKET_TEST_FILE_OK"] = "1"

    result = _run_init_script(env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"DOCKER_SOCKET={run_user_socket}"


def test_init_docker_socket_falls_back_to_rootful_socket(tmp_path: Path) -> None:
    rootful_socket = tmp_path / "var-run" / "docker.sock"
    _create_placeholder_socket_file(rootful_socket)

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(tmp_path / "xdg-no-sock")
    env["RUN_USER_DIR_BASE"] = str(tmp_path / "run-user")
    env["ROOTFUL_DOCKER_SOCK"] = str(rootful_socket)
    env["DOCKER_SOCKET_TEST_FILE_OK"] = "1"

    result = _run_init_script(env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"DOCKER_SOCKET={rootful_socket}"


def test_init_docker_socket_errors_when_no_socket_found(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(tmp_path / "xdg-no-sock")
    env["RUN_USER_DIR_BASE"] = str(tmp_path / "run-user")
    env["ROOTFUL_DOCKER_SOCK"] = str(tmp_path / "var-run" / "docker.sock")

    result = _run_init_script(env=env)

    assert result.returncode == 1
    assert "Docker socket not found" in result.stderr
    assert f"{env['XDG_RUNTIME_DIR']}/docker.sock" in result.stderr
    assert f"{env['RUN_USER_DIR_BASE']}/{os.getuid()}/docker.sock" in result.stderr
    assert env["ROOTFUL_DOCKER_SOCK"] in result.stderr


def test_init_docker_socket_rejects_regular_file_by_default(tmp_path: Path) -> None:
    xdg_dir = tmp_path / "xdg"
    xdg_socket = xdg_dir / "docker.sock"
    _create_placeholder_socket_file(xdg_socket)

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(xdg_dir)
    env["RUN_USER_DIR_BASE"] = str(tmp_path / "run-user")
    env["ROOTFUL_DOCKER_SOCK"] = str(tmp_path / "var-run" / "docker.sock")
    env.pop("DOCKER_SOCKET_TEST_FILE_OK", None)

    result = _run_init_script(env=env)

    assert result.returncode == 1
    assert "Docker socket not found" in result.stderr


def test_devcontainer_compose_references_detected_socket() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / ".devcontainer" / "docker-compose.devcontainer.yml"

    assert compose_path.exists()
    content = compose_path.read_text(encoding="utf-8")

    assert "${DOCKER_SOCKET}" in content
    assert "workspace:" in content
    assert "depends_on:" in content
    assert "backend" in content
    assert "frontend" in content
