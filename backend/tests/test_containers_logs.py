from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.containers import LogEntry
from app.services.auth import AuthService
from app.services.base import ContainerProvider
from app.services.containers import ContainerService
from app.services.secrets import SecretManager


class TestContainerLogs:
    @pytest.fixture
    def container_service(self) -> ContainerService:
        provider = AsyncMock(spec=ContainerProvider)
        secret_manager = AsyncMock(spec=SecretManager)
        auth_service = AsyncMock(spec=AuthService)
        return ContainerService(provider, secret_manager, auth_service)

    @pytest.mark.asyncio
    async def test_stream_logs_yields_provider_entries(
        self, container_service: ContainerService
    ) -> None:
        entries = [
            LogEntry(
                timestamp=datetime(2024, 1, 1, 10, 0, 0),
                message="stdout message",
                stream="stdout",
            ),
            LogEntry(
                timestamp=datetime(2024, 1, 1, 10, 0, 1),
                message="stderr message",
                stream="stderr",
            ),
        ]

        async def stream():
            for entry in entries:
                yield entry

        container_service.provider.stream_logs = MagicMock(return_value=stream())

        result = []
        async for entry in container_service.stream_logs("test-container"):
            result.append(entry)

        assert result == entries
        container_service.provider.stream_logs.assert_called_once_with(
            "test-container", True, 100
        )
