"""Authentication Service for Bitwarden integration."""

import asyncio
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

from ..config import settings
from ..models.auth import AuthMethod, LoginRequest, Session

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Custom exception for authentication errors."""
    pass


class AuthService:
    """
    Manages Bitwarden authentication and session lifecycle.
    
    Responsibilities:
    - Authenticate users via Bitwarden (API key or master password)
    - Create and manage sessions
    - Handle session timeouts
    - Provide vault access through session keys
    """

    def __init__(self, on_session_end: Optional['Callable[[str], None]'] = None):
        """
        Initialize the Auth Service.
        
        Args:
            on_session_end: Optional callback function to be called when a session ends.
                           Receives session_id as argument.
        """
        # In-memory session storage: {session_id: Session}
        self._sessions: Dict[str, Session] = {}
        self._session_timeout = timedelta(minutes=settings.session_timeout_minutes)
        self._on_session_end = on_session_end

    async def login(self, login_request: LoginRequest) -> Session:
        """
        Authenticate user with Bitwarden and create a session.
        
        Args:
            login_request: Login credentials and method
            
        Returns:
            Session object with session_id and bw_session_key
            
        Raises:
            AuthError: If authentication fails
        """
        # Validate credentials are provided for the method
        try:
            login_request.validate_credentials()
        except ValueError as e:
            raise AuthError(str(e)) from e
        
        # Authenticate with Bitwarden
        bw_session_key = await self._authenticate_bitwarden(login_request)
        
        # Create session
        session_id = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + self._session_timeout
        
        session = Session(
            session_id=session_id,
            user_email=login_request.email,
            bw_session_key=bw_session_key,
            created_at=now,
            expires_at=expires_at,
            last_activity=now
        )
        
        # Store session
        self._sessions[session_id] = session
        
        logger.info(f"Session created for user {login_request.email}: {session_id}")
        
        return session

    async def logout(self, session_id: str) -> bool:
        """
        Terminate a session and revoke vault access.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was successfully terminated, False if session not found
        """
        if session_id not in self._sessions:
            logger.warning(f"Logout attempted for non-existent session: {session_id}")
            return False
        
        session = self._sessions[session_id]
        
        # Lock the Bitwarden vault for this session
        await self._lock_bitwarden(session.bw_session_key)
        
        # Remove session from storage
        del self._sessions[session_id]
        
        # Trigger session end callback if provided
        if self._on_session_end:
            try:
                self._on_session_end(session_id)
            except Exception as e:
                logger.error(f"Error in session end callback for {session_id}: {e}")
        
        logger.info(f"Session terminated: {session_id}")
        
        return True

    async def validate_session(self, session_id: str) -> bool:
        """
        Check if a session is valid and not expired.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session is valid, False otherwise
        """
        if session_id not in self._sessions:
            return False
        
        session = self._sessions[session_id]
        now = datetime.now()
        
        # Check if session has expired
        if now >= session.expires_at:
            logger.info(f"Session expired: {session_id}")
            # Clean up expired session
            await self.logout(session_id)
            return False
        
        # Check for inactivity timeout
        time_since_activity = now - session.last_activity
        if time_since_activity >= self._session_timeout:
            logger.info(f"Session timed out due to inactivity: {session_id}")
            await self.logout(session_id)
            return False
        
        # Update last activity time
        session.last_activity = now
        
        return True

    async def get_vault_access(self, session_id: str) -> Optional[str]:
        """
        Get Bitwarden vault access key for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Bitwarden session key if session is valid, None otherwise
        """
        if not await self.validate_session(session_id):
            return None
        
        session = self._sessions[session_id]
        return session.bw_session_key

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session object if found and valid, None otherwise
        """
        if not await self.validate_session(session_id):
            return None
        
        return self._sessions.get(session_id)

    async def cleanup_expired_sessions(self) -> int:
        """
        Remove all expired sessions from storage.
        
        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in self._sessions.items():
            if now >= session.expires_at or (now - session.last_activity) >= self._session_timeout:
                expired_sessions.append(session_id)
        
        # Clean up expired sessions
        for session_id in expired_sessions:
            await self.logout(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)

    async def _authenticate_bitwarden(self, login_request: LoginRequest) -> str:
        """
        Authenticate with Bitwarden CLI and obtain session key.
        
        Args:
            login_request: Login credentials
            
        Returns:
            Bitwarden session key
            
        Raises:
            AuthError: If authentication fails
        """
        process = None
        try:
            if login_request.method == AuthMethod.API_KEY:
                # Authenticate using API key
                bw_session_key = await self._login_with_api_key(
                    login_request.client_id,
                    login_request.client_secret,
                    login_request.master_password
                )
            else:
                # Authenticate using master password
                bw_session_key = await self._login_with_password(
                    login_request.email,
                    login_request.master_password,
                    login_request.two_step_login_method,
                    login_request.two_step_login_code
                )
            
            # Verify the session key works by unlocking the vault
            await self._verify_session_key(bw_session_key)
            
            return bw_session_key
            
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"Bitwarden authentication failed: {e}")
            raise AuthError(f"Authentication failed: {str(e)}") from e

    async def _login_with_api_key(self, client_id: str, client_secret: str, master_password: str) -> str:
        """
        Login to Bitwarden using API key (Client ID & Secret).
        This method bypasses 2FA but requires Master Password to unlock the vault.
        
        Args:
            client_id: Bitwarden Client ID
            client_secret: Bitwarden Client Secret
            master_password: Master Password (for unlocking)
            
        Returns:
            Bitwarden session key
            
        Raises:
            AuthError: If login or unlock fails
        """
        process = None
        try:
            # Set API key as environment variable and login
            cmd = [settings.bitwarden_cli_path, "login", "--apikey"]
            
            # Use os.environ as base to keep PATH etc, but update with API keys
            env = os.environ.copy()
            env["BW_CLIENTID"] = client_id
            env["BW_CLIENTSECRET"] = client_secret
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Wait for process with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.bitwarden_cli_timeout_seconds
                )
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                raise AuthError("Bitwarden login timed out")
            
            if process.returncode != 0:
                stdout_msg = stdout.decode().strip()
                stderr_msg = stderr.decode().strip()
                combined = f"{stdout_msg}\n{stderr_msg}".strip()
                if "You are already logged in" not in combined:
                    raise AuthError(f"Bitwarden login failed: {combined}")
            
            # For API key login, we must unlock the vault to get the session key
            return await self._unlock_vault(master_password)
            
        except asyncio.TimeoutError:
            raise AuthError("Bitwarden login timed out")
        except Exception as e:
            if isinstance(e, AuthError):
                raise
            raise AuthError(f"API key login failed: {str(e)}") from e
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass

    async def _login_with_password(
        self,
        email: str,
        password: str,
        two_step_method: Optional[int] = None,
        two_step_code: Optional[str] = None
    ) -> str:
        """
        Login to Bitwarden using master password.
        
        Args:
            email: User email
            password: Master password
            two_step_method: Optional 2FA method enum value
            two_step_code: Optional 2FA code
            
        Returns:
            Bitwarden session key
            
        Raises:
            AuthError: If login fails
        """
        process = None
        try:
            # Login with master password
            cmd = [settings.bitwarden_cli_path, "login", email, "--raw"]
            
            # Add 2FA parameters if provided
            if two_step_method is not None and two_step_code:
                cmd.extend(["--method", str(two_step_method), "--code", two_step_code])
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Send password to stdin
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=password.encode()),
                    timeout=settings.bitwarden_cli_timeout_seconds
                )
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                raise AuthError("Bitwarden login timed out")
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                # Common error messages
                if "Invalid credentials" in error_msg or "Username or password is incorrect" in error_msg:
                    raise AuthError("Invalid email or password")
                raise AuthError(f"Bitwarden login failed: {error_msg}")
            
            # Session key is returned in stdout
            session_key = stdout.decode().strip()
            
            if not session_key:
                raise AuthError("No session key returned from Bitwarden")
            
            return session_key
            
        except asyncio.TimeoutError:
            raise AuthError("Bitwarden login timed out")
        except Exception as e:
            if isinstance(e, AuthError):
                raise
            raise AuthError(f"Password login failed: {str(e)}") from e
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass

    async def _unlock_vault(self, password: str) -> str:
        """
        Unlock Bitwarden vault and get session key.
        
        Args:
            password: Master password or API key
            
        Returns:
            Bitwarden session key
            
        Raises:
            AuthError: If unlock fails
        """
        process = None
        try:
            cmd = [settings.bitwarden_cli_path, "unlock", "--raw"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=password.encode()),
                    timeout=settings.bitwarden_cli_timeout_seconds
                )
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                raise AuthError("Bitwarden unlock timed out")
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise AuthError(f"Bitwarden unlock failed: {error_msg}")
            
            session_key = stdout.decode().strip()
            
            if not session_key:
                raise AuthError("No session key returned from unlock")
            
            return session_key
            
        except asyncio.TimeoutError:
            raise AuthError("Bitwarden unlock timed out")
        except Exception as e:
            if isinstance(e, AuthError):
                raise
            raise AuthError(f"Vault unlock failed: {str(e)}") from e
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass

    async def _verify_session_key(self, session_key: str) -> None:
        """
        Verify that a session key is valid by testing vault access.
        
        Args:
            session_key: Bitwarden session key to verify
            
        Raises:
            AuthError: If session key is invalid
        """
        process = None
        try:
            # Try to sync to verify the session key works
            cmd = [
                settings.bitwarden_cli_path,
                "sync",
                "--session",
                session_key
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.bitwarden_cli_timeout_seconds
                )
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                raise AuthError("Session verification timed out")
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise AuthError(f"Invalid session key: {error_msg}")
            
        except asyncio.TimeoutError:
            raise AuthError("Session verification timed out")
        except Exception as e:
            if isinstance(e, AuthError):
                raise
            raise AuthError(f"Session verification failed: {str(e)}") from e
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass

    async def _lock_bitwarden(self, session_key: str) -> None:
        """
        Lock the Bitwarden vault for a session.
        
        Args:
            session_key: Bitwarden session key
        """
        process = None
        try:
            cmd = [
                settings.bitwarden_cli_path,
                "lock",
                "--session",
                session_key
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.bitwarden_cli_timeout_seconds
                )
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                logger.warning("Bitwarden lock command timed out")
            
            # We don't raise errors here since logout should succeed even if lock fails
            if process.returncode != 0:
                logger.warning("Failed to lock Bitwarden vault, but continuing with logout")
                
        except Exception as e:
            # Log but don't raise - logout should succeed even if lock fails
            logger.warning(f"Error locking Bitwarden vault: {e}")
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass
