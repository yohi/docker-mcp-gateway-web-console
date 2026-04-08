"""Tests for container operation race conditions."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import status
from app.main import app
from app.api.auth import get_auth_service, get_session_id
from app.services.containers import ContainerAlreadyExistsError, ContainerService
from app.api.containers import get_container_service

client = TestClient(app)

class TestContainerRaceV2:
    """Test suite for container operation race conditions."""

    def setup_method(self):
        """Reset dependency overrides before each test."""
        app.dependency_overrides.clear()

    def test_create_container_already_exists_race(self):
        """Test that creating a container that already exists (race condition) returns 409."""
        mock_auth_service = AsyncMock()
        mock_auth_service.validate_session.return_value = True
        mock_auth_service.get_session.return_value = MagicMock(bw_session_key="test-key")
        
        mock_container_service = AsyncMock(spec=ContainerService)
        mock_container_service.create_container.side_effect = ContainerAlreadyExistsError(
            name="existing-container",
            container_id="some-id",
            status="running"
        )
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_session_id] = lambda: "valid-session-id"
        app.dependency_overrides[get_container_service] = lambda: mock_container_service
        
        response = client.post(
            "/api/containers",
            json={
                "name": "existing-container",
                "image": "hello-world"
            }
        )
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "コンテナ名 existing-container は既に使用されています" in response.json()["detail"]

    def test_list_containers_unavailable_race(self):
        """Test that list_containers handles Docker unavailability gracefully."""
        from app.services.containers import ContainerUnavailableError
        
        mock_auth_service = AsyncMock()
        mock_auth_service.validate_session.return_value = True
        
        mock_container_service = AsyncMock(spec=ContainerService)
        mock_container_service.list_containers.side_effect = ContainerUnavailableError(
            attempted_hosts=["unix:///var/run/docker.sock"],
            errors=["Permission denied"]
        )
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_session_id] = lambda: "valid-session-id"
        app.dependency_overrides[get_container_service] = lambda: mock_container_service
        
        response = client.get("/api/containers")
        
        # It should return a warning message but status 200 (as per current implementation)
        assert response.status_code == 200
        assert "Docker デーモンに接続できない" in response.json()["warning"]
