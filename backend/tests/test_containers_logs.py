
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.services.containers import ContainerService, LogEntry
from app.services.secrets import SecretManager

class TestContainerLogs:
    @pytest.fixture
    def container_service(self):
        secret_manager = MagicMock(spec=SecretManager)
        service = ContainerService(secret_manager)
        # Mock the client to avoid actual Docker connection
        service._client = MagicMock()
        return service

    @pytest.mark.asyncio
    async def test_stream_logs_demux(self, container_service):
        container_id = "test-container"
        mock_container = MagicMock()
        container_service._client.containers.get.return_value = mock_container

        # Prepare the mock log data
        # Docker SDK with demux=True yields tuples of (stdout, stderr)
        # Timestamps are included because timestamps=True
        log_data = [
            (b"2024-01-01T10:00:00.000000000Z stdout message\n", None),
            (None, b"2024-01-01T10:00:01.000000000Z stderr message\n"),
            (b"simple message without timestamp\n", None),
            (None, None), # Should be skipped
        ]
        
        # container.logs returns an iterator
        mock_container.logs.return_value = iter(log_data)

        # Collect results
        entries = []
        async for entry in container_service.stream_logs(container_id):
            entries.append(entry)

        # Verify results
        assert len(entries) == 3
        
        # Entry 1: stdout
        assert entries[0].stream == "stdout"
        assert entries[0].message == "stdout message"
        # Verify timestamp parsing (ignoring timezone details for simplicity or checking basic correctness)
        assert entries[0].timestamp.year == 2024
        assert entries[0].timestamp.hour == 10

        # Entry 2: stderr
        assert entries[1].stream == "stderr"
        assert entries[1].message == "stderr message"
        assert entries[1].timestamp.second == 1

        # Entry 3: stdout fallback (no timestamp parsing)
        assert entries[2].stream == "stdout"
        assert entries[2].message == "simple message without timestamp"
        # Timestamp should be roughly "now", so we just check it's a datetime
        assert isinstance(entries[2].timestamp, datetime)

        # Verify container.logs was called with correct arguments
        mock_container.logs.assert_called_once()
        call_kwargs = mock_container.logs.call_args[1]
        assert call_kwargs['demux'] is True
        assert call_kwargs['stdout'] is True
        assert call_kwargs['stderr'] is True
        assert call_kwargs['timestamps'] is True
