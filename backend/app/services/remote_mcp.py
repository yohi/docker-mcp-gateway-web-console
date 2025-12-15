"""リモート MCP サーバーを管理するサービス層。"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse
from uuid import uuid4

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


class RemoteMcpService:
    """リモート MCP サーバーの CRUD と資格情報取得を担当する。"""

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        oauth_service: Optional[object] = None,
    ) -> None:
        self._state_store = state_store or StateStore()
        self.state_store = self._state_store  # テスト用に公開
        self._oauth_service = oauth_service
        try:
            self._state_store.init_schema()
        except Exception:
            logger.debug("state store init skipped", exc_info=True)

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
