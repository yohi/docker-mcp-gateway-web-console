"""Authentication Service for Bitwarden integration."""

import asyncio
import json
import logging
import os
import stat
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from ..config import settings
from ..models.auth import AuthMethod, LoginRequest, Session
from ..models.state import AuthSessionRecord
from .state_store import StateStore

logger = logging.getLogger(__name__)

_DEFAULT_STATE_STORE = StateStore()
try:
    _DEFAULT_STATE_STORE.init_schema()
except Exception as exc:  # noqa: BLE001
    logger.warning("StateStore の初期化に失敗しました（継続します）: %s", exc)


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

    def __init__(
        self,
        on_session_end: Optional['Callable[[str], None]'] = None,
        state_store: Optional[StateStore] = None,
    ):
        """
        Initialize the Auth Service.
        
        Args:
            on_session_end: Optional callback function to be called when a session ends.
                           Receives session_id as argument.
            state_store: 永続化用の StateStore。未指定ならデフォルトパスを利用。
        """
        # In-memory session storage: {session_id: Session}
        self._sessions: Dict[str, Session] = {}
        self._session_timeout = timedelta(minutes=settings.session_timeout_minutes)
        self._on_session_end = on_session_end
        self._state_store = state_store or _DEFAULT_STATE_STORE

        try:
            self._state_store.init_schema()
            self._load_persisted_sessions()
        except Exception as exc:  # noqa: BLE001
            logger.warning("セッション永続化の初期化に失敗しました: %s", exc)

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
        now = datetime.now(timezone.utc)
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
        self._persist_session(session)
        
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
        session = self._sessions.get(session_id) or self._load_session_from_store(session_id)
        if session is None:
            logger.warning(f"Logout attempted for non-existent session: {session_id}")
            return False
        
        # Lock the Bitwarden vault for this session
        await self._lock_bitwarden(session.bw_session_key)
        
        # Remove session from storage
        self._sessions.pop(session_id, None)
        self._delete_persisted_session(session_id)
        
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
        session = self._sessions.get(session_id) or self._load_session_from_store(session_id)
        if session is None:
            return False

        # Normalize timestamps to UTC to avoid naive/aware mismatches
        session.last_activity = self._to_utc(session.last_activity)
        session.expires_at = self._to_utc(session.expires_at)

        now = datetime.now(timezone.utc)
        
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
        self._sessions[session_id] = session
        self._persist_session(session)

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
        now = datetime.now(timezone.utc)
        expired_sessions = []

        for session_id, session in self._sessions.items():
            session.expires_at = self._to_utc(session.expires_at)
            session.last_activity = self._to_utc(session.last_activity)
            if now >= session.expires_at or (now - session.last_activity) >= self._session_timeout:
                expired_sessions.append(session_id)
        
        # Clean up expired sessions
        for session_id in expired_sessions:
            await self.logout(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)

    def _load_persisted_sessions(self) -> None:
        """永続化済みセッションを復元し、期限切れを掃除する。"""
        try:
            records = self._state_store.list_auth_sessions()
        except Exception as exc:  # noqa: BLE001
            logger.warning("永続化セッションの読み込みに失敗しました: %s", exc)
            return

        restored = 0
        now = datetime.now(timezone.utc)
        for record in records:
            session = self._record_to_session(record)
            if now >= session.expires_at or (now - session.last_activity) >= self._session_timeout:
                self._delete_persisted_session(session.session_id)
                continue
            self._sessions[session.session_id] = session
            restored += 1

        if restored:
            logger.info("永続化セッションを復元: %d 件", restored)

    def _record_to_session(self, record: AuthSessionRecord) -> Session:
        """AuthSessionRecord をメモリ用 Session に変換する。"""
        return Session(
            session_id=record.session_id,
            user_email=record.user_email,
            bw_session_key=record.bw_session_key,
            created_at=self._to_utc(record.created_at),
            expires_at=self._to_utc(record.expires_at),
            last_activity=self._to_utc(record.last_activity),
        )

    def _load_session_from_store(self, session_id: str) -> Optional[Session]:
        """単一セッションをストアから復元し、期限切れなら削除する。"""
        try:
            record = self._state_store.get_auth_session(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("永続化セッションの取得に失敗しました: %s", exc)
            return None

        if record is None:
            return None

        session = self._record_to_session(record)
        now = datetime.now(timezone.utc)
        if now >= session.expires_at or (now - session.last_activity) >= self._session_timeout:
            self._delete_persisted_session(session_id)
            return None

        self._sessions[session_id] = session
        return session

    def _persist_session(self, session: Session) -> None:
        """セッションを永続化ストアに保存する。失敗時は警告のみ。"""
        try:
            record = AuthSessionRecord(
                session_id=session.session_id,
                user_email=session.user_email,
                bw_session_key=session.bw_session_key,
                created_at=self._to_utc(session.created_at),
                expires_at=self._to_utc(session.expires_at),
                last_activity=self._to_utc(session.last_activity),
            )
            self._state_store.save_auth_session(record)
        except Exception as exc:  # noqa: BLE001
            logger.warning("セッション永続化に失敗しました: %s", exc)

    def _delete_persisted_session(self, session_id: str) -> None:
        """永続化ストアからセッションを削除する。"""
        try:
            self._state_store.delete_auth_session(session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("セッション削除に失敗しました: %s", exc)

    def _to_utc(self, value: datetime) -> datetime:
        """タイムゾーンの有無を問わず UTC の datetime に正規化する。"""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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
            if (two_step_method is not None) ^ (two_step_code is not None):
                raise ValueError("Both two_step_method and two_step_code must be provided together")
            
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
        Bitwarden のアンロックを実行し、セッションキーを取得する。
        1st: 環境変数経由 (--passwordenv)
        2nd: stdin 経由でパスワードを送る
        3rd: status から取得できればフォールバック
        """
        pw_len = len(password or "")
        logger.info("bw unlock start (password length only): len=%d", pw_len)

        async def _run_unlock(cmd_extra: list[str], use_env: bool, use_stdin: bool) -> tuple[str, str, int]:
            """bw unlock を指定オプションで実行するユーティリティ。"""
            process = None
            try:
                cmd = [settings.bitwarden_cli_path, "unlock", "--raw", *cmd_extra]
                kwargs = {}
                env = os.environ.copy()
                if use_env:
                    env["BW_PASSWORD"] = password
                    kwargs["env"] = env
                if use_stdin:
                    kwargs["stdin"] = asyncio.subprocess.PIPE
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **kwargs,
                )
                input_bytes = password.encode() if use_stdin else None
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=input_bytes),
                    timeout=settings.bitwarden_cli_timeout_seconds,
                )
                return stdout.decode().strip(), stderr.decode().strip(), process.returncode or 0
            finally:
                if process is not None and process.returncode is None:
                    try:
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except (ProcessLookupError, asyncio.TimeoutError):
                        pass

        # passwordfile 用の一時ファイルを用意（使わない場合もあるが先に準備）
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, mode="wb") as tmp:
                os.chmod(tmp.name, stat.S_IRUSR | stat.S_IWUSR)
                tmp.write(password.encode())
                tmp.flush()
                tmp_path = tmp.name
        except Exception:
            tmp_path = None

        try:
            # 試行順:
            #  1. env+nointeraction
            #  2. env(対話オフ指定なし)
            #  3. stdin+nointeraction
            #  4. stdin(指定なし)
            #  5. passwordfile
            #  6. 引数 --password 直接指定（ローカル用途の最終手段）
            attempts = [
                (["--nointeraction", "--passwordenv", "BW_PASSWORD"], True, False),
                (["--passwordenv", "BW_PASSWORD"], True, False),
                (["--nointeraction"], False, True),
                ([], False, True),
                *(
                    [
                        (["--nointeraction", "--passwordfile", tmp_path], False, False),
                        (["--passwordfile", tmp_path], False, False),
                    ]
                    if tmp_path
                    else []
                ),
            ]

            if settings.allow_cli_password:
                logger.warning(
                    "AUTH_ALLOW_CLI_PASSWORD が有効です。--password 引数は非推奨で、"
                    "本番環境では使用しないでください。"
                )
                attempts.append((["--nointeraction", "--password", password], False, False))

            results: list[tuple[str, str, int]] = []
            for idx, (extra, use_env, use_stdin) in enumerate(attempts):
                stdout_msg, stderr_msg, rc = await _run_unlock(extra, use_env, use_stdin)
                results.append((stdout_msg, stderr_msg, rc))
                logger.info(
                    "bw unlock attempt %d rc=%s use_env=%s use_stdin=%s stdout=%s stderr=%s",
                    idx + 1,
                    rc,
                    use_env,
                    use_stdin,
                    stdout_msg[:200],
                    stderr_msg[:200],
                )
                if rc == 0 and stdout_msg:
                    return stdout_msg
                # rc==0 かつ stdout 空の場合: 既存セッションがあるかもしれないので status で確認
                if rc == 0 and not stdout_msg:
                    session_key = await self._get_session_from_status()
                    if session_key:
                        return session_key

            # 3rd: アンロック済みで --raw が空を返した場合のフォールバック
            session_key = await self._get_session_from_status()
            if session_key:
                return session_key

            # 失敗時は詳細を返す
            detail = "Bitwarden unlock failed"
            for stdout_msg, stderr_msg, rc in results:
                msg = stderr_msg or stdout_msg
                if msg:
                    detail = f"{detail}: {msg}"
                    break
            raise AuthError(detail)
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


    async def _get_session_from_status(self) -> Optional[str]:
        """bw status --raw から既存セッションキーを取得するフォールバック。"""
        process = None
        try:
            cmd = [settings.bitwarden_cli_path, "status", "--raw"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.bitwarden_cli_timeout_seconds,
            )
            if process.returncode != 0:
                return None

            try:
                data = json.loads(stdout.decode() or "{}")
                session = data.get("session")
                if isinstance(session, str) and session:
                    return session
            except Exception:
                return None
        except Exception:
            return None
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass
        return None

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
