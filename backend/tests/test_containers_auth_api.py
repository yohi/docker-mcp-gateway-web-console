"""Tests for container API authentication enforcement."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import get_auth_service, get_session_id

client = TestClient(app)

class TestContainerAuthAPI:
    """Test suite for container API authentication."""

    def setup_method(self):
        """Reset dependency overrides before each test."""
        app.dependency_overrides.clear()

    def test_list_containers_unauthorized(self):
        """Test listing containers with invalid session returns 401."""
        mock_auth_service = AsyncMock()
        mock_auth_service.get_session.return_value = None
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_session_id] = lambda: "invalid-session-id"
        
        response = client.get("/api/containers")
        assert response.status_code == 401
        assert "Invalid or expired session" in response.json()["detail"]

    def test_create_container_unauthorized(self):
        """Test creating container with invalid session returns 401."""
        mock_auth_service = AsyncMock()
        mock_auth_service.get_session.return_value = None
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_session_id] = lambda: "invalid-session-id"
        
        response = client.post(
            "/api/containers",
            json={
                "name": "test-container",
                "image": "hello-world"
            }
        )
        assert response.status_code == 401
        assert "Invalid or expired session" in response.json()["detail"]

    def test_container_actions_unauthorized(self):
        """Test container actions (start, stop, etc.) with invalid session return 401."""
        mock_auth_service = AsyncMock()
        mock_auth_service.get_session.return_value = None
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_session_id] = lambda: "invalid-session-id"
        
        endpoints = [
            ("POST", "/api/containers/test-id/start"),
            ("POST", "/api/containers/test-id/stop"),
            ("POST", "/api/containers/test-id/restart"),
            ("DELETE", "/api/containers/test-id"),
        ]
        
        for method, url in endpoints:
            if method == "POST":
                response = client.post(url)
            elif method == "DELETE":
                response = client.delete(url)
            
            assert response.status_code == 401, f"Endpoint {url} should require authentication"
            assert "Invalid or expired session" in response.json()["detail"]

    def test_get_config_unauthorized(self):
        """Test getting container config with invalid session returns 401."""
        mock_auth_service = AsyncMock()
        mock_auth_service.get_session.return_value = None
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_session_id] = lambda: "invalid-session-id"
        
        response = client.get("/api/containers/test-id/config")
        assert response.status_code == 401
        assert "Invalid or expired session" in response.json()["detail"]
