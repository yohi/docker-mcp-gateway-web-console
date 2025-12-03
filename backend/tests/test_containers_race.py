"""Tests for container API race conditions."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.api.auth import get_auth_service

client = TestClient(app)

def test_create_container_session_race_condition():
    """
    Test that create_container handles the race condition where 
    validate_session returns True but get_session returns None.
    """
    # Mock AuthService
    mock_auth_service = AsyncMock()
    # validate_session returns True (session exists)
    mock_auth_service.validate_session.return_value = True
    # get_session returns None (session expired/removed just after validation)
    mock_auth_service.get_session.return_value = None
    
    # Override dependency
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
    
    try:
        response = client.post(
            "/api/containers",
            json={
                "name": "test-container",
                "image": "alpine:latest",
                "env_vars": {}
            },
            headers={"Authorization": "Bearer valid-session-id"}
        )
        
        # Without the fix, this would likely be 500 Internal Server Error
        # With the fix, it should be 401 Unauthorized or similar
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired session" in response.json()["detail"]
        
    finally:
        app.dependency_overrides.clear()
