"""Tests for catalog source identifier enum."""

from app.models.catalog import CatalogSourceId


def test_catalog_source_id_values():
    """CatalogSourceId exposes the expected preset values."""
    assert CatalogSourceId.DOCKER.value == "docker"
    assert CatalogSourceId.OFFICIAL.value == "official"


def test_catalog_source_id_string_behavior():
    """CatalogSourceId behaves like a string enum."""
    assert isinstance(CatalogSourceId.DOCKER, str)
    assert CatalogSourceId.DOCKER == "docker"
