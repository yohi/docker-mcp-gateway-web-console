"""リモート MCP サーバーを管理するサービス層。"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from ..models.remote import RemoteServer, RemoteServerStatus
from ..models.state import CredentialRecord, RemoteServerRecord
from .oauth import CredentialNotFoundError, RemoteServerNotFoundError
from .state_store import StateStore

logger = logging.getLogger(__name__)
_UNSET = object()


class RemoteMcpError(Exception):
    """RemoteMcpService で発生する汎用エラー。"""


class EndpointNotAllowedError(RemoteMcpError):
    """許可リストにないエンドポイントが指定された場合のエラー。"""


class DuplicateRemoteServerError(RemoteMcpError):
    """既に登録済みのサーバーに対する重複登録エラー。"""


class TooManyConnectionsError(RemoteMcpError):
    """同時接続上限を超過した場合のエラー。"""


class RemoteMcpService:
    """リモート MCP サーバーの CRUD と資格情報取得を担当する。"""

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        oauth_service: Optional[object] = None,
        *,
        max_connections: Optional[int] = None,
        sse_client_factory: Optional[object] = None,
        http_client_factory: Optional[object] = None,
        connect_timeout_seconds: float = 30.0,
        heartbeat_interval_seconds: float = 120.0,
        idle_timeout_seconds: float = 300.0,
    ) -> None:
        self._state_store = state_store or StateStore()
        self.state_store = self._state_store  # テスト用に公開
        self._oauth_service = oauth_service
        try:
            self._state_store.init_schema()
        except Exception:
            logger.debug("state store init skipped", exc_info=True)

        # 依存を注入可能にし、テスト時にモックできるようにする
        if sse_client_factory is not None:
            self._sse_client_factory = sse_client_factory
        else:
            try:
                from mcp.client.sse import sse_client  # type: ignore

                self._sse_client_factory = sse_client
            except Exception:
                self._sse_client_factory = None

        self._http_client_factory = http_client_factory or self._default_http_client_factory

        self._connect_timeout = float(connect_timeout_seconds)
        self._heartbeat_interval = float(heartbeat_interval_seconds)
        self._idle_timeout = float(idle_timeout_seconds)

        max_conn = max_connections or self._get_max_connections()
        self._connection_semaphore = asyncio.Semaphore(max_conn)

    async def register_server(
        self,
        *,
        catalog_item_id: str,
        name: str,
        endpoint: str,
        correlation_id: Optional[str] = None,
    ) -> RemoteServer:
        """
        カタログ項目をもとにリモートサーバーを登録する。

        Raises:
            EndpointNotAllowedError: 許可リストに一致しない場合
            DuplicateRemoteServerError: 同一 catalog_item_id または endpoint が既に登録済みの場合
        """
        endpoint_norm = (endpoint or "").strip()
        if not catalog_item_id or not name or not endpoint_norm:
            raise RemoteMcpError("catalog_item_id, name, endpoint は必須です")

        parsed = urlparse(endpoint_norm)
        host = parsed.hostname or ""
        port = parsed.port or (443 if (parsed.scheme or "").lower() == "https" else 80)

        if not self._state_store.is_endpoint_allowed(endpoint_norm):
            self._record_audit(
                event_type="endpoint_rejected",
                correlation_id=correlation_id or catalog_item_id,
                metadata={
                    "catalog_item_id": catalog_item_id,
                    "endpoint": endpoint_norm,
                    "reason": "not_in_allowlist",
                },
            )
            raise EndpointNotAllowedError(
                f"Endpoint not allowed: {host}:{port} is not in REMOTE_MCP_ALLOWED_DOMAINS"
            )

        existing = self._state_store.list_remote_servers()
        for record in existing:
            if record.catalog_item_id == catalog_item_id or record.endpoint == endpoint_norm:
                raise DuplicateRemoteServerError("指定のサーバーは既に登録されています")

        server_id = f"remote-{catalog_item_id}"
        if any(record.server_id == server_id for record in existing):
            server_id = f"{server_id}-{uuid4().hex[:8]}"

        server = RemoteServer(
            server_id=server_id,
            catalog_item_id=catalog_item_id,
            name=name,
            endpoint=endpoint_norm,
            status=RemoteServerStatus.REGISTERED,
            created_at=datetime.now(timezone.utc),
        )
        await self.save_server(server)

        self._record_audit(
            event_type="server_registered",
            correlation_id=correlation_id or server_id,
            metadata={
                "server_id": server_id,
                "catalog_item_id": catalog_item_id,
                "endpoint": endpoint_norm,
            },
        )

        return server

    async def save_server(self, server: RemoteServer) -> RemoteServer:
        """remote_servers へ保存（INSERT/REPLACE）する。"""
        record = self._to_record(server)
        self._state_store.save_remote_server(record)
        return server

    async def connect(self, server_id: str) -> dict:
        """
        リモート MCP サーバーへ SSE 接続し、capabilities を返す。

        - 許可リスト検証を接続前に実施
        - 同時接続数をセマフォで制御（上限超過時は TooManyConnectionsError）
        - 接続・初期化はタイムアウト付きで実行
        """
        server = await self._require_server(server_id)
        if server.status == RemoteServerStatus.DISABLED:
            raise RemoteMcpError("サーバーが無効化されています")

        if not self._state_store.is_endpoint_allowed(server.endpoint):
            parsed = urlparse(server.endpoint)
            host = parsed.hostname or ""
            port = parsed.port or (443 if (parsed.scheme or "").lower() == "https" else 80)
            self._record_audit(
                event_type="endpoint_rejected",
                correlation_id=server_id,
                metadata={
                    "server_id": server_id,
                    "endpoint": server.endpoint,
                    "reason": "not_in_allowlist",
                },
            )
            raise EndpointNotAllowedError(
                f"Endpoint not allowed: {host}:{port} is not in REMOTE_MCP_ALLOWED_DOMAINS"
            )

        acquired = False
        try:
            await self._try_acquire_connection_slot()
            acquired = True

            credential = await self.get_server_credential(server_id)
            headers = self._build_auth_headers(credential)

            if self._sse_client_factory is None:
                raise RemoteMcpError("SSE クライアントが設定されていません")

            async with self._http_client_factory() as http_client:
                transport = self._sse_client_factory(
                    server.endpoint,
                    headers=headers,
                    client=http_client,
                )
                async with transport as client:
                    session = await asyncio.wait_for(
                        client.connect(), timeout=self._connect_timeout
                    )
                    capabilities = await asyncio.wait_for(
                        session.initialize(), timeout=self._connect_timeout
                    )
                    await self._run_heartbeat(session)

            await self.set_status(
                server_id=server_id,
                status=RemoteServerStatus.AUTHENTICATED,
                last_connected_at=datetime.now(timezone.utc),
                error_message="",
            )
            self._record_audit(
                event_type="server_authenticated",
                correlation_id=server_id,
                metadata={"server_id": server_id, "endpoint": server.endpoint},
            )
            return capabilities
        except Exception as exc:  # noqa: BLE001
            await self.set_status(
                server_id=server_id,
                status=RemoteServerStatus.ERROR,
                error_message=str(exc),
            )
            self._record_audit(
                event_type="connection_failed",
                correlation_id=server_id,
                metadata={
                    "server_id": server_id,
                    "endpoint": server.endpoint,
                    "error": str(exc),
                },
            )
            raise
        finally:
            # セマフォを取得できた場合のみ解放する
            if acquired:
                self._connection_semaphore.release()

    async def test_connection(self, server_id: str) -> dict:
        """
        リモート MCP サーバーへの到達性と認証状態を検証する。

        - allowlist や同時接続上限の検証は connect() と同一
        - 既知の入力エラーは上位へ送出し、その他の失敗は reachable=False で返す
        """
        try:
            capabilities = await self.connect(server_id)
            return {"reachable": True, "authenticated": True, "capabilities": capabilities}
        except (
            EndpointNotAllowedError,
            RemoteServerNotFoundError,
            TooManyConnectionsError,
            CredentialNotFoundError,
        ):
            # HTTP レイヤーで適切なステータスに変換させる
            raise
        except Exception as exc:  # noqa: BLE001
            return {"reachable": False, "authenticated": False, "error": str(exc)}

    async def list_servers(self) -> List[RemoteServer]:
        """登録済みリモートサーバーを全件取得する。"""
        records = self._state_store.list_remote_servers()
        return [self._from_record(record) for record in records]

    async def get_server(self, server_id: str) -> Optional[RemoteServer]:
        """server_id からリモートサーバーを取得する。存在しない場合は None。"""
        record = self._state_store.get_remote_server(server_id)
        if record is None:
            return None
        return self._from_record(record)

    async def delete_server(
        self,
        server_id: str,
        *,
        delete_credentials: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """指定されたリモートサーバーを削除する。存在しない場合は例外。"""
        server = await self._require_server(server_id)

        if delete_credentials and server.credential_key:
            self._state_store.delete_credential(server.credential_key)

        self._state_store.delete_remote_server(server_id)
        self._record_audit(
            event_type="server_deleted",
            correlation_id=correlation_id or server_id,
            metadata={
                "server_id": server_id,
                "catalog_item_id": server.catalog_item_id,
                "delete_credentials": bool(delete_credentials and server.credential_key),
            },
        )

    async def revoke_credentials(
        self, server_id: str, *, correlation_id: Optional[str] = None
    ) -> RemoteServer:
        """サーバーに紐づく資格情報を削除し、認証待ち状態へ遷移させる。"""
        server = await self._require_server(server_id)

        if not server.credential_key:
            raise CredentialNotFoundError("credential_key が設定されていません")

        self._state_store.delete_credential(server.credential_key)
        updated = await self.set_status(
            server_id=server_id,
            status=RemoteServerStatus.AUTH_REQUIRED,
            credential_key=None,
            error_message="",
        )

        self._record_audit(
            event_type="credentials_revoked",
            correlation_id=correlation_id or server_id,
            metadata={
                "server_id": server_id,
                "catalog_item_id": server.catalog_item_id,
            },
        )
        return updated

    async def enable_server(
        self,
        server_id: str,
        *,
        requires_auth: bool = True,
        correlation_id: Optional[str] = None,
    ) -> RemoteServer:
        """サーバーを有効化し、必要に応じて認証待ち状態へ遷移させる。"""
        server = await self._require_server(server_id)
        previous_status = server.status

        if server.credential_key:
            new_status = RemoteServerStatus.AUTHENTICATED
        elif requires_auth:
            new_status = RemoteServerStatus.AUTH_REQUIRED
        else:
            new_status = RemoteServerStatus.REGISTERED

        updated = await self.set_status(
            server_id=server_id,
            status=new_status,
            error_message="",
        )

        self._record_audit(
            event_type="server_enabled",
            correlation_id=correlation_id or server_id,
            metadata={
                "server_id": server_id,
                "from_status": previous_status.value,
                "to_status": new_status.value,
                "requires_auth": requires_auth,
            },
        )

        return updated

    async def disable_server(
        self,
        server_id: str,
        *,
        correlation_id: Optional[str] = None,
    ) -> RemoteServer:
        """サーバーを無効化し、ランタイム統合を停止状態へ遷移させる。"""
        server = await self._require_server(server_id)
        previous_status = server.status

        updated = await self.set_status(
            server_id=server_id,
            status=RemoteServerStatus.DISABLED,
            last_connected_at=None,
            error_message="",
        )

        self._record_audit(
            event_type="server_disabled",
            correlation_id=correlation_id or server_id,
            metadata={
                "server_id": server_id,
                "from_status": previous_status.value,
                "to_status": RemoteServerStatus.DISABLED.value,
            },
        )

        return updated

    async def set_status(
        self,
        server_id: str,
        status: RemoteServerStatus,
        *,
        credential_key: object = _UNSET,
        last_connected_at: object = _UNSET,
        error_message: object = _UNSET,
    ) -> RemoteServer:
        """ステータスや紐づく credential_key 等を更新する。"""
        server = await self._require_server(server_id)

        updates: dict[str, object] = {"status": status}
        if credential_key is not _UNSET:
            updates["credential_key"] = credential_key
        if last_connected_at is not _UNSET:
            updates["last_connected_at"] = last_connected_at
        if error_message is not _UNSET:
            updates["error_message"] = error_message

        updated = server.model_copy(update=updates)
        await self.save_server(updated)
        return updated

    async def get_server_credential(self, server_id: str) -> CredentialRecord:
        """server_id に紐づく資格情報を取得する。存在しない場合は例外。"""
        server = await self._require_server(server_id)
        credential_key = server.credential_key
        if not credential_key:
            raise CredentialNotFoundError("credential_key が設定されていません")

        record = self._state_store.get_credential(credential_key)
        if record is None or record.server_id != server_id:
            raise CredentialNotFoundError("credential_key が server_id に紐づいていません")
        return record

    async def _require_server(self, server_id: str) -> RemoteServer:
        """存在確認付きでサーバーを取得する。"""
        server = await self.get_server(server_id)
        if server is None:
            raise RemoteServerNotFoundError("server_id が存在しません")
        return server

    def _to_record(self, server: RemoteServer) -> RemoteServerRecord:
        """ドメインモデルを永続化レコードへ変換する。"""
        return RemoteServerRecord(
            server_id=server.server_id,
            catalog_item_id=server.catalog_item_id,
            name=server.name,
            endpoint=server.endpoint,
            status=server.status.value,
            credential_key=server.credential_key,
            last_connected_at=server.last_connected_at,
            error_message=server.error_message,
            created_at=server.created_at,
        )

    def _from_record(self, record: RemoteServerRecord) -> RemoteServer:
        """永続化レコードをドメインモデルへ変換する。"""
        return RemoteServer(
            server_id=record.server_id,
            catalog_item_id=record.catalog_item_id,
            name=record.name,
            endpoint=record.endpoint,
            status=RemoteServerStatus(record.status),
            credential_key=record.credential_key,
            last_connected_at=record.last_connected_at,
            error_message=record.error_message,
            created_at=record.created_at,
        )

    def _record_audit(self, event_type: str, correlation_id: str, metadata: dict) -> None:
        """監査ログを安全に記録する。"""
        try:
            self._state_store.record_audit_log(
                event_type=event_type, correlation_id=correlation_id, metadata=metadata
            )
        except Exception:
            logger.warning("監査ログの記録に失敗しました", exc_info=True)

    async def _try_acquire_connection_slot(self) -> None:
        """同時接続セマフォを即時取得し、失敗時は TooManyConnectionsError を送出する。"""
        try:
            await asyncio.wait_for(self._connection_semaphore.acquire(), timeout=0)
        except asyncio.TimeoutError as exc:
            raise TooManyConnectionsError("同時接続上限を超えています") from exc

    @staticmethod
    def _get_max_connections() -> int:
        """環境変数 REMOTE_MCP_MAX_CONNECTIONS から上限を取得する。未設定時は 5 を既定とする。"""
        raw = os.getenv("REMOTE_MCP_MAX_CONNECTIONS")
        if raw:
            try:
                value = int(raw)
                return max(1, value)
            except ValueError:
                logger.warning("REMOTE_MCP_MAX_CONNECTIONS が不正なため既定値 5 を使用します: %s", raw)
        return 5

    @staticmethod
    def _default_http_client_factory() -> httpx.AsyncClient:
        """SSE 接続用の httpx.AsyncClient を生成する。"""
        return httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    def _build_auth_headers(self, credential: CredentialRecord) -> dict:
        """credential から Authorization ヘッダーを組み立てる。"""
        token_value = None
        if self._oauth_service and hasattr(self._oauth_service, "_decrypt_token_ref"):
            try:
                secret = self._oauth_service._decrypt_token_ref(credential.token_ref)  # type: ignore[attr-defined]
                token_value = secret.get("access_token")
            except Exception:
                logger.debug("token_ref の復号に失敗しました", exc_info=True)

        if token_value is None:
            token_value = credential.token_ref.get("access_token") or credential.token_ref.get("value")

        headers: dict[str, str] = {}
        if token_value:
            headers["Authorization"] = f"Bearer {token_value}"
        return headers

    async def _run_heartbeat(self, session: object) -> None:
        """
        心拍（ping）を送信し、接続ヘルスを確認する。

        120 秒間隔を想定するが、ここでは初回接続時に 1 度送信して
        SSE セッションが疎通できることを検証する。
        """
        if not hasattr(session, "ping"):
            return
        try:
            await asyncio.wait_for(session.ping(), timeout=self._idle_timeout)
        except Exception as exc:  # noqa: BLE001
            raise RemoteMcpError("SSE heartbeat failed") from exc
