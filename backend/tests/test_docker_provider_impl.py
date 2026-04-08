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
    # DockerException with "timeout" should be normalized to DockerUnavailableError
    mock_container.start.side_effect = DockerException("Connection timeout")

    # Image check/pull は成功させる
    provider._call_docker_api = AsyncMock(return_value=None)
    config = ContainerConfig(name="test", image="alpine")
    
    with pytest.raises(DockerUnavailableError, match="Connection timeout"):
        await provider.create_container(config, "test", {})
    
    # container.remove(force=True) が呼ばれたことを確認
    # run_in_executor を経由するため、呼び出しを検証
    mock_container.remove.assert_called_once_with(force=True)

@pytest.mark.asyncio
async def test_create_container_connection_normalization(provider):
    """接続エラー時に DockerUnavailableError に正規化され、クライアントがリセットされることを検証する。"""
    mock_client = MagicMock()
    mock_container = MagicMock()
    
    # get_client と call_docker_api をモック
    provider._get_client = AsyncMock(return_value=mock_client)
    mock_client.containers.create.return_value = mock_container
    # start() 中に接続エラーが発生するシミュレーション
    mock_container.start.side_effect = DockerException("Connection timeout")
    
    # Image check は成功させる
    provider._call_docker_api = AsyncMock(return_value=None)
    config = ContainerConfig(name="test", image="alpine")
    
    # クライアントがセットされている状態から開始
    provider._client = mock_client
    
    with pytest.raises(DockerUnavailableError):
        await provider.create_container(config, "test", {})
    
    # クライアントが None にリセットされていることを確認
    assert provider._client is None
    # 補償削除が呼ばれていることを確認
    mock_container.remove.assert_called_once_with(force=True)
