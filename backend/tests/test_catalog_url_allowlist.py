import pytest

from app.config import Settings
from app.models.catalog import CatalogErrorCode
from app.services.catalog import AllowedURLsValidator, CatalogError


def _settings_with_catalog_urls(
    monkeypatch: pytest.MonkeyPatch, *, docker_url: str, official_url: str
) -> Settings:
    monkeypatch.setenv("CATALOG_DEFAULT_URL", docker_url)
    monkeypatch.setenv("CATALOG_OFFICIAL_URL", official_url)
    return Settings(_env_file=None)


def test_allowed_urls_validator_accepts_normalized_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_with_catalog_urls(
        monkeypatch,
        docker_url="https://example.com/catalog",
        official_url="http://example.com:80/official/",
    )
    validator = AllowedURLsValidator(settings)

    assert (
        validator.validate("https://example.com/catalog/")
        == "https://example.com/catalog"
    )
    assert (
        validator.validate("http://example.com/official")
        == "http://example.com/official"
    )


def test_allowed_urls_validator_rejects_unlisted_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_with_catalog_urls(
        monkeypatch,
        docker_url="https://example.com/catalog",
        official_url="https://example.com/official",
    )
    validator = AllowedURLsValidator(settings)

    with pytest.raises(CatalogError) as exc:
        validator.validate("https://evil.example.com/catalog")

    assert exc.value.error_code == CatalogErrorCode.INVALID_SOURCE


def test_allowed_urls_validator_rejects_non_http_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_with_catalog_urls(
        monkeypatch,
        docker_url="https://example.com/catalog",
        official_url="https://example.com/official",
    )
    validator = AllowedURLsValidator(settings)

    with pytest.raises(CatalogError) as exc:
        validator.validate("file:///etc/passwd")

    assert exc.value.error_code == CatalogErrorCode.INVALID_SOURCE


def test_allowed_urls_validator_normalizes_ipv6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings_with_catalog_urls(
        monkeypatch,
        docker_url="http://[::1]/",
        official_url="https://example.com/official",
    )
    validator = AllowedURLsValidator(settings)

    assert validator.validate("http://[0:0:0:0:0:0:0:1]") == "http://[::1]"


def test_allowed_urls_validator_rejects_non_default_port_not_in_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """デフォルト以外の明示ポートが許可リストに存在しない場合は拒否される"""
    settings = _settings_with_catalog_urls(
        monkeypatch,
        docker_url="https://example.com/catalog",
        official_url="https://example.com/official",
    )
    validator = AllowedURLsValidator(settings)

    with pytest.raises(CatalogError) as exc:
        validator.validate("https://example.com:8080/catalog")

    assert exc.value.error_code == CatalogErrorCode.INVALID_SOURCE


def test_allowed_urls_validator_accepts_explicit_port_in_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """許可リストに明示ポート付きURLが登録されている場合は一致する"""
    settings = _settings_with_catalog_urls(
        monkeypatch,
        docker_url="https://example.com:8443/catalog",
        official_url="https://example.com/official",
    )
    validator = AllowedURLsValidator(settings)

    assert (
        validator.validate("https://example.com:8443/catalog")
        == "https://example.com:8443/catalog"
    )
