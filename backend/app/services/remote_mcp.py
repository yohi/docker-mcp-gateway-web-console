"""リモート MCP サーバーを管理するサービス層。"""

import logging
from datetime import datetime
from typing import List, Optional

from ..models.remote import RemoteServer, RemoteServerStatus
from ..models.state import CredentialRecord, RemoteServerRecord
from .oauth import CredentialNotFoundError, RemoteServerNotFoundError
from .state_store import StateStore

logger = logging.getLogger(__name__)
_UNSET = object()


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

    async def delete_server(self, server_id: str) -> None:
        """指定されたリモートサーバーを削除する（存在しない場合は無視）。"""
        self._state_store.delete_remote_server(server_id)

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
