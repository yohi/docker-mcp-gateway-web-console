"""Property-based tests for authentication service."""

import pytest
from hypothesis import given, strategies as st
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.auth import AuthMethod, LoginRequest
from app.services.auth import AuthError, AuthService

@pytest.fixture
def auth_service():
    """Create an AuthService instance for testing."""
    # Kept for compatibility if needed, but not used in property tests anymore.
    return AuthService()

class TestAuthProperties:
    """Property-based tests for AuthService."""

    @given(
        email=st.emails(),
        password=st.text(min_size=1),
        session_key=st.text(min_size=10)
    )
    @pytest.mark.asyncio
    async def test_session_establishment_property(self, email, password, session_key):
        """
        **Feature: docker-mcp-gateway-console, Property 1: 認証成功時のセッション確立**
        
        For any valid Bitwarden credentials, if authentication succeeds,
        the system should return a valid session ID and vault access rights.
        """
        auth_service = AuthService()

        # Valid login request
        login_request = LoginRequest(
            method=AuthMethod.MASTER_PASSWORD,
            email=email,
            master_password=password
        )
        
        normalized_email = login_request.email

        # Mock successful authentication
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = session_key

            session = await auth_service.login(login_request)

            # Property verification
            assert session.session_id is not None
            # Pydantic EmailStr normalizes email (lowercase, punycode etc.)
            assert session.user_email == normalized_email
            assert session.bw_session_key == session_key
            assert session.created_at is not None
            assert session.expires_at > datetime.now()
            
            # Verify session is valid and stored
            assert await auth_service.validate_session(session.session_id) is True
            assert await auth_service.get_vault_access(session.session_id) == session_key

    @given(
        email=st.emails(),
        password=st.text(min_size=1)
    )
    @pytest.mark.asyncio
    async def test_auth_failure_property(self, email, password):
        """
        **Feature: docker-mcp-gateway-console, Property 2: 認証失敗時のセッション非確立**
        
        For any invalid Bitwarden credentials, if authentication fails,
        the system should NOT establish a session and should raise an error.
        """
        auth_service = AuthService()

        login_request = LoginRequest(
            method=AuthMethod.MASTER_PASSWORD,
            email=email,
            master_password=password
        )

        # Mock failed authentication
        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.side_effect = AuthError("Authentication failed")

            # Expect AuthError
            with pytest.raises(AuthError):
                await auth_service.login(login_request)

            # Verify NO session was created (internal state check)
            assert len(auth_service._sessions) == 0

    @given(
        email=st.emails(),
        password=st.text(min_size=1),
        session_key=st.text(min_size=10)
    )
    @pytest.mark.asyncio
    async def test_session_timeout_property(self, email, password, session_key):
        """
        **Feature: docker-mcp-gateway-console, Property 3: セッションタイムアウト**
        
        For any session, if the time since last activity exceeds the timeout period,
        the session should be invalidated.
        """
        auth_service = AuthService()

        login_request = LoginRequest(
            method=AuthMethod.MASTER_PASSWORD,
            email=email,
            master_password=password
        )

        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = session_key
            session = await auth_service.login(login_request)
            
            # Simulate timeout by modifying last_activity
            # Setting it to (timeout + 1 second) ago
            timeout = auth_service._session_timeout
            session.last_activity = datetime.now() - timeout - timedelta(seconds=1)

            # Mock lock (for logout)
            with patch.object(auth_service, '_lock_bitwarden', new_callable=AsyncMock):
                is_valid = await auth_service.validate_session(session.session_id)
                assert is_valid is False
                
                # Verify session is removed
                assert session.session_id not in auth_service._sessions

    @given(
        email=st.emails(),
        password=st.text(min_size=1),
        session_key=st.text(min_size=10)
    )
    @pytest.mark.asyncio
    async def test_logout_property(self, email, password, session_key):
        """
        **Feature: docker-mcp-gateway-console, Property 4: ログアウト時のセッション終了**
        
        For any active session, if logout is executed,
        the session should be immediately invalidated and vault access revoked.
        """
        auth_service = AuthService()

        login_request = LoginRequest(
            method=AuthMethod.MASTER_PASSWORD,
            email=email,
            master_password=password
        )

        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = session_key
            session = await auth_service.login(login_request)
            
            # Mock lock
            with patch.object(auth_service, '_lock_bitwarden', new_callable=AsyncMock) as mock_lock:
                success = await auth_service.logout(session.session_id)
                
                assert success is True
                assert session.session_id not in auth_service._sessions
                
                # Verify lock was called
                mock_lock.assert_called_with(session_key)

    @given(
        email=st.emails(),
        password=st.text(min_size=1),
        session_key=st.text(min_size=10)
    )
    @pytest.mark.asyncio
    async def test_cache_clear_property(self, email, password, session_key):
        """
        **Feature: docker-mcp-gateway-console, Property 24: セッション終了時のキャッシュクリア**
        
        For any session, when it ends (logout or timeout),
        all associated cached secrets MUST be destroyed.
        """
        # We need to inject a mock callback/observer to verify cache clearing
        # Since AuthService doesn't support it yet, this test drives the implementation.
        
        mock_cleanup = MagicMock()
        auth_service = AuthService(on_session_end=mock_cleanup)
        
        login_request = LoginRequest(
            method=AuthMethod.MASTER_PASSWORD,
            email=email,
            master_password=password
        )

        with patch.object(auth_service, '_authenticate_bitwarden', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = session_key
            session = await auth_service.login(login_request)
            
            # 1. Test Explicit Logout
            with patch.object(auth_service, '_lock_bitwarden', new_callable=AsyncMock):
                await auth_service.logout(session.session_id)
                
                # Verify cleanup called with session_id
                mock_cleanup.assert_called_with(session.session_id)
            
            # Reset for timeout test
            mock_cleanup.reset_mock()
            session = await auth_service.login(login_request)
            
            # 2. Test Timeout
            timeout = auth_service._session_timeout
            session.last_activity = datetime.now() - timeout - timedelta(seconds=1)
            
            with patch.object(auth_service, '_lock_bitwarden', new_callable=AsyncMock):
                await auth_service.validate_session(session.session_id)
                
                # Verify cleanup called
                mock_cleanup.assert_called_with(session.session_id)