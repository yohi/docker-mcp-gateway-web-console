"""
後方互換性テスト: 既存のカタログ機能が正常に動作することを確認する

このテストは、移行ガイドの内容と実装が一致していることを検証します。
具体的には以下の点を確認します:

1. 環境変数のマッピングと優先順位が移行ガイドの表と一致している
2. CATALOG_DEFAULT_URL が CATALOG_DOCKER_URL のエイリアスとして機能する
3. source パラメータ省略時にデフォルトで Docker ソースが使用される
4. Official Registry 不可時でも Docker ソースが利用可能
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import Settings
from app.services.catalog import CatalogError, CatalogErrorCode


class TestBackwardCompatibility:
    """後方互換性テストスイート"""

    @pytest.fixture
    def client(self):
        """テストクライアントを作成"""
        return TestClient(app)

    def test_catalog_default_url_is_docker_url_alias(self):
        """
        CATALOG_DOCKER_URL が CATALOG_DEFAULT_URL のエイリアスとして機能することを確認
        
        設計: 「catalog_docker_url は catalog_default_url のプロパティエイリアス」
        移行ガイド: 「`CATALOG_DOCKER_URL` が未設定の場合、`CATALOG_DEFAULT_URL` の値が使用されます（後方互換）」
        """
        # CATALOG_DEFAULT_URL のみ設定
        with patch.dict(os.environ, {
            "CATALOG_DEFAULT_URL": "https://api.github.com/repos/docker/mcp-registry/contents/servers",
        }, clear=True):
            settings = Settings()
            
            # catalog_docker_url が catalog_default_url のエイリアスとして機能することを確認
            assert settings.catalog_docker_url == settings.catalog_default_url
            assert settings.catalog_docker_url == "https://api.github.com/repos/docker/mcp-registry/contents/servers"

    def test_source_parameter_omitted_defaults_to_docker(self, client):
        """
        source パラメータ省略時にデフォルトで Docker ソースが使用されることを確認
        
        移行ガイド: 「デフォルトで "Docker" が選択されているため、既存ユーザーの体験は維持されます」
        要件: 2.2 「source 省略時は Docker」
        """
        # カタログサービスをモック
        with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
             patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
            
            mock_get_cache.return_value = None
            mock_fetch.return_value = ([], False)
            
            # source パラメータを省略してリクエスト
            response = client.get("/api/catalog")
            
            assert response.status_code == 200
            # fetch_catalog が Docker URL で呼ばれたことを確認
            called_url = mock_fetch.call_args[0][0]
            assert "docker" in called_url.lower() or "github.com" in called_url

    def test_official_registry_unavailable_docker_still_works(self, client):
        """
        Official Registry 不可時でも Docker ソースが利用可能であることを確認
        
        要件: 6.4 「Official MCP Registry が一時的に利用不可でも、DockerMCPCatalog は利用可能」
        """
        # Official Registry へのリクエストを失敗させる
        def mock_fetch_catalog(source_url: str, force_refresh: bool = False):
            if "modelcontextprotocol.io" in source_url:
                raise CatalogError(
                    error_code=CatalogErrorCode.UPSTREAM_UNAVAILABLE,
                    message="Official Registry is unavailable"
                )
            # Docker ソースは成功
            return ([], False)
        
        with patch("app.api.catalog.catalog_service.fetch_catalog", side_effect=mock_fetch_catalog), \
             patch("app.api.catalog.catalog_service.get_cached_catalog", return_value=None):
            
            # Official ソースは失敗
            response_official = client.get("/api/catalog?source=official")
            assert response_official.status_code == 503
            
            # Docker ソースは成功
            response_docker = client.get("/api/catalog?source=docker")
            assert response_docker.status_code == 200

    def test_environment_variable_mapping_matches_migration_guide(self):
        """
        環境変数のマッピングが移行ガイドの表と一致することを確認
        
        移行ガイド マッピング表:
        - CATALOG_OFFICIAL_URL: Official ソース選択時に使用
        - CATALOG_DOCKER_URL: Docker ソース選択時に使用（CATALOG_DEFAULT_URL のエイリアス）
        
        設計: catalog_docker_url は catalog_default_url のプロパティエイリアス
        """
        # ケース 1: CATALOG_DEFAULT_URL が設定されている場合
        with patch.dict(os.environ, {
            "CATALOG_DEFAULT_URL": "https://custom-docker.example.com",
        }, clear=True):
            settings = Settings()
            # catalog_docker_url は catalog_default_url のエイリアス
            assert settings.catalog_docker_url == "https://custom-docker.example.com"
            assert settings.catalog_docker_url == settings.catalog_default_url
        
        # ケース 2: CATALOG_OFFICIAL_URL が設定されている場合
        with patch.dict(os.environ, {
            "CATALOG_OFFICIAL_URL": "https://custom-official.example.com",
        }, clear=True):
            settings = Settings()
            # catalog_official_url は独立した設定
            assert settings.catalog_official_url == "https://custom-official.example.com"

    def test_next_public_catalog_url_is_ignored(self, client):
        """
        NEXT_PUBLIC_CATALOG_URL が無視されることを確認
        
        移行ガイド: 「`NEXT_PUBLIC_CATALOG_URL` は廃止 (Ignored)。フロントエンドはプリセット ID のみを送信」
        """
        # NEXT_PUBLIC_CATALOG_URL を設定（フロントエンド用環境変数だが念のため）
        with patch.dict(os.environ, {
            "NEXT_PUBLIC_CATALOG_URL": "https://should-be-ignored.example.com",
        }, clear=False):
            # カタログサービスをモック
            with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
                 patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
                
                mock_get_cache.return_value = None
                mock_fetch.return_value = ([], False)
                
                # source=docker でリクエスト
                response = client.get("/api/catalog?source=docker")
                
                assert response.status_code == 200
                # NEXT_PUBLIC_CATALOG_URL は使用されず、CATALOG_DOCKER_URL が使用される
                called_url = mock_fetch.call_args[0][0]
                assert "should-be-ignored.example.com" not in called_url

    def test_source_switching_without_page_reload(self, client):
        """
        ページリロードなしでソース切替が可能であることを確認
        
        要件: 6.5 「ユーザーがカタログソースを切り替える際、ページリロードなしで実行可能」
        """
        # カタログサービスをモック
        with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
             patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
            
            mock_get_cache.return_value = None
            mock_fetch.return_value = ([], False)
            
            # Docker ソースでリクエスト
            response_docker = client.get("/api/catalog?source=docker")
            assert response_docker.status_code == 200
            
            # Official ソースでリクエスト（同じクライアントセッション内）
            response_official = client.get("/api/catalog?source=official")
            assert response_official.status_code == 200
            
            # 両方のリクエストが成功し、異なる URL で呼ばれたことを確認
            assert mock_fetch.call_count == 2
            call_urls = [call[0][0] for call in mock_fetch.call_args_list]
            assert len(set(call_urls)) == 2  # 異なる URL が使用された

    def test_existing_client_compatibility(self, client):
        """
        既存クライアントの互換性を確認
        
        要件: 6.1 「既存クライアントが source を指定せずに GET /api/catalog を呼び出した場合、
        機能追加前のスキーマと互換性のあるレスポンスを返す」
        """
        # カタログサービスをモック
        with patch("app.api.catalog.catalog_service.fetch_catalog") as mock_fetch, \
             patch("app.api.catalog.catalog_service.get_cached_catalog") as mock_get_cache:
            
            mock_get_cache.return_value = None
            mock_fetch.return_value = ([], False)
            
            # source パラメータなしでリクエスト
            response = client.get("/api/catalog")
            
            assert response.status_code == 200
            # レスポンススキーマが既存と互換性があることを確認
            data = response.json()
            assert "servers" in data or "items" in data
            items_key = "servers" if "servers" in data else "items"
            assert isinstance(data[items_key], list)
