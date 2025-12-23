import pytest
from pydantic import ValidationError

from app.models.catalog import CatalogItem


class TestCatalogItem:
    """CatalogItem 拡張フィールドの挙動を検証するテスト."""

    def test_remote_endpoint_sets_remote_flags(self):
        """docker_image を持たないリモート項目では is_remote/server_type が派生する."""
        item = CatalogItem(
            id="remote-1",
            name="Remote Service",
            description="Remote endpoint only",
            vendor="",
            category="general",
            docker_image=None,
            remote_endpoint="https://api.example.com/sse",
        )

        assert str(item.remote_endpoint) == "https://api.example.com/sse"
        assert item.is_remote is True
        assert item.server_type == "remote"

    def test_docker_image_is_preferred_over_remote_endpoint(self):
        """docker_image があればリモート情報があっても docker 優先になる."""
        item = CatalogItem(
            id="docker-1",
            name="Docker Server",
            description="Has docker image and remote endpoint",
            vendor="",
            category="general",
            docker_image="docker/image:latest",
            remote_endpoint="https://api.example.com/sse",
        )

        assert item.docker_image == "docker/image:latest"
        assert str(item.remote_endpoint) == "https://api.example.com/sse"
        assert item.is_remote is False
        assert item.server_type == "docker"

    def test_blank_docker_image_treated_as_missing(self):
        """空白 docker_image はリモート扱いにフォールバックする."""
        item = CatalogItem(
            id="remote-blank",
            name="Remote With Blank Docker",
            description="Blank docker_image should not disable remote detection",
            vendor="",
            category="general",
            docker_image="  ",
            remote_endpoint="https://api.example.com/sse",
        )

        assert item.docker_image == "  "
        assert item.is_remote is True
        assert item.server_type == "remote"

    def test_oauth_config_is_optional_and_preserved(self):
        """oauth_config が任意で保存される."""
        oauth_config = {"scopes": ["read:all"], "client_id": "client-123"}

        item = CatalogItem(
            id="remote-oauth",
            name="Remote OAuth Server",
            description="Remote with oauth config",
            vendor="",
            category="general",
            docker_image=None,
            remote_endpoint="https://auth.example.com/sse",
            oauth_config=oauth_config,
        )

        assert item.oauth_config == oauth_config
        assert item.is_remote is True
        assert item.server_type == "remote"

    def test_allowed_url_schemes(self):
        """許可されたスキーム（https, wss, http, ws）が正常に機能する."""
        allowed_schemes = [
            "https://example.com/sse",
            "wss://example.com/ws",
            "http://example.com/sse",
            "ws://example.com/ws",
        ]

        for url in allowed_schemes:
            item = CatalogItem(
                id=f"test-{url.split(':')[0]}",
                name="Test Server",
                description="Test allowed scheme",
                vendor="",
                category="general",
                remote_endpoint=url,
            )
            assert str(item.remote_endpoint) == url
            assert item.is_remote is True

    def test_disallowed_url_schemes_file(self):
        """file:// スキームはモデルレベルで拒否される."""
        with pytest.raises(ValidationError) as exc_info:
            CatalogItem(
                id="test-file",
                name="Test Server",
                description="Test disallowed file scheme",
                vendor="",
                category="general",
                remote_endpoint="file:///etc/passwd",
            )

        error = exc_info.value
        assert "remote_endpoint" in str(error)

    def test_disallowed_url_schemes_ftp(self):
        """ftp:// スキームはモデルレベルで拒否される."""
        with pytest.raises(ValidationError) as exc_info:
            CatalogItem(
                id="test-ftp",
                name="Test Server",
                description="Test disallowed ftp scheme",
                vendor="",
                category="general",
                remote_endpoint="ftp://example.com/file",
            )

        error = exc_info.value
        assert "remote_endpoint" in str(error)

    def test_disallowed_url_schemes_data(self):
        """data:// スキームはモデルレベルで拒否される."""
        with pytest.raises(ValidationError) as exc_info:
            CatalogItem(
                id="test-data",
                name="Test Server",
                description="Test disallowed data scheme",
                vendor="",
                category="general",
                remote_endpoint="data:text/plain;base64,SGVsbG8=",
            )

        error = exc_info.value
        assert "remote_endpoint" in str(error)
