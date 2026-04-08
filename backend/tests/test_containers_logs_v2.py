"""Tests for container log streaming in the new architecture."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.containers import ContainerService
from app.models.containers import LogEntry
from app.services.base import ContainerProvider
from app.services.secrets import SecretManager

class TestContainerLogsV2:
    @pytest.fixture
    def container_service(self):
        provider = MagicMock(spec=ContainerProvider)
        secret_manager = MagicMock(spec=SecretManager)
        auth_service = MagicMock()
        service = ContainerService(provider, secret_manager, auth_service)
        return service

    @pytest.mark.asyncio
    async def test_stream_logs_success(self, container_service):
        """Verify stream_logs correctly delegates to provider and yields entries."""
        container_id = "test-container"
        
        # Mock provider.stream_logs to be an async generator
        async def mock_log_generator(cid, follow, tail):
            yield LogEntry(
                timestamp=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
                message="stdout message",
                stream="stdout"
            )
            yield LogEntry(
                timestamp=datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
                message="stderr message",
                stream="stderr"
            )

        container_service.provider.stream_logs = mock_log_generator

        # Collect results
        entries = []
        async for entry in container_service.stream_logs(container_id):
            entries.append(entry)

        # Verify results
        assert len(entries) == 2
        assert entries[0].message == "stdout message"
        assert entries[0].stream == "stdout"
        assert entries[1].message == "stderr message"
        assert entries[1].stream == "stderr"

    @pytest.mark.asyncio
    async def test_stream_logs_error(self, container_service):
        """Verify stream_logs raises ContainerError when provider fails."""
        container_id = "test-container"
        
        async def error_generator(cid, follow, tail):
            raise Exception("Provider failure")
            yield # Needed for async generator

        container_service.provider.stream_logs = error_generator

        from app.services.containers import ContainerError
        with pytest.raises(ContainerError) as excinfo:
            async for _ in container_service.stream_logs(container_id):
                pass
        
        assert "Failed to stream logs" in str(excinfo.value)
