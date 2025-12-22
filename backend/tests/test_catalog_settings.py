"""Tests for catalog-related settings."""

from app.config import Settings


def test_catalog_official_url_default() -> None:
    settings = Settings(_env_file=None)

    assert (
        settings.catalog_official_url
        == "https://registry.modelcontextprotocol.io/v0/servers"
    )


def test_catalog_official_url_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CATALOG_OFFICIAL_URL", "https://example.com/registry")

    settings = Settings(_env_file=None)

    assert settings.catalog_official_url == "https://example.com/registry"


def test_catalog_docker_url_aliases_default(monkeypatch) -> None:
    monkeypatch.setenv("CATALOG_DEFAULT_URL", "https://example.com/docker")

    settings = Settings(_env_file=None)

    assert settings.catalog_default_url == "https://example.com/docker"
    assert settings.catalog_docker_url == "https://example.com/docker"
