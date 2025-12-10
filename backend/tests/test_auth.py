"""Tests for authentication service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.auth import AuthMethod, LoginRequest
from app.services.auth import AuthError, AuthService
from app.services.state_store import StateStore


@pytest.fixture
def state_store(tmp_path) -> StateStore:
    """テスト用の一時 StateStore を返す。"""
    db_path = tmp_path / "auth.db"
    store = StateStore(str(db_path))
    store.init_schema()
    return store


@pytest.fixture
def auth_service(state_store: StateStore):
    """Create an AuthService instance for testing."""
    return AuthService(state_store=state_store)


@pytest.fixture
def mock_login_request():
    """Create a mock login request."""
    return LoginRequest(
        method=AuthMethod.MASTER_PASSWORD,
        email="test@example.com",
        master_password="test_password"
    )


class TestAuthService:
    """Test suite for AuthService."""

    @pytest.mark.asyncio
    async def test_login_creates_session(self, auth_service, mock_login_request):
        """Test that successful login creates a valid session."""
        # Mock the Bitwarden authentication
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "test_session_key"
            
            session = await auth_service.login(mock_login_request)
            
            # Verify session was created
            assert session.session_id is not None
            assert session.user_email == "test@example.com"
            assert session.bw_session_key == "test_session_key"
            assert session.created_at is not None
            assert session.expires_at > datetime.now(timezone.utc)
            
            # Verify session is stored
            assert session.session_id in auth_service._sessions

    @pytest.mark.asyncio
    async def test_login_with_invalid_credentials_raises_error(self, auth_service, mock_login_request):
        """Test that login with invalid credentials raises AuthError."""
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.side_effect = AuthError("Invalid credentials")
            
            with pytest.raises(AuthError):
                await auth_service.login(mock_login_request)

    @pytest.mark.asyncio
    async def test_validate_session_returns_true_for_valid_session(self, auth_service, mock_login_request):
        """Test that validate_session returns True for valid sessions."""
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "test_session_key"
            
            session = await auth_service.login(mock_login_request)
            
            # Validate the session
            is_valid = await auth_service.validate_session(session.session_id)
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_session_returns_false_for_invalid_session(self, auth_service):
        """Test that validate_session returns False for non-existent sessions."""
        is_valid = await auth_service.validate_session("non_existent_session")
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_session_expires_old_sessions(self, auth_service, mock_login_request):
        """Test that validate_session expires sessions past their timeout."""
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "test_session_key"
            
            session = await auth_service.login(mock_login_request)
            
            # Manually expire the session
            session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            
            # Validate should return False and clean up the session
            is_valid = await auth_service.validate_session(session.session_id)
            assert is_valid is False
            assert session.session_id not in auth_service._sessions

    @pytest.mark.asyncio
    async def test_logout_removes_session(self, auth_service, mock_login_request):
        """Test that logout removes the session."""
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "test_session_key"
            
            session = await auth_service.login(mock_login_request)
            
            # Mock the lock operation
            with patch.object(auth_service, '_lock_bitwarden', new_callable=AsyncMock):
                success = await auth_service.logout(session.session_id)
                
                assert success is True
                assert session.session_id not in auth_service._sessions

    @pytest.mark.asyncio
    async def test_logout_returns_false_for_invalid_session(self, auth_service):
        """Test that logout returns False for non-existent sessions."""
        with patch.object(auth_service, '_lock_bitwarden', new_callable=AsyncMock):
            success = await auth_service.logout("non_existent_session")
            assert success is False

    @pytest.mark.asyncio
    async def test_get_vault_access_returns_key_for_valid_session(self, auth_service, mock_login_request):
        """Test that get_vault_access returns the session key for valid sessions."""
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "test_session_key"
            
            session = await auth_service.login(mock_login_request)
            
            vault_access = await auth_service.get_vault_access(session.session_id)
            assert vault_access == "test_session_key"

    @pytest.mark.asyncio
    async def test_get_vault_access_returns_none_for_invalid_session(self, auth_service):
        """Test that get_vault_access returns None for invalid sessions."""
        vault_access = await auth_service.get_vault_access("non_existent_session")
        assert vault_access is None

    @pytest.mark.asyncio
    async def test_session_timeout_on_inactivity(self, auth_service, mock_login_request):
        """Test that sessions timeout after period of inactivity."""
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "test_session_key"
            
            session = await auth_service.login(mock_login_request)
            
            # Simulate inactivity by setting last_activity to past
            session.last_activity = datetime.now(timezone.utc) - timedelta(minutes=31)
            
            # Validate should return False due to inactivity
            is_valid = await auth_service.validate_session(session.session_id)
            assert is_valid is False
            assert session.session_id not in auth_service._sessions

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, auth_service, mock_login_request):
        """Test that cleanup_expired_sessions removes expired sessions."""
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "test_session_key"
            
            # Create multiple sessions
            session1 = await auth_service.login(mock_login_request)
            session2 = await auth_service.login(mock_login_request)
            
            # Expire one session
            session1.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            
            # Mock the lock operation
            with patch.object(auth_service, '_lock_bitwarden', new_callable=AsyncMock):
                cleaned = await auth_service.cleanup_expired_sessions()
                
                assert cleaned == 1
                assert session1.session_id not in auth_service._sessions
                assert session2.session_id in auth_service._sessions

    @pytest.mark.asyncio
    async def test_session_persisted_and_restored(self, state_store, mock_login_request):
        """永続化ストアからセッションが復元されることを検証する。"""
        service1 = AuthService(state_store=state_store)
        with patch.object(service1, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = "persisted_key"
            session = await service1.login(mock_login_request)

        service2 = AuthService(state_store=state_store)

        assert session.session_id in service2._sessions
        assert await service2.validate_session(session.session_id) is True
        assert await service2.get_vault_access(session.session_id) == "persisted_key"

    @pytest.mark.asyncio
    async def test_login_validates_credentials(self, auth_service):
        """Test that login validates credentials are provided for the method."""
        # API key method without api_key
        request = LoginRequest(
            method=AuthMethod.API_KEY,
            email="test@example.com"
        )
        
        with pytest.raises(AuthError, match="Client ID and Client Secret are required"):
            await auth_service.login(request)

        # API key method without master password
        request = LoginRequest(
            method=AuthMethod.API_KEY,
            email="test@example.com",
            client_id="test_id",
            client_secret="test_secret"
        )
        
        with pytest.raises(AuthError, match="Master password is required for api_key"):
            await auth_service.login(request)
        
        # Master password method without password
        request = LoginRequest(
            method=AuthMethod.MASTER_PASSWORD,
            email="test@example.com"
        )
        
        with pytest.raises(AuthError, match="Master password is required"):
            await auth_service.login(request)
