"""OAuth フローを扱うサービス。"""

import asyncio
import base64
import hashlib
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from ..config import settings
from ..models.state import CredentialRecord
from .state_store import StateStore

logger = logging.getLogger(__name__)


@dataclass
class OAuthState:
    """state に紐づく PKCE/スコープ情報。"""

    server_id: str
    code_challenge: Optional[str]
    code_challenge_method: Optional[str]
    scopes: List[str]


class TokenCipher:
    """トークンを暗号化・復号するユーティリティ。"""

    def __init__(self, key: str, key_id: str = "default", algorithm: str = "fernet") -> None:
        self._algo = algorithm
        self._key_id = key_id
        self._fernet = Fernet(key.encode("utf-8") if isinstance(key, str) else key)

    @property
    def metadata(self) -> Dict[str, str]:
        """暗号メタデータを返す。"""
        return {"algo": self._algo, "key_id": self._key_id}

    def encrypt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """ペイロードを暗号化し token_ref 用の辞書を返す。"""
        blob = self._fernet.encrypt(json.dumps(payload).encode("utf-8")).decode("utf-8")
        return {"type": "encrypted", "algo": self._algo, "key_id": self._key_id, "blob": blob}

    def decrypt(self, token_ref: Dict[str, Any]) -> Dict[str, Any]:
        """token_ref から平文ペイロードを復号する。"""
        if token_ref.get("type") != "encrypted":
            raise ValueError("token_ref type is not encrypted")

        algo = token_ref.get("algo") or token_ref.get("algorithm")
        key_id = token_ref.get("key_id") or token_ref.get("kid")
        if algo and algo != self._algo:
            raise ValueError(f"unsupported algorithm: {algo}")
        if key_id and key_id != self._key_id:
            raise ValueError(f"unsupported key id: {key_id}")

        blob = token_ref.get("blob")
        if not blob:
            raise ValueError("token_ref missing blob")

        try:
            decrypted = self._fernet.decrypt(blob.encode("utf-8"))
        except InvalidToken as exc:
            raise ValueError("token_ref decrypt failed") from exc

        return json.loads(decrypted.decode("utf-8"))


class OAuthError(Exception):
    """OAuth 処理での例外基底。"""


class OAuthStateMismatchError(OAuthError):
    """state 不一致時の例外。"""


class OAuthProviderError(OAuthError):
    """プロバイダ 4xx 時の例外。"""


class OAuthProviderUnavailableError(OAuthError):
    """プロバイダ 5xx/タイムアウト時の例外。"""


class ScopeNotAllowedError(OAuthError):
    """未許可スコープが含まれる場合の例外。"""

    def __init__(self, missing: List[str]) -> None:
        super().__init__("未許可のスコープが要求されました")
        self.missing = missing


class CredentialNotFoundError(OAuthError):
    """credential_key が見つからない場合の例外。"""


class ConfigurationError(OAuthError):
    """設定値が無効な場合の例外。"""


class ServerMismatchError(OAuthError):
    """server_id が一致しない場合の例外。"""


class OAuthInvalidGrantError(OAuthError):
    """invalid_grant/invalid_token 時の例外。"""


class ScopeUpdateForbiddenError(OAuthError):
    """管理者以外がスコープ変更を試行した場合の例外。"""


class ScopePolicyService:
    """許可スコープを検証するサービス。"""

    def __init__(self, permitted_scopes: Optional[List[str]] = None) -> None:
        self._permitted_scopes = permitted_scopes or []

    def validate(self, required_scopes: List[str]) -> List[str]:
        """不足スコープを返す。許可されていれば空リスト。"""
        if not self._permitted_scopes or not required_scopes:
            return []
        missing: List[str] = []
        for scope in required_scopes:
            if not self._is_permitted(scope):
                missing.append(scope)
        return missing

    def _is_permitted(self, scope: str) -> bool:
        for permitted in self._permitted_scopes:
            if permitted.endswith("*"):
                prefix = permitted[:-1]
                if scope.startswith(prefix):
                    return True
            elif scope == permitted:
                return True
        return False


class OAuthService:
    """OAuth 認可開始とトークン交換を管理する。"""

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        backoff_schedule: Optional[List[float]] = None,
        refresh_backoff_schedule: Optional[List[float]] = None,
        permitted_scopes: Optional[List[str]] = None,
        credential_creator: str = "system",
    ) -> None:
        # state 管理（メモリ）と永続ストア
        self._state_store_mem: Dict[str, OAuthState] = {}
        self._state_store = state_store or StateStore()
        self.state_store = self._state_store  # テスト用に公開
        try:
            self._state_store.init_schema()
        except Exception:
            logger.debug("state store init skipped", exc_info=True)
        self._backoff_schedule = backoff_schedule or [1.0, 2.0, 4.0]
        self._refresh_backoff_schedule = refresh_backoff_schedule or [2.0, 4.0]
        self._refresh_threshold = timedelta(minutes=15)
        self._scope_policy = ScopePolicyService(permitted_scopes or [])
        self._credential_creator = credential_creator
        encryption_key = settings.oauth_token_encryption_key
        if not encryption_key or encryption_key.strip() == "":
            raise ConfigurationError(
                "oauth_token_encryption_key が未設定です。環境変数 OAUTH_TOKEN_ENCRYPTION_KEY に有効な Fernet キーを設定してください。"
            )
        self._token_cipher = TokenCipher(
            encryption_key, settings.oauth_token_encryption_key_id
        )
        self._secret_store: Dict[str, Dict[str, object]] = {}
        self._load_persisted_credentials()

    def _load_persisted_credentials(self) -> None:
        """永続ストアから暗号化済みトークンを復元する。失敗時は再認可させるため削除する。"""
        try:
            records = self._state_store.list_credentials()
        except Exception:
            logger.warning("資格情報のロードに失敗しました。再認可が必要です。", exc_info=True)
            return

        for record in records:
            try:
                secret = self._decrypt_token_ref(record.token_ref)
                self._secret_store[record.credential_key] = secret
            except Exception:
                logger.warning("資格情報の復号に失敗したため削除します: %s", record.credential_key, exc_info=True)
                try:
                    self._state_store.delete_credential(record.credential_key)
                except Exception:
                    logger.debug("復号失敗した credential の削除に失敗しました", exc_info=True)

    def _encrypt_tokens(
        self, *, access_token: Optional[str], refresh_token: Optional[str], scopes: List[str], expires_at: datetime
    ) -> Dict[str, Any]:
        """アクセストークン等を暗号化し token_ref を生成する。"""
        payload = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scopes": scopes,
            "expires_at": expires_at.isoformat(),
            **self._token_cipher.metadata,
        }
        return self._token_cipher.encrypt(payload)

    def _decrypt_token_ref(self, token_ref: Dict[str, Any]) -> Dict[str, Any]:
        """token_ref を復号してメモリキャッシュ用の辞書を返す。"""
        payload = self._token_cipher.decrypt(token_ref)

        expires_raw = payload.get("expires_at")
        if isinstance(expires_raw, str):
            expires_at = datetime.fromisoformat(expires_raw)
        elif isinstance(expires_raw, datetime):
            expires_at = expires_raw
        else:
            raise ValueError("expires_at is missing")

        scopes = payload.get("scopes") or payload.get("scope") or []
        if isinstance(scopes, str):
            scopes = scopes.split()

        return {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "expires_at": expires_at,
            "scope": scopes,
        }

    @staticmethod
    def _parse_expires_in(raw_value: object) -> int:
        """expires_in を安全に整数秒へ変換する。"""
        default = 3600
        if raw_value is None:
            return default
        try:
            seconds = int(float(raw_value))
        except (TypeError, ValueError):
            return default
        if seconds < 0:
            return 0
        return seconds

    def start_auth(
        self,
        server_id: str,
        scopes: List[str],
        code_challenge: Optional[str] = None,
        code_challenge_method: str = "S256",
    ) -> dict:
        """state を生成し、クライアント指定の code_challenge で認可 URL を返す。"""
        if not settings.oauth_authorize_url or not settings.oauth_client_id:
            raise OAuthError("OAuth 設定が不足しています")

        missing = self._scope_policy.validate(scopes)
        state = secrets.token_urlsafe(32)
        if missing:
            self._record_audit(
                event_type="scope_denied",
                correlation_id=state,
                metadata={"server_id": server_id, "requested_scopes": scopes, "missing": missing},
            )
            raise ScopeNotAllowedError(missing)

        if code_challenge and code_challenge_method not in {"S256", "plain"}:
            raise OAuthError("未対応の code_challenge_method です。S256 もしくは plain を指定してください。")

        scope_value = " ".join(scopes) if scopes else ""
        query = {
            "response_type": "code",
            "client_id": settings.oauth_client_id,
            "redirect_uri": settings.oauth_redirect_uri,
            "state": state,
            "scope": scope_value,
        }
        if code_challenge:
            query["code_challenge"] = code_challenge
            query["code_challenge_method"] = code_challenge_method

        auth_url = f"{settings.oauth_authorize_url}?{urlencode(query)}"

        self._state_store_mem[state] = OAuthState(
            server_id=server_id,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method if code_challenge else None,
            scopes=scopes,
        )

        logger.info("OAuth 認可開始: server_id=%s state=%s", server_id, state)
        return {
            "auth_url": auth_url,
            "state": state,
            "required_scopes": scopes,
        }

    def update_permitted_scopes(
        self, scopes: List[str], is_admin: bool, correlation_id: Optional[str] = None
    ) -> None:
        """許可スコープを更新し、既存資格情報を無効化する。"""
        correlation = correlation_id or secrets.token_urlsafe(16)
        if not is_admin:
            self._record_audit(
                event_type="scope_update_forbidden",
                correlation_id=correlation,
                metadata={"requested_scopes": scopes},
            )
            raise ScopeUpdateForbiddenError("許可スコープの変更は管理者のみ可能です")

        self._scope_policy = ScopePolicyService(scopes or [])
        # 既存の credential を無効化
        for key in list(self._secret_store.keys()):
            self._delete_credential(key)
        self._record_audit(
            event_type="scope_updated",
            correlation_id=correlation,
            metadata={"permitted_scopes": scopes},
        )

    async def exchange_token(
        self,
        code: str,
        state: str,
        server_id: Optional[str] = None,
        code_verifier: Optional[str] = None,
    ) -> dict:
        """認可コードをトークンに交換する。"""
        if not settings.oauth_token_url:
            raise OAuthError("OAuth トークンエンドポイントが設定されていません")
        if state not in self._state_store_mem:
            raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")

        oauth_state = self._state_store_mem.get(state)
        if oauth_state is None:
            raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")
        if server_id and oauth_state.server_id != server_id:
            raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")
        oauth_state = self._state_store_mem.pop(state)

        if oauth_state.code_challenge:
            if not code_verifier:
                raise OAuthError("code_verifier が指定されていません")
            if oauth_state.code_challenge_method == "S256":
                computed_challenge = self._compute_code_challenge(code_verifier)
            else:
                computed_challenge = code_verifier
            if oauth_state.code_challenge != computed_challenge:
                raise OAuthError("code_verifier が一致しません")

        request_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oauth_redirect_uri,
            "client_id": settings.oauth_client_id,
        }
        if code_verifier:
            request_data["code_verifier"] = code_verifier

        last_error: Optional[Exception] = None
        for attempt, delay in enumerate(self._backoff_schedule, start=1):
            try:
                response = await self._send_token_request(request_data)
                if 400 <= response.status_code < 500:
                    raise OAuthProviderError("プロバイダから無効な応答が返されました。再認可してください。")
                if response.status_code >= 500:
                    raise OAuthProviderUnavailableError("プロバイダ障害。時間を置いて再試行してください")

                payload = response.json()
                scope_value = payload.get("scope") or " ".join(oauth_state.scopes)
                scope_list = scope_value.split() if isinstance(scope_value, str) else oauth_state.scopes
                credential = self._save_tokens(
                    server_id=oauth_state.server_id,
                    scopes=scope_list,
                    payload=payload,
                    correlation_id=state,
                )
                return {
                    "status": "authorized",
                    "scope": scope_list,
                    "expires_in": payload.get("expires_in"),
                    "credential_key": credential["credential_key"],
                    "expires_at": credential["expires_at"],
                }
            except OAuthProviderUnavailableError as exc:
                last_error = exc
                if attempt >= len(self._backoff_schedule):
                    break
                await asyncio.sleep(delay)
            except httpx.TimeoutException as exc:
                last_error = OAuthProviderUnavailableError("プロバイダ障害。時間を置いて再試行してください")
                last_error.__cause__ = exc
                if attempt >= len(self._backoff_schedule):
                    break
                await asyncio.sleep(delay)
            except Exception as exc:
                last_error = exc
                break

        if last_error:
            raise last_error

        raise OAuthProviderUnavailableError("プロバイダ障害。時間を置いて再試行してください")

    async def refresh_token(self, server_id: str, credential_key: str) -> dict:
        """保存済みトークンを必要に応じてリフレッシュする。"""
        record = self._state_store.get_credential(credential_key)
        secret = self._secret_store.get(credential_key)
        if record is None or secret is None:
            raise CredentialNotFoundError("credential_key が見つかりません")
        if server_id and record.server_id != server_id:
            raise ServerMismatchError("server_id が一致しません")

        now = datetime.now(timezone.utc)
        if record.expires_at - now > self._refresh_threshold:
            return {
                "credential_key": credential_key,
                "refreshed": False,
                "scope": record.scopes,
                "expires_at": record.expires_at,
            }

        refresh_token = secret.get("refresh_token")
        if not refresh_token:
            self._delete_credential(credential_key)
            raise OAuthInvalidGrantError("保存済みトークンが無効になりました。再認可してください。")

        request_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.oauth_client_id,
        }
        last_error: Optional[Exception] = None
        for attempt, delay in enumerate(self._refresh_backoff_schedule, start=1):
            try:
                response = await self._send_token_request(request_data)
                if 400 <= response.status_code < 500:
                    self._delete_credential(credential_key)
                    raise OAuthInvalidGrantError("保存済みトークンが無効になりました。再認可してください。")
                if response.status_code >= 500:
                    raise OAuthProviderUnavailableError("プロバイダ障害。時間を置いて再試行してください")

                payload = response.json()
                scope_value = payload.get("scope") or " ".join(record.scopes)
                scopes = scope_value.split() if isinstance(scope_value, str) else record.scopes
                credential = self._save_tokens(
                    server_id=record.server_id, scopes=scopes, payload=payload
                )
                self._delete_credential(credential_key)
                self._record_audit(
                    event_type="token_refreshed",
                    correlation_id=credential["credential_key"],
                    metadata={
                        "old_credential_key": credential_key,
                        "credential_key": credential["credential_key"],
                        "server_id": record.server_id,
                    },
                )
                return {
                    "credential_key": credential["credential_key"],
                    "refreshed": True,
                    "scope": scopes,
                    "expires_at": credential["expires_at"],
                }
            except OAuthInvalidGrantError:
                raise
            except OAuthProviderUnavailableError as exc:
                last_error = exc
                if attempt >= len(self._refresh_backoff_schedule):
                    break
                await asyncio.sleep(delay)
            except httpx.TimeoutException as exc:
                last_error = OAuthProviderUnavailableError("プロバイダ障害。時間を置いて再試行してください")
                last_error.__cause__ = exc
                if attempt >= len(self._refresh_backoff_schedule):
                    break
                await asyncio.sleep(delay)
            except Exception as exc:
                last_error = exc
                break

        if last_error:
            raise last_error
        raise OAuthProviderUnavailableError("プロバイダ障害。時間を置いて再試行してください")

    def _save_tokens(
        self,
        server_id: str,
        scopes: List[str],
        payload: Dict[str, object],
        correlation_id: Optional[str] = None,
    ) -> Dict[str, object]:
        """トークンを保存し credential_key を返す。"""
        expires_in = self._parse_expires_in(payload.get("expires_in"))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        credential_key = str(uuid.uuid4())
        token_ref = self._encrypt_tokens(
            access_token=payload.get("access_token"),
            refresh_token=payload.get("refresh_token"),
            scopes=scopes,
            expires_at=expires_at,
        )

        record = CredentialRecord(
            credential_key=credential_key,
            token_ref=token_ref,
            scopes=scopes,
            expires_at=expires_at,
            server_id=server_id,
            created_by=self._credential_creator,
        )
        self._state_store.save_credential(record)
        self._secret_store[credential_key] = {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "expires_at": expires_at,
            "scope": scopes,
        }
        self._record_audit(
            event_type="token_saved",
            correlation_id=correlation_id or credential_key,
            metadata={
                "credential_key": credential_key,
                "server_id": server_id,
                "expires_at": expires_at.isoformat(),
            },
        )
        return {"credential_key": credential_key, "expires_at": expires_at}

    def _delete_credential(self, credential_key: str) -> None:
        """credential_key に紐づくデータを削除する。"""
        self._state_store.delete_credential(credential_key)
        self._secret_store.pop(credential_key, None)

    def _record_audit(
        self, event_type: str, correlation_id: str, metadata: Dict[str, object]
    ) -> None:
        """監査ログを記録する。"""
        try:
            self._state_store.record_audit_log(
                event_type=event_type,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        except Exception:
            logger.warning("監査ログの記録に失敗しました", exc_info=True)

    @staticmethod
    def _compute_code_challenge(pkce_verifier: str) -> str:
        """PKCE code_challenge を生成する。"""
        digest = hashlib.sha256(pkce_verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    async def _send_token_request(self, data: dict) -> httpx.Response:
        """トークンエンドポイントへリクエストする。"""
        async with httpx.AsyncClient(timeout=settings.oauth_request_timeout_seconds) as client:
            return await client.post(
                settings.oauth_token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
