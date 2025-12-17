import pytest

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
