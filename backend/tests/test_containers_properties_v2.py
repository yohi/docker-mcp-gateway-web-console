"""Tests for container properties reporting in the new architecture."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from app.services.containers import ContainerService
from app.models.containers import ContainerInfo
from app.services.base import ContainerProvider
from app.services.secrets import SecretManager

class TestContainerPropertiesV2:
    @pytest.fixture
    def container_service(self):
        provider = MagicMock(spec=ContainerProvider)
        secret_manager = MagicMock(spec=SecretManager)
        auth_service = MagicMock()
        service = ContainerService(provider, secret_manager, auth_service)
        return service

    @pytest.mark.asyncio
    async def test_list_containers_properties(self, container_service):
        """Verify list_containers returns correct container properties from provider."""
        mock_containers = [
            ContainerInfo(
                id="id1",
                name="container1",
                image="image1:latest",
                status="running",
                created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                ports={"80/tcp": 8080},
                labels={"label1": "val1"}
            ),
            ContainerInfo(
                id="id2",
                name="container2",
                image="image2:latest",
                status="stopped",
                created_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
                ports={},
                labels={}
            )
        ]
        
        container_service.provider.list_containers = AsyncMock(return_value=mock_containers)

        results = await container_service.list_containers(all_containers=True)

        assert len(results) == 2
        assert results[0].id == "id1"
        assert results[0].status == "running"
        assert results[0].ports["80/tcp"] == 8080
        assert results[1].id == "id2"
        assert results[1].status == "stopped"

    @pytest.mark.asyncio
    async def test_get_container_config_not_found(self, container_service):
        """Verify get_container_config raises ContainerError when not in state store."""
        from app.services.containers import ContainerError
        container_service._state_store.get_container_config = MagicMock(return_value=None)
        
        with pytest.raises(ContainerError) as excinfo:
            container_service.get_container_config("non-existent-id")
        
        assert "コンテナ設定が保存されていません" in str(excinfo.value)
