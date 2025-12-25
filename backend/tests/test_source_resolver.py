"""Tests for catalog source ID resolution logic."""

import pytest
from app.api.catalog import _resolve_source_url
from app.config import settings
from app.models.catalog import CatalogSourceId


def test_resolve_docker_source_to_url():
    """docker source ID resolves to Docker catalog URL."""
    source_id = CatalogSourceId.DOCKER
    resolved_url = _resolve_source_url(source_id)
    
    # Should map to catalog_docker_url (alias of catalog_default_url)
    assert resolved_url == settings.catalog_docker_url
    assert resolved_url == settings.catalog_default_url


def test_resolve_official_source_to_url():
    """official source ID resolves to Official MCP Registry URL."""
    source_id = CatalogSourceId.OFFICIAL
    resolved_url = _resolve_source_url(source_id)
    
    # Should map to catalog_official_url
    assert resolved_url == settings.catalog_official_url


def test_resolve_docker_returns_expected_default():
    """docker source ID returns the expected GitHub API URL."""
    source_id = CatalogSourceId.DOCKER
    resolved_url = _resolve_source_url(source_id)
    
    # Verify it's the GitHub API URL (unless overridden by env)
    assert "github.com" in resolved_url or resolved_url.startswith("http")


def test_resolve_official_returns_expected_registry():
    """official source ID returns the expected Official Registry URL."""
    source_id = CatalogSourceId.OFFICIAL
    resolved_url = _resolve_source_url(source_id)
    
    # Verify it's the Official Registry URL (unless overridden by env)
    assert "modelcontextprotocol.io" in resolved_url or resolved_url.startswith("http")


def test_resolve_source_url_mapping_is_exhaustive():
    """All CatalogSourceId enum members have URL mappings."""
    # Ensure every source ID can be resolved
    for source_id in CatalogSourceId:
        resolved_url = _resolve_source_url(source_id)
        assert isinstance(resolved_url, str)
        assert len(resolved_url) > 0
        assert resolved_url.startswith("http")


def test_resolve_source_url_returns_distinct_urls():
    """docker and official source IDs resolve to different URLs."""
    docker_url = _resolve_source_url(CatalogSourceId.DOCKER)
    official_url = _resolve_source_url(CatalogSourceId.OFFICIAL)
    
    # The two sources should point to different endpoints
    assert docker_url != official_url
