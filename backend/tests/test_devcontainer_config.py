import yaml
from pathlib import Path

def test_devcontainer_dind_tls_config():
    """devcontainer.json と docker-compose.devcontainer.yml の DinD/TLS 設定を検証する。"""
    root_dir = Path(__file__).parent.parent.parent
    
    # 1. docker-compose.devcontainer.yml の検証
    compose_path = root_dir / ".devcontainer" / "docker-compose.devcontainer.yml"
    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)
    
    # version キーが削除されていることを確認
    assert "version" not in compose
    
    services = compose.get("services", {})
    assert "dind" in services
    assert services["dind"]["image"] == "docker:dind"
    assert services["dind"]["privileged"] is True
    
    # workspace/backend が dind を参照しているか確認
    for svc_name in ["workspace", "backend"]:
        svc = services.get(svc_name, {})
        env = {}
        raw_env = svc.get("environment", [])
        if isinstance(raw_env, dict):
            for key, value in raw_env.items():
                env[key] = str(value) if value is not None else ""
        elif isinstance(raw_env, list):
            for item in raw_env:
                if isinstance(item, str) and "=" in item:
                    key, value = item.split("=", 1)
                    env[key] = value
                elif isinstance(item, str):
                    env[item] = ""
        
        assert env.get("DOCKER_HOST") == "tcp://dind:2376"
        assert env.get("DOCKER_TLS_VERIFY") == "1"
        assert env.get("DOCKER_CERT_PATH") == "/certs/client"

    # 2. devcontainer.json の検証
    import json
    devcontainer_path = root_dir / ".devcontainer" / "devcontainer.json"
    with open(devcontainer_path, "r", encoding="utf-8") as f:
        devcontainer = json.load(f)
    
    remote_env = devcontainer.get("remoteEnv", {})
    assert remote_env.get("DOCKER_HOST") == "tcp://dind:2376"
    assert remote_env.get("DOCKER_TLS_VERIFY") == "1"
    assert remote_env.get("DOCKER_CERT_PATH") == "/certs/client"
