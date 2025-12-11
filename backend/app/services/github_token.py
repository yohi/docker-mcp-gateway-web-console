"""GitHub トークン管理サービス。"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings
from ..models.github_token import GitHubItemSummary, GitHubTokenStatus
from ..models.state import GitHubTokenRecord
from .auth import AuthError, AuthService
from .secrets import SecretManager
from .state_store import StateStore

logger = logging.getLogger(__name__)


class GitHubTokenError(Exception):
    """GitHub トークン操作のエラー。"""

    pass


class GitHubTokenService:
    """Bitwarden から GitHub トークンを取得・保存し、利用可能な形で提供する。"""

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        secret_manager: Optional[SecretManager] = None,
        auth_service: Optional[AuthService] = None,
    ) -> None:
        self._state_store = state_store or StateStore()
        self._secret_manager = secret_manager or SecretManager()
        self._auth_service = auth_service or AuthService()
        self._cached_token: Optional[str] = None
        self._cached_source: Optional[str] = None
        self._cached_updated_at: Optional[datetime] = None

        # 初回起動でテーブルが無い場合に備え、スキーマ初期化を保証する
        try:
            self._state_store.init_schema()
        except Exception:
            logger.debug("state store schema initialization skipped", exc_info=True)

    async def search_items(
        self, query: str, session_id: str, limit: int = 20
    ) -> List[GitHubItemSummary]:
        """Bitwarden のアイテムを検索し、ID/名称/フィールド名一覧を返す。"""
        await self._ensure_valid_session(session_id)
        session = await self._auth_service.get_session(session_id)
        if session is None:
            raise AuthError("セッションが無効です")

        items = await self._list_bitwarden_items(session.bw_session_key, query, limit)
        return items

    async def save_from_bitwarden(
        self, session_id: str, item_id: str, field: str
    ) -> GitHubTokenStatus:
        """Bitwarden から指定フィールドを取得し、暗号化して保存する。"""
        await self._ensure_valid_session(session_id)
        session = await self._auth_service.get_session(session_id)
        if session is None:
            raise AuthError("セッションが無効です")

        reference = f"{{{{ bw:{item_id}:{field} }}}}"
        token_value = await self._secret_manager.resolve_reference(
            reference, session_id, session.bw_session_key
        )
        if not token_value:
            raise GitHubTokenError("GitHub トークンが取得できませんでした")

        source = f"bitwarden:{item_id}:{field}"
        self._save_token(token_value, source=source, updated_by=session.user_email or "unknown")
        return self.get_status()

    def delete_token(self) -> None:
        """保存済みの GitHub トークンを削除する。"""
        self._state_store.delete_github_token()
        self._cached_token = None
        self._cached_source = None
        self._cached_updated_at = None

    def get_status(self) -> GitHubTokenStatus:
        """保存状態を返す。"""
        record = self._state_store.get_github_token()
        if record is None:
            return GitHubTokenStatus(configured=False, source=None, updated_by=None, updated_at=None)

        return GitHubTokenStatus(
            configured=True,
            source=record.source,
            updated_by=record.updated_by,
            updated_at=record.updated_at,
        )

    def get_active_token(self) -> Optional[str]:
        """
        GitHub API 呼び出しで利用するトークンを返す。

        優先度: キャッシュ > DB 保存トークン > 環境変数 `github_token`
        """
        if self._cached_token:
            return self._cached_token

        record = self._state_store.get_github_token()
        if record:
            token = self._decrypt_token(record.token_ref)
            self._cached_token = token
            self._cached_source = record.source
            self._cached_updated_at = record.updated_at
            return token

        if settings.github_token:
            self._cached_token = settings.github_token
            self._cached_source = "env:github_token"
            self._cached_updated_at = datetime.now()
            return settings.github_token

        return None

    async def _list_bitwarden_items(
        self, bw_session_key: str, query: str, limit: int
    ) -> List[GitHubItemSummary]:
        """`bw list items` を呼び出し、簡易情報を返す。"""
        process = None
        cmd = [settings.bitwarden_cli_path, "list", "items", "--session", bw_session_key]
        if query:
            cmd.extend(["--search", query])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=settings.bitwarden_cli_timeout_seconds
            )
            if process.returncode != 0:
                msg = stderr.decode().strip() or stdout.decode().strip()
                raise GitHubTokenError(f"Bitwarden 検索に失敗しました: {msg}")

            data = json.loads(stdout.decode() or "[]")
            if not isinstance(data, list):
                raise GitHubTokenError("Bitwarden の応答形式が不正です")

            results: List[GitHubItemSummary] = []
            for item in data[: limit if limit > 0 else None]:
                item_id = item.get("id") or ""
                name = item.get("name") or item.get("object") or "unknown"
                item_type = item.get("type") or item.get("object")
                fields = self._extract_field_names(item)
                results.append(
                    GitHubItemSummary(
                        id=item_id,
                        name=name,
                        type=str(item_type) if item_type is not None else None,
                        fields=fields,
                    )
                )
            return results
        except asyncio.TimeoutError:
            raise GitHubTokenError("Bitwarden 検索がタイムアウトしました")
        except GitHubTokenError:
            raise
        except Exception as exc:
            raise GitHubTokenError(f"Bitwarden 検索に失敗しました: {exc}") from exc
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass

    def _extract_field_names(self, item: dict) -> List[str]:
        """Bitwarden アイテムから利用可能なフィールド名を抽出する。"""
        field_names = set()
        login = item.get("login") or {}
        if login.get("password"):
            field_names.add("password")
        if login.get("username"):
            field_names.add("username")
        if login.get("totp"):
            field_names.add("totp")

        custom_fields = item.get("fields") or []
        if isinstance(custom_fields, list):
            for f in custom_fields:
                name = f.get("name") if isinstance(f, dict) else None
                if name:
                    field_names.add(name)

        return sorted(field_names)

    def _save_token(self, token_value: str, source: str, updated_by: str) -> None:
        """トークンを暗号化して保存し、キャッシュを更新する。"""
        token_ref = self._encrypt_token(token_value)
        record = GitHubTokenRecord(
            token_ref=token_ref,
            source=source,
            updated_by=updated_by,
            updated_at=datetime.now(),
        )
        self._state_store.save_github_token(record)
        self._cached_token = token_value
        self._cached_source = source
        self._cached_updated_at = record.updated_at

    def _encrypt_token(self, token_value: str) -> dict:
        """Fernet でトークンを暗号化する。"""
        cipher = Fernet(settings.oauth_token_encryption_key.encode())
        ciphertext = cipher.encrypt(token_value.encode()).decode()
        return {"ciphertext": ciphertext, "key_id": settings.oauth_token_encryption_key_id}

    def _decrypt_token(self, token_ref: dict) -> str:
        """保存済みトークンを復号する。"""
        ciphertext = token_ref.get("ciphertext")
        if not ciphertext:
            raise GitHubTokenError("保存されたトークンの形式が不正です")

        cipher = Fernet(settings.oauth_token_encryption_key.encode())
        try:
            return cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise GitHubTokenError("GitHub トークンの復号に失敗しました") from exc

    async def _ensure_valid_session(self, session_id: str) -> None:
        """セッションが有効か確認し、無効なら AuthError を送出する。"""
        is_valid = await self._auth_service.validate_session(session_id)
        if not is_valid:
            raise AuthError("セッションが無効または期限切れです")

