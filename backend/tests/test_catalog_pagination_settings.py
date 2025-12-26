"""Tests for Official Registry pagination settings."""

from app.config import Settings


def test_catalog_official_max_pages_default() -> None:
    """Test default value for CATALOG_OFFICIAL_MAX_PAGES."""
    settings = Settings(_env_file=None)

    assert settings.catalog_official_max_pages == 20


def test_catalog_official_max_pages_env_override(monkeypatch) -> None:
    """Test environment variable override for CATALOG_OFFICIAL_MAX_PAGES."""
    monkeypatch.setenv("CATALOG_OFFICIAL_MAX_PAGES", "50")

    settings = Settings(_env_file=None)

    assert settings.catalog_official_max_pages == 50


def test_catalog_official_fetch_timeout_default() -> None:
    """Test default value for CATALOG_OFFICIAL_FETCH_TIMEOUT."""
    settings = Settings(_env_file=None)

    assert settings.catalog_official_fetch_timeout == 60


def test_catalog_official_fetch_timeout_env_override(monkeypatch) -> None:
    """Test environment variable override for CATALOG_OFFICIAL_FETCH_TIMEOUT."""
    monkeypatch.setenv("CATALOG_OFFICIAL_FETCH_TIMEOUT", "120")

    settings = Settings(_env_file=None)

    assert settings.catalog_official_fetch_timeout == 120


def test_catalog_official_page_delay_default() -> None:
    """Test default value for CATALOG_OFFICIAL_PAGE_DELAY."""
    settings = Settings(_env_file=None)

    assert settings.catalog_official_page_delay == 100


def test_catalog_official_page_delay_env_override(monkeypatch) -> None:
    """Test environment variable override for CATALOG_OFFICIAL_PAGE_DELAY."""
    monkeypatch.setenv("CATALOG_OFFICIAL_PAGE_DELAY", "200")

    settings = Settings(_env_file=None)

    assert settings.catalog_official_page_delay == 200


def test_all_pagination_settings_together(monkeypatch) -> None:
    """Test all pagination settings can be set together."""
    monkeypatch.setenv("CATALOG_OFFICIAL_MAX_PAGES", "30")
    monkeypatch.setenv("CATALOG_OFFICIAL_FETCH_TIMEOUT", "90")
    monkeypatch.setenv("CATALOG_OFFICIAL_PAGE_DELAY", "150")

    settings = Settings(_env_file=None)

    assert settings.catalog_official_max_pages == 30
    assert settings.catalog_official_fetch_timeout == 90
    assert settings.catalog_official_page_delay == 150
