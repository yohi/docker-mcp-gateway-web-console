"""Tests for catalog source identifier enum."""

import pytest
from app.models.catalog import CatalogSourceId


def test_catalog_source_id_values():
    """CatalogSourceId exposes the expected preset values."""
    assert CatalogSourceId.DOCKER.value == "docker"
    assert CatalogSourceId.OFFICIAL.value == "official"


def test_catalog_source_id_string_behavior():
    """CatalogSourceId behaves like a string enum."""
    assert isinstance(CatalogSourceId.DOCKER, str)
    assert CatalogSourceId.DOCKER == "docker"


def test_catalog_source_id_accepts_valid_docker():
    """CatalogSourceId accepts valid 'docker' value."""
    source_id = CatalogSourceId("docker")
    assert source_id == CatalogSourceId.DOCKER
    assert source_id.value == "docker"


def test_catalog_source_id_accepts_valid_official():
    """CatalogSourceId accepts valid 'official' value."""
    source_id = CatalogSourceId("official")
    assert source_id == CatalogSourceId.OFFICIAL
    assert source_id.value == "official"


def test_catalog_source_id_rejects_invalid_value():
    """CatalogSourceId rejects invalid values."""
    with pytest.raises(ValueError):
        CatalogSourceId("invalid")


def test_catalog_source_id_rejects_empty_string():
    """CatalogSourceId rejects empty string."""
    with pytest.raises(ValueError):
        CatalogSourceId("")


def test_catalog_source_id_rejects_none():
    """CatalogSourceId rejects None value."""
    with pytest.raises((ValueError, TypeError)):
        CatalogSourceId(None)


def test_catalog_source_id_rejects_arbitrary_url():
    """CatalogSourceId rejects arbitrary URL strings."""
    with pytest.raises(ValueError):
        CatalogSourceId("https://example.com/catalog")


def test_catalog_source_id_rejects_mixed_case():
    """CatalogSourceId rejects mixed case values (case-sensitive)."""
    with pytest.raises(ValueError):
        CatalogSourceId("Docker")
    with pytest.raises(ValueError):
        CatalogSourceId("OFFICIAL")
