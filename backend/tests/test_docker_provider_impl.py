import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.docker_provider import DockerSdkProvider, DockerUnavailableError
from backend.app.models.containers import ContainerConfig
from docker.errors import DockerException

@pytest.fixture
def provider():
    return DockerSdkProvider(base_url="unix:///var/run/docker.sock")

@pytest.mark.asyncio
async def test_call_docker_api_normalization(provider):
    """APIエラーが DockerUnavailableError に正規化されるか検証する。"""
    mock_func = MagicMock(side_effect=DockerException("Connection refused"))
    
    # _get_client をモックして有効なクライアントがある状態にする
    provider._client = MagicMock()
    
    with pytest.raises(DockerUnavailableError):
        await provider._call_docker_api(mock_func)
    
    # エラー後はクライアントキャッシュがクリアされていること
    assert provider._client is None

@pytest.mark.asyncio
async def test_container_summary_mapping(provider):
    """Docker APIのレスポンスが ContainerInfo に正しく変換されるか検証する。"""
    summary = {
        "Id": "abc123456789",
        "Names": ["/test-container"],
        "Image": "alpine:latest",
        "State": "running",
        "Created": 1712476800,
        "Ports": [{"PrivatePort": 80, "PublicPort": 8080}],
        "Labels": {"mcp.type": "server"}
    }
    
    info = provider._container_summary_to_info(summary)
    
    assert info.id == "abc123456789"
    assert info.name == "test-container"
    assert info.image == "alpine:latest"
    assert info.status == "running"
    assert info.ports == {"80": 8080}
    assert info.labels["mcp.type"] == "server"

@pytest.mark.asyncio
async def test_create_container_compensation_logic(provider):
    """start() 失敗時にコンテナが削除される補償トランザクションを検証する。"""
    mock_client = MagicMock()
    mock_container = MagicMock()
    
    # get_client と call_docker_api をモック
    provider._get_client = AsyncMock(return_value=mock_client)
    
    # containers.create は成功するが start は失敗する設定
    mock_client.containers.create.return_value = mock_container
    
    # 最初の call_docker_api (pull/get image) は成功
    # 2回目 (containers.create) も成功
    # 3回目 (container.start) は失敗させる
    async def side_effect(func, *args, **kwargs):
        if func == mock_container.start:
            raise Exception("Start failed")
        return func(*args, **kwargs)
    
    provider._call_docker_api = AsyncMock(side_effect=side_effect)
    
    config = ContainerConfig(name="test", image="alpine")
    
    with pytest.raises(Exception, match="Start failed"):
        await provider.create_container(config, "test", {})
    
    # container.remove(force=True) が呼ばれたことを確認
    # run_in_executor を経由するため、呼び出しを検証
    mock_container.remove.assert_called_once_with(force=True)
