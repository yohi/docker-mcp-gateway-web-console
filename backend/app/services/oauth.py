"""OAuth フローを扱うサービス。"""

import asyncio
import base64
import hashlib
import ipaddress
import json
import logging
import secrets
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER, settings
from ..models.state import CredentialRecord, OAuthStateRecord
from .metrics import MetricsRecorder
from .state_store import StateStore

logger = logging.getLogger(__name__)


@dataclass
class OAuthState:
    """state に紐づく PKCE/スコープ情報。"""

    server_id: str
    code_challenge: Optional[str]
    code_challenge_method: Optional[str]
    scopes: List[str]
    authorize_url: str
    token_url: str
    client_id: str
    redirect_uri: str
    expires_at: datetime


def _is_private_or_local_ip(hostname: str) -> bool:
    """ホスト名がプライベート/ローカル/メタデータIPかチェックする。"""
    try:
        # ホスト名をIPアドレスに解決
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)

        # プライベート/ローカル/予約済みアドレスをチェック
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True

        # クラウドメタデータエンドポイント(169.254.169.254)をチェック
        if ip_str == "169.254.169.254":
            return True

        return False
    except socket.gaierror:
        # DNS解決に失敗した場合はローカル開発やオフライン環境を許容し、非プライベートとみなす
        return False
    except ValueError:
        # IP形式への変換ができない場合はプライベート判定できないため非プライベートとみなす
        return False


def _normalize_oauth_url(value: str, *, field_name: str) -> str:
    """OAuth URLを検証・正規化する。SSRF対策を含む。"""
    url = (value or "").strip()
    if not url:
        raise OAuthError(f"{field_name} が未設定です")

    parsed = urlparse(url)

    # HTTPSスキームのみ許可。ただしローカル開発用途の http://localhost 系のみ許容
    hostname = parsed.hostname or parsed.netloc.split(":")[0]
    if parsed.scheme == "http":
        if hostname not in {"localhost", "127.0.0.1", "::1"}:
            logger.warning(
                "OAuth URL rejected: non-HTTPS scheme. field=%s url=%s",
                field_name,
                url,
            )
            raise OAuthError(f"{field_name} は HTTPS スキームである必要があります: {url}")
    elif parsed.scheme != "https":
        logger.warning(
            "OAuth URL rejected: unsupported scheme. field=%s url=%s",
            field_name,
            url,
        )
        raise OAuthError(f"{field_name} のスキームが不正です: {url}")

    if not parsed.netloc:
        raise OAuthError(f"{field_name} が不正です: {url}")

    # ホスト名を抽出(ポート番号を除く)
    hostname = parsed.hostname or parsed.netloc.split(":")[0]

    # IPアドレス形式をチェック
    try:
        ip = ipaddress.ip_address(hostname)
        # プライベート/ローカル/予約済みIPを拒否
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            logger.warning(
                "OAuth URL rejected: private/local IP. field=%s url=%s ip=%s",
                field_name,
                url,
                hostname,
            )
            # ローカル開発用途の http + localhost 以外は拒否
            if not (parsed.scheme == "http" and hostname in {"127.0.0.1", "::1"}):
                raise OAuthError(f"{field_name} にプライベート/ローカルIPは使用できません")

        # クラウドメタデータエンドポイントを拒否
        if str(ip) == "169.254.169.254":
            logger.warning(
                "OAuth URL rejected: metadata endpoint. field=%s url=%s",
                field_name,
                url,
            )
            raise OAuthError(f"{field_name} にメタデータエンドポイントは使用できません")
    except ValueError:
        # IPアドレスではなくホスト名の場合
        # ローカルホスト名は HTTP スキームの開発用途のみ許容
        if hostname.lower() in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
            if parsed.scheme != "http":
                logger.warning(
                    "OAuth URL rejected: localhost. field=%s url=%s hostname=%s",
                    field_name,
                    url,
                    hostname,
                )
                raise OAuthError(f"{field_name} に localhost は使用できません")
        # DNS解決してプライベートIPをチェック
        elif _is_private_or_local_ip(hostname):
            logger.warning(
                "OAuth URL rejected: resolves to private IP. field=%s url=%s hostname=%s",
                field_name,
                url,
                hostname,
            )
            raise OAuthError(f"{field_name} がプライベートIPに解決されます")

    return url


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


def _strip_trailing_slash(url: str) -> str:
    return url[:-1] if url.endswith("/") else url


def _is_github_oauth_endpoints(authorize_url: str, token_url: str) -> bool:
    return _strip_trailing_slash(authorize_url) == GITHUB_AUTHORIZE_URL and _strip_trailing_slash(
        token_url
    ) == GITHUB_TOKEN_URL


def _is_domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    """URLのドメインが許可リストに含まれているかチェックする。"""
    # 許可ドメイン指定なしの場合は拒否（本番環境で明示的な設定を要求）
    if not allowed_domains:
        return False

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()

        for allowed_domain in allowed_domains:
            # 完全一致またはサブドメイン一致
            if hostname == allowed_domain or hostname.endswith(f".{allowed_domain}"):
                return True

        return False
    except Exception:
        return False


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_allowed_redirect_uri(redirect_uri: str) -> bool:
    try:
        origin = _origin(redirect_uri)
    except Exception:
        return False
    return origin in settings.cors_origins_list


class TokenCipher:
    """トークンを暗号化・復号するユーティリティ。"""

    def __init__(self, key: str, key_id: str = "default", algorithm: str = "fernet") -> None:
        self._algo = algorithm or "fernet"
        self._key_id = key_id
        self._fernet: Optional[Fernet] = None
        self._aesgcm: Optional[AESGCM] = None

        if self._algo == "fernet":
            self._fernet = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        elif self._algo == "aes-gcm":
            key_bytes = key.encode("utf-8") if isinstance(key, str) else key
            try:
                key_bytes = base64.urlsafe_b64decode(key_bytes)
            except Exception as exc:  # noqa: BLE001
                raise ValueError("invalid AES-GCM key encoding") from exc
            if len(key_bytes) != 32:
                raise ValueError("AES-GCM key must be 32 bytes (256-bit)")
            self._aesgcm = AESGCM(key_bytes)
        else:
            raise ValueError(f"unsupported algorithm: {self._algo}")

    @property
    def metadata(self) -> Dict[str, str]:
        """暗号メタデータを返す。"""
        return {"algo": self._algo, "key_id": self._key_id}

    def encrypt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """ペイロードを暗号化し token_ref 用の辞書を返す。"""
        message = json.dumps(payload).encode("utf-8")
        if self._algo == "fernet" and self._fernet:
            blob = self._fernet.encrypt(message).decode("utf-8")
            return {"type": "encrypted", "algo": self._algo, "key_id": self._key_id, "blob": blob}

        if self._algo == "aes-gcm" and self._aesgcm:
            nonce = secrets.token_bytes(12)
            ciphertext = self._aesgcm.encrypt(nonce, message, associated_data=None)
            return {
                "type": "encrypted",
                "algo": self._algo,
                "key_id": self._key_id,
                "blob": base64.urlsafe_b64encode(ciphertext).decode("utf-8"),
                "nonce": base64.urlsafe_b64encode(nonce).decode("utf-8"),
            }

        raise ValueError("cipher is not initialized")

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

        if self._algo == "fernet" and self._fernet:
            blob = token_ref.get("blob")
            if not blob:
                raise ValueError("token_ref missing blob")
            try:
                decrypted = self._fernet.decrypt(blob.encode("utf-8"))
            except InvalidToken as exc:  # noqa: BLE001
                raise ValueError("token_ref decrypt failed") from exc
            return json.loads(decrypted.decode("utf-8"))

        if self._algo == "aes-gcm" and self._aesgcm:
            blob = token_ref.get("blob")
            nonce = token_ref.get("nonce")
            if not blob or not nonce:
                raise ValueError("token_ref missing blob or nonce")
            try:
                ciphertext = base64.urlsafe_b64decode(blob)
                nonce_bytes = base64.urlsafe_b64decode(nonce)
            except Exception as exc:  # noqa: BLE001
                raise ValueError("token_ref base64 decode failed") from exc
            try:
                decrypted = self._aesgcm.decrypt(nonce_bytes, ciphertext, associated_data=None)
            except Exception as exc:  # noqa: BLE001
                raise ValueError("token_ref decrypt failed") from exc
            return json.loads(decrypted.decode("utf-8"))

        raise ValueError("cipher is not initialized")


class OAuthError(Exception):
    """OAuth 処理での例外基底。"""


class OAuthStateMismatchError(OAuthError):
    """state 不一致時の例外。"""


class PkceVerificationError(OAuthError):
    """PKCE 検証失敗時の例外。"""


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


class RemoteServerNotFoundError(OAuthError):
    """server_id に対応するリモートサーバーが存在しない場合の例外。"""


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
        metrics: Optional[MetricsRecorder] = None,
    ) -> None:
        # state 管理（メモリ）と永続ストア
        self._state_store_mem: Dict[str, OAuthState] = {}
        self._state_store = state_store or StateStore()
        self.state_store = self._state_store  # テスト用に公開
        try:
            self._state_store.init_schema()
        except Exception:
            logger.debug("state store init skipped", exc_info=True)
        self._state_ttl = timedelta(minutes=10)
        self._backoff_schedule = backoff_schedule or [1.0, 2.0, 4.0]
        self._refresh_backoff_schedule = refresh_backoff_schedule or [2.0, 4.0]
        self._refresh_threshold = timedelta(minutes=15)
        self._scope_policy = ScopePolicyService(permitted_scopes or [])
        self._credential_creator = credential_creator
        self._client_secret = settings.oauth_client_secret.strip() or None
        self._token_cipher = self._build_token_cipher()
        self._secret_store: Dict[str, Dict[str, object]] = {}
        self._load_persisted_credentials()
        self.metrics = metrics or MetricsRecorder()

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

    def _build_token_cipher(self) -> TokenCipher:
        """暗号化方式を選択して TokenCipher を構築する。"""
        cred_key = settings.credential_encryption_key.strip()
        if cred_key:
            return TokenCipher(
                cred_key,
                settings.credential_encryption_key_id,
                algorithm="aes-gcm",
            )

        fernet_key = settings.oauth_token_encryption_key
        if fernet_key and fernet_key.strip() and fernet_key != OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER:
            return TokenCipher(
                fernet_key,
                settings.oauth_token_encryption_key_id,
                algorithm="fernet",
            )

        raise ConfigurationError(
            "credential_encryption_key もしくは oauth_token_encryption_key を設定してください。"
        )

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
        authorize_url: Optional[str] = None,
        token_url: Optional[str] = None,
        client_id: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: str = "S256",
    ) -> dict:
        """state を生成し、クライアント指定の code_challenge で認可 URL を返す。"""
        # server_id の存在確認（リモートサーバーが登録済みであることが前提）
        server_record = self._state_store.get_remote_server(server_id)
        if server_record is None:
            raise RemoteServerNotFoundError("server_id が存在しません")

        use_authorize_url = authorize_url or settings.oauth_authorize_url
        use_token_url = token_url or settings.oauth_token_url
        use_client_id = client_id or settings.oauth_client_id
        use_redirect_uri = redirect_uri or settings.oauth_redirect_uri

        overrides_requested = any(
            v is not None for v in (authorize_url, token_url, client_id, redirect_uri)
        )
        if overrides_requested and not settings.oauth_allow_override:
            # 既定では上書き禁止。ただしフロント側のリダイレクト(/oauth/callback)対応や GitHub OAuth など、
            # 安全と判断できる限定ケースのみ許可する。
            if client_id is not None:
                raise OAuthError(
                    "OAuth client_id の上書きが無効です。環境変数 OAUTH_ALLOW_OVERRIDE=true を設定してください。"
                )

            if authorize_url is not None or token_url is not None:
                if authorize_url is None or token_url is None:
                    raise OAuthError(
                        "OAuth authorize_url/token_url はセットで指定してください。"
                    )
                normalized_authorize = _normalize_oauth_url(authorize_url, field_name="authorize_url")
                normalized_token = _normalize_oauth_url(token_url, field_name="token_url")
                if not _is_github_oauth_endpoints(normalized_authorize, normalized_token):
                    raise OAuthError(
                        "OAuth エンドポイントの上書きが無効です。環境変数 OAUTH_ALLOW_OVERRIDE=true を設定してください。"
                    )
                use_authorize_url = normalized_authorize
                use_token_url = normalized_token

            if redirect_uri is not None:
                normalized_redirect = _normalize_oauth_url(redirect_uri, field_name="redirect_uri")
                if not _is_allowed_redirect_uri(normalized_redirect):
                    raise OAuthError(
                        "OAuth redirect_uri が許可されていません。CORS_ORIGINS にフロントのOriginを追加するか、"
                        "環境変数 OAUTH_ALLOW_OVERRIDE=true を設定してください。"
                    )
                use_redirect_uri = normalized_redirect

        use_authorize_url = _normalize_oauth_url(use_authorize_url, field_name="authorize_url")
        use_token_url = _normalize_oauth_url(use_token_url, field_name="token_url")
        use_client_id = (use_client_id or "").strip()
        if not use_client_id:
            raise OAuthError("client_id が未設定です")
        use_redirect_uri = _normalize_oauth_url(use_redirect_uri, field_name="redirect_uri")

        # 許可ドメインリストチェック
        allowed_domains = settings.oauth_allowed_domains_list
        if not _is_domain_allowed(use_authorize_url, allowed_domains):
            logger.warning(
                "OAuth URL rejected: domain not in allowlist. url=%s allowed_domains=%s",
                use_authorize_url,
                allowed_domains,
            )
            raise OAuthError(
                f"authorize_url のドメインが許可リストに含まれていません。許可ドメイン: {', '.join(allowed_domains)}"
            )
        if not _is_domain_allowed(use_token_url, allowed_domains):
            logger.warning(
                "OAuth URL rejected: domain not in allowlist. url=%s allowed_domains=%s",
                use_token_url,
                allowed_domains,
            )
            raise OAuthError(
                f"token_url のドメインが許可リストに含まれていません。許可ドメイン: {', '.join(allowed_domains)}"
            )

        missing = self._scope_policy.validate(scopes)
        state = secrets.token_urlsafe(32)
        if missing:
            self._record_audit(
                event_type="scope_denied",
                correlation_id=state,
                metadata={"server_id": server_id, "requested_scopes": scopes, "missing": missing},
            )
            raise ScopeNotAllowedError(missing)

        if not code_challenge:
            raise OAuthError("code_challenge が指定されていません")
        if code_challenge_method != "S256":
            raise OAuthError("code_challenge_method は S256 のみサポートします")

        scope_value = " ".join(scopes) if scopes else ""
        query = {
            "response_type": "code",
            "client_id": use_client_id,
            "redirect_uri": use_redirect_uri,
            "state": state,
            "scope": scope_value,
        }
        if code_challenge:
            query["code_challenge"] = code_challenge
            query["code_challenge_method"] = code_challenge_method

        auth_url = f"{use_authorize_url}?{urlencode(query)}"

        expires_at = datetime.now(timezone.utc) + self._state_ttl
        oauth_state = OAuthState(
            server_id=server_id,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scopes=scopes,
            authorize_url=use_authorize_url,
            token_url=use_token_url,
            client_id=use_client_id,
            redirect_uri=use_redirect_uri,
            expires_at=expires_at,
        )
        self._state_store_mem[state] = oauth_state
        self._persist_state(state, oauth_state)

        logger.info("OAuth 認可開始: server_id=%s state=%s", server_id, state)
        return {
            "auth_url": auth_url,
            "state": state,
            "required_scopes": scopes,
        }

    def _persist_state(self, state: str, oauth_state: OAuthState) -> None:
        """state を永続化し、単一使用・TTL を担保する。"""
        record = OAuthStateRecord(
            state=state,
            server_id=oauth_state.server_id,
            code_challenge=oauth_state.code_challenge,
            code_challenge_method=oauth_state.code_challenge_method,
            scopes=oauth_state.scopes,
            authorize_url=oauth_state.authorize_url,
            token_url=oauth_state.token_url,
            client_id=oauth_state.client_id,
            redirect_uri=oauth_state.redirect_uri,
            expires_at=oauth_state.expires_at,
        )
        self._state_store.save_oauth_state(record)

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

    def _load_state(self, state: str, server_id: Optional[str] = None) -> OAuthState:
        """永続ストアまたはメモリから state を取得し、必要に応じ server_id を検証する。"""
        now = datetime.now(timezone.utc)
        record = self._state_store.get_oauth_state(state)
        if record:
            self._state_store.delete_oauth_state(state)
            if record.expires_at < now:
                raise OAuthStateMismatchError("state の有効期限が切れています。再認可を実施してください")
            if server_id and record.server_id != server_id:
                raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")
            return OAuthState(
                server_id=record.server_id,
                code_challenge=record.code_challenge,
                code_challenge_method=record.code_challenge_method,
                scopes=record.scopes,
                authorize_url=record.authorize_url,
                token_url=record.token_url,
                client_id=record.client_id,
                redirect_uri=record.redirect_uri,
                expires_at=record.expires_at,
            )

        oauth_state = self._state_store_mem.pop(state, None)
        if oauth_state:
            if oauth_state.expires_at < now:
                raise OAuthStateMismatchError("state の有効期限が切れています。再認可を実施してください")
            if server_id and oauth_state.server_id != server_id:
                raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")
            return oauth_state

        raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")

    async def exchange_token(
        self,
        code: str,
        state: str,
        server_id: Optional[str] = None,
        code_verifier: Optional[str] = None,
    ) -> dict:
        """認可コードをトークンに交換する。"""
        oauth_state = self._load_state(state, server_id)

        # state から復元した server_id が現在も有効か確認
        server_record = self._state_store.get_remote_server(oauth_state.server_id)
        if server_record is None:
            raise RemoteServerNotFoundError("server_id が存在しません")

        if oauth_state.code_challenge:
            if not code_verifier:
                raise PkceVerificationError("code_verifier が指定されていません")
            if oauth_state.code_challenge_method and oauth_state.code_challenge_method != "S256":
                raise PkceVerificationError("code_challenge_method が不正です")
            computed_challenge = self._compute_code_challenge(code_verifier)
            if oauth_state.code_challenge != computed_challenge:
                raise PkceVerificationError("code_verifier が一致しません")

        request_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": oauth_state.redirect_uri,
            "client_id": oauth_state.client_id,
        }
        if self._client_secret:
            request_data["client_secret"] = self._client_secret
        if code_verifier:
            request_data["code_verifier"] = code_verifier

        last_error: Optional[Exception] = None
        for attempt, delay in enumerate(self._backoff_schedule, start=1):
            try:
                response = await self._send_token_request(oauth_state.token_url, request_data)
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
                    oauth_token_url=oauth_state.token_url,
                    oauth_client_id=oauth_state.client_id,
                )
                self.metrics.increment(
                    "oauth_flow_success_total", {"result": "exchange_token"}
                )
                return {
                    "success": True,
                    "status": "authorized",
                    "scope": scope_list,
                    "expires_in": payload.get("expires_in"),
                    "credential_key": credential["credential_key"],
                    "expires_at": credential["expires_at"],
                    "server_id": oauth_state.server_id,
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
            self.metrics.increment(
                "oauth_flow_failure_total",
                {"error": last_error.__class__.__name__, "result": "exchange_token"},
            )
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

        token_url = record.oauth_token_url or settings.oauth_token_url
        if not token_url:
            self._delete_credential(credential_key)
            raise OAuthError("OAuth トークンエンドポイントが設定されていません")
        client_id = record.oauth_client_id or settings.oauth_client_id
        if not client_id:
            self._delete_credential(credential_key)
            raise OAuthError("OAuth client_id が設定されていません")

        request_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        if self._client_secret:
            request_data["client_secret"] = self._client_secret
        last_error: Optional[Exception] = None
        for attempt, delay in enumerate(self._refresh_backoff_schedule, start=1):
            try:
                response = await self._send_token_request(token_url, request_data)
                if 400 <= response.status_code < 500:
                    self._delete_credential(credential_key)
                    raise OAuthInvalidGrantError("保存済みトークンが無効になりました。再認可してください。")
                if response.status_code >= 500:
                    raise OAuthProviderUnavailableError("プロバイダ障害。時間を置いて再試行してください")

                payload = response.json()
                scope_value = payload.get("scope") or " ".join(record.scopes)
                scopes = scope_value.split() if isinstance(scope_value, str) else record.scopes
                credential = self._save_tokens(
                    server_id=record.server_id,
                    scopes=scopes,
                    payload=payload,
                    oauth_token_url=token_url,
                    oauth_client_id=client_id,
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
        oauth_token_url: Optional[str] = None,
        oauth_client_id: Optional[str] = None,
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
            oauth_token_url=oauth_token_url,
            oauth_client_id=oauth_client_id,
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

    async def _send_token_request(self, token_url: str, data: dict) -> httpx.Response:
        """トークンエンドポイントへリクエストする。"""
        async with httpx.AsyncClient(timeout=settings.oauth_request_timeout_seconds) as client:
            return await client.post(
                token_url,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json, application/x-www-form-urlencoded;q=0.9, */*;q=0.1",
                },
            )
