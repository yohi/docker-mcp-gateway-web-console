"""OAuth フローを扱うサービス。"""

import asyncio
import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class OAuthState:
    """state に紐づく PKCE/スコープ情報。"""

    server_id: str
    code_challenge: Optional[str]
    code_challenge_method: Optional[str]
    scopes: List[str]


class OAuthError(Exception):
    """OAuth 処理での例外基底。"""


class OAuthStateMismatchError(OAuthError):
    """state 不一致時の例外。"""


class OAuthProviderError(OAuthError):
    """プロバイダ 4xx 時の例外。"""


class OAuthProviderUnavailableError(OAuthError):
    """プロバイダ 5xx/タイムアウト時の例外。"""


class OAuthService:
    """OAuth 認可開始とトークン交換を管理する。"""

    def __init__(
        self,
        state_store: Optional[Dict[str, OAuthState]] = None,
        backoff_schedule: Optional[List[float]] = None,
    ) -> None:
        # TODO: 本番環境では Redis などの永続/共有ストアを注入すること
        self._state_store: Dict[str, OAuthState] = state_store if state_store is not None else {}
        self._backoff_schedule = backoff_schedule or [1.0, 2.0, 4.0]

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

        state = secrets.token_urlsafe(32)
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

        self._state_store[state] = OAuthState(
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
        if state not in self._state_store:
            raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")

        oauth_state = self._state_store.get(state)
        if oauth_state is None:
            raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")
        if server_id and oauth_state.server_id != server_id:
            raise OAuthStateMismatchError("state 不一致のため再認可を実施してください")
        oauth_state = self._state_store.pop(state)

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
                return {
                    "status": "authorized",
                    "scope": scope_list,
                    "expires_in": payload.get("expires_in"),
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
