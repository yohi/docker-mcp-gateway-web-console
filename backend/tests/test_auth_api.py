"""Tests for authentication API endpoints."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.api.auth import get_auth_service
from app.models.auth import Session
from app.services.auth import AuthError

client = TestClient(app)


class TestAuthAPI:
    """Test suite for authentication API endpoints."""

    def test_login_success(self):
        """Test successful login returns session_id and expires_at."""
        mock_session = Session(
            session_id="test-session-id",
            user_email="test@example.com",
            bw_session_key="test-bw-key",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=30),
            last_activity=datetime.now()
        )
        
        mock_service = AsyncMock()
        mock_service.login.return_value = mock_session
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        try:
            response = client.post(
                "/api/auth/login",
                json={
                    "method": "master_password",
                    "email": "test@example.com",
                    "master_password": "test_password"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "session_id" in data
            assert "expires_at" in data
            assert data["session_id"] == "test-session-id"
        finally:
            app.dependency_overrides.clear()

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials returns 401."""
        mock_service = AsyncMock()
        mock_service.login.side_effect = AuthError("Invalid credentials")
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        try:
            response = client.post(
                "/api/auth/login",
                json={
                    "method": "master_password",
                    "email": "test@example.com",
                    "master_password": "wrong_password"
                }
            )
            
            assert response.status_code == 401
            assert "Invalid credentials" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_login_with_missing_credentials(self):
        """Test login with missing required fields returns 401."""
        mock_service = AsyncMock()
        mock_service.login.side_effect = AuthError("API key is required for api_key authentication method")
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        try:
            response = client.post(
                "/api/auth/login",
                json={
                    "method": "api_key",
                    "email": "test@example.com"
                    # Missing api_key
                }
            )
            
            # Should return 401 with validation error
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    def test_logout_success(self):
        """Test successful logout."""
        mock_service = AsyncMock()
        mock_service.logout.return_value = True
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        try:
            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": "Bearer test-session-id"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_logout_without_authorization_header(self):
        """Test logout without authorization header returns 401."""
        response = client.post("/api/auth/logout")
        
        assert response.status_code == 401
        assert "Missing authorization header" in response.json()["detail"]

    def test_logout_with_invalid_session(self):
        """Test logout with invalid session returns 404."""
        mock_service = AsyncMock()
        mock_service.logout.return_value = False
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        try:
            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": "Bearer invalid-session"}
            )
            
            assert response.status_code == 404
            assert "Session not found" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_validate_session_valid(self):
        """Test session validation for valid session."""
        mock_session = Session(
            session_id="test-session-id",
            user_email="test@example.com",
            bw_session_key="test-bw-key",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=30),
            last_activity=datetime.now()
        )
        
        mock_service = AsyncMock()
        mock_service.validate_session.return_value = True
        mock_service.get_session.return_value = mock_session
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        try:
            response = client.get(
                "/api/auth/session",
                headers={"Authorization": "Bearer test-session-id"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert "expires_at" in data
        finally:
            app.dependency_overrides.clear()

    def test_validate_session_invalid(self):
        """Test session validation for invalid session."""
        mock_service = AsyncMock()
        mock_service.validate_session.return_value = False
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        try:
            response = client.get(
                "/api/auth/session",
                headers={"Authorization": "Bearer invalid-session"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False
        finally:
            app.dependency_overrides.clear()

    def test_validate_session_without_authorization_header(self):
        """Test session validation without authorization header returns 401."""
        response = client.get("/api/auth/session")
        
        assert response.status_code == 401
        assert "Missing authorization header" in response.json()["detail"]

    def test_authorization_header_format_validation(self):
        """Test that invalid authorization header format is rejected."""
        # Missing Bearer prefix
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "test-session-id"}
        )
        assert response.status_code == 401
        assert "Invalid authorization header format" in response.json()["detail"]
        
        # Wrong prefix
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Basic test-session-id"}
        )
        assert response.status_code == 401
        assert "Invalid authorization header format" in response.json()["detail"]
