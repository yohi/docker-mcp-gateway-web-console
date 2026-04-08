from __future__ import annotations

from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_yaml(relative_path: str) -> dict:
    return yaml.safe_load((_repo_root() / relative_path).read_text(encoding="utf-8"))


def _assert_backend_uses_dind_tls(services: dict, network_name: str) -> None:
    backend = services["backend"]
    backend_env = backend.get("environment", [])
    backend_volumes = backend.get("volumes", [])
    backend_depends_on = backend.get("depends_on", {})
    backend_networks = backend.get("networks", [])

    assert any(
        "DOCKER_HOST=tcp://dind:2376" in item for item in backend_env
    ), f"Expected DOCKER_HOST=tcp://dind:2376 in environment, but got: {backend_env}"
    assert any(
        "DOCKER_TLS_VERIFY=1" in item for item in backend_env
    ), f"Expected DOCKER_TLS_VERIFY=1 in environment, but got: {backend_env}"
    assert any(
        "DOCKER_CERT_PATH=/certs/client" in item for item in backend_env
    ), f"Expected DOCKER_CERT_PATH=/certs/client in environment, but got: {backend_env}"
    assert any(
        "dind-certs:/certs/client:ro" == item for item in backend_volumes
    ), f"Expected dind-certs:/certs/client:ro in volumes, but got: {backend_volumes}"
    assert (
        "dind" in backend_depends_on
    ), f"Expected 'dind' in depends_on, but got: {backend_depends_on}"
    assert (
        network_name in backend_networks
    ), f"Expected '{network_name}' in networks, but got: {backend_networks}"


def _assert_dind_service(services: dict, network_name: str) -> None:
    dind = services["dind"]
    dind_env = dind.get("environment", [])
    dind_volumes = dind.get("volumes", [])
    dind_networks = dind.get("networks", [])

    assert (
        dind["image"] in ["docker:dind", "docker:dind-rootless"]
    ), f"Expected dind image to be 'docker:dind' or 'docker:dind-rootless', but got: {dind.get('image')}"
    if dind["image"] == "docker:dind":
        assert (
            dind.get("privileged") is True
        ), f"Expected dind service to be privileged, but got: {dind.get('privileged')}"
    assert any(
        "DOCKER_TLS_CERTDIR=/certs" in item for item in dind_env
    ), f"Expected DOCKER_TLS_CERTDIR=/certs in environment, but got: {dind_env}"
    assert (
        "dind-certs:/certs/client" in dind_volumes
    ), f"Expected 'dind-certs:/certs/client' in volumes, but got: {dind_volumes}"
    assert (
        "dind-data:/var/lib/docker" in dind_volumes
    ), f"Expected 'dind-data:/var/lib/docker' in volumes, but got: {dind_volumes}"
    assert (
        network_name in dind_networks
    ), f"Expected '{network_name}' in networks, but got: {dind_networks}"


def test_local_compose_uses_dind_with_tls() -> None:
    data = _load_yaml("docker-compose.yml")
    services = data["services"]

    _assert_backend_uses_dind_tls(services, "mcp-gateway")
    _assert_dind_service(services, "mcp-gateway")

    dind_ports = services["dind"].get("ports", [])
    assert any("8080-8090:8080-8090" == item for item in dind_ports)


def test_e2e_compose_uses_dind_with_tls() -> None:
    data = _load_yaml("docker-compose.test.yml")
    services = data["services"]

    _assert_backend_uses_dind_tls(services, "mcp-gateway-test")
    _assert_dind_service(services, "mcp-gateway-test")

    dind_ports = services["dind"].get("ports", [])
    assert any("8080-8090:8080-8090" == item for item in dind_ports)


def test_prod_compose_uses_dind_with_tls() -> None:
    data = _load_yaml("docker-compose.prod.yml")
    services = data["services"]

    _assert_backend_uses_dind_tls(services, "mcp-network")
    _assert_dind_service(services, "mcp-network")

    dind_ports = services["dind"].get("ports", [])
    assert any("8080-8090:8080-8090" == item for item in dind_ports)

