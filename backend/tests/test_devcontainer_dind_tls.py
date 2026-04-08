"""Tests for devcontainer configuration (DinD and TLS settings)."""

import json
import yaml
from pathlib import Path

def test_devcontainer_json_structure():
    """Verify devcontainer.json uses correct docker-compose files."""
    root_dir = Path(__file__).parent.parent.parent
    devcontainer_json_path = root_dir / ".devcontainer" / "devcontainer.json"
    
    assert devcontainer_json_path.exists(), "devcontainer.json should exist"
    
    with open(devcontainer_json_path, "r") as f:
        # devcontainer.json can contain comments, so we use a simple parser or strip them
        content = f.read()
        # Strip simple // comments
        lines = [line for line in content.splitlines() if not line.strip().startswith("//")]
        data = json.loads("\n".join(lines))
        
    assert "dockerComposeFile" in data
    assert "../docker-compose.yml" in data["dockerComposeFile"]
    assert "docker-compose.devcontainer.yml" in data["dockerComposeFile"]
    assert data["service"] == "workspace"

def test_docker_compose_devcontainer_dind_settings():
    """Verify docker-compose.devcontainer.yml implements DinD with TLS."""
    root_dir = Path(__file__).parent.parent.parent
    compose_path = root_dir / ".devcontainer" / "docker-compose.devcontainer.yml"
    
    assert compose_path.exists(), "docker-compose.devcontainer.yml should exist"
    
    with open(compose_path, "r") as f:
        data = yaml.safe_load(f)
        
    workspace_service = data.get("services", {}).get("workspace", {})
    env = workspace_service.get("environment", [])
    
    # Convert list of "KEY=VALUE" to dict
    env_dict = {}
    for item in env:
        if "=" in item:
            k, v = item.split("=", 1)
            env_dict[k] = v
        else:
            env_dict[item] = True
            
    # Check for DinD network settings instead of socket
    assert env_dict.get("DOCKER_HOST") == "tcp://dind:2376", "Workspace should use DinD over TCP"
    assert env_dict.get("DOCKER_TLS_VERIFY") == "1", "Workspace should use TLS for Docker"
    assert env_dict.get("DOCKER_CERT_PATH") == "/certs/client", "Workspace should have DOCKER_CERT_PATH"

def test_docker_compose_backend_tls_env_support():
    """Verify backend service in devcontainer supports Docker TLS env vars."""
    root_dir = Path(__file__).parent.parent.parent
    compose_path = root_dir / ".devcontainer" / "docker-compose.devcontainer.yml"
    
    assert compose_path.exists(), "docker-compose.devcontainer.yml should exist"
    
    with open(compose_path, "r") as f:
        data = yaml.safe_load(f)
        
    backend_service = data.get("services", {}).get("backend", {})
    env = backend_service.get("environment", [])
    
    env_dict = {}
    for item in env:
        if "=" in item:
            k, v = item.split("=", 1)
            env_dict[k] = v
            
    assert env_dict.get("DOCKER_HOST") == "tcp://dind:2376", "Backend should use DinD over TCP"
    assert env_dict.get("DOCKER_TLS_VERIFY") == "1", "Backend should use TLS for Docker"
