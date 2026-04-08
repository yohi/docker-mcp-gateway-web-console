import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from app.services.docker_provider import (
    DockerSdkProvider, 
    DockerUnavailableError, 
    _parse_version_triplet
)
from docker.errors import DockerException

def test_parse_version_triplet():
    assert _parse_version_triplet("1.41.0") == (1, 41, 0)
    assert _parse_version_triplet("7.1") == (7, 1, 0)
    assert _parse_version_triplet("  2.32.1  ") == (2, 32, 1)
    assert _parse_version_triplet("invalid") is None

def test_container_summary_to_info_minimal():
    provider = DockerSdkProvider(base_url="unix:///var/run/docker.sock")
    summary = {
        "Id": "123",
        "Image": "alpine",
        "State": "exited",
    }
    info = provider._container_summary_to_info(summary)
    assert info.id == "123"
    assert info.name == "123"
    assert info.status == "stopped"
    assert isinstance(info.created_at, datetime)

def test_container_summary_to_info_status_mappings():
    provider = DockerSdkProvider(base_url="unix:///var/run/docker.sock")
    
    # マッピングのテストケース
    test_cases = [
        ("running", "running"),
        ("exited", "stopped"),
        ("created", "stopped"),
        ("paused", "stopped"),
        ("removing", "error"),
        ("dead", "error"),
        ("restarting", "error"),
        ("", "error"),
        (None, "error"),
    ]
    
    for state, expected_status in test_cases:
        summary = {"Id": "123", "State": state}
        info = provider._container_summary_to_info(summary)
        assert info.status == expected_status, f"State '{state}' should map to '{expected_status}'"

@pytest.mark.asyncio
async def test_get_client_caching_and_throttle():
    provider = DockerSdkProvider(base_url="http://invalid:2375")
    
    # time.monotonic() をモックしてスロットリング挙動を安定化させる
    # 呼び出し回数に依存しないよう、現在の時刻を保持する状態オブジェクトを使用
    class MockTime:
        def __init__(self):
            self.now = 100.0
        def __call__(self, *args, **kwargs):
            return self.now
            
    mock_time = MockTime()
    
    with patch("time.monotonic", side_effect=mock_time):
        # 最初の失敗 (DockerExceptionを投げる必要がある)
        with patch("docker.DockerClient", side_effect=DockerException("First failure")):
            with pytest.raises(DockerUnavailableError):
                await provider._get_client()
        
        first_error = provider._last_error
        assert first_error is not None
        
        # 時間を2秒進める (5秒以内)
        mock_time.now = 102.0
        
        # 5秒以内の再試行 (102.0 - 100.0 = 2.0 < 5) は即座に同じエラーを投げる
        with patch("docker.DockerClient") as mock_client:
            with pytest.raises(DockerUnavailableError) as excinfo:
                await provider._get_client()
            assert excinfo.value is first_error
            mock_client.assert_not_called()

@pytest.mark.asyncio
async def test_stream_logs_parsing():
    provider = DockerSdkProvider(base_url="unix:///var/run/docker.sock")
    mock_client = MagicMock()
    provider._client = mock_client
    
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container
    
    # logs() はジェネレータを返す
    log_data = [
        (b"2024-04-08T12:00:00.000000000Z Hello stdout\n", None),
        (None, b"2024-04-08T12:00:01.000000000Z Hello stderr\n"),
        (b"invalid_timestamp No space", None),
    ]
    mock_container.logs.return_value = iter(log_data)
    
    logs = []
    async for entry in provider.stream_logs("cont_id", follow=False):
        logs.append(entry)
        
    assert len(logs) == 3
    assert logs[0].message == "Hello stdout"
    assert logs[0].stream == "stdout"
    assert logs[0].timestamp == datetime.fromisoformat("2024-04-08T12:00:00.000000+00:00")
    
    assert logs[1].message == "Hello stderr"
    assert logs[1].stream == "stderr"
    
    assert logs[2].message == "invalid_timestamp No space"
    assert isinstance(logs[2].timestamp, datetime)

@pytest.mark.asyncio
async def test_exec_command_success():
    provider = DockerSdkProvider(base_url="unix:///var/run/docker.sock")
    mock_client = MagicMock()
    provider._client = mock_client
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container
    
    mock_container.exec_run.return_value = (0, b"success output")
    
    exit_code, output = await provider.exec_command("cont_id", ["ls"])
    assert exit_code == 0
    assert output == b"success output"

@pytest.mark.asyncio
async def test_call_docker_api_connection_error_handling():
    provider = DockerSdkProvider(base_url="unix:///var/run/docker.sock")
    provider._client = MagicMock()
    
    from requests.exceptions import ConnectionError as RequestsConnectionError
    
    mock_func = MagicMock(side_effect=RequestsConnectionError("Connection lost"))
    
    with pytest.raises(DockerUnavailableError):
        await provider._call_docker_api(mock_func)
    
    assert provider._client is None
