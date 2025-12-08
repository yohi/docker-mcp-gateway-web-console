
import pytest
from pydantic import ValidationError

from app.schemas.catalog import RegistryItem

class TestRegistryItem:
    """Test suite for RegistryItem schema."""

    def test_import(self):
        """Test that RegistryItem can be imported."""
        assert RegistryItem is not None, "app.schemas.catalog.RegistryItem not found"

    def test_registry_item_valid(self):
        """Test creating a valid RegistryItem."""
        data = {
            "name": "fetch",
            "description": "Web fetch tool",
            "vendor": "Docker Inc.",
            "image": "docker/mcp-fetch:latest",
            "required_envs": ["API_KEY"]
        }
        item = RegistryItem(**data)
        assert item.name == "fetch"
        assert item.description == "Web fetch tool"
        assert item.vendor == "Docker Inc."
        assert item.image == "docker/mcp-fetch:latest"
        assert item.required_envs == ["API_KEY"]

    def test_registry_item_optional_fields(self):
        """Test RegistryItem with optional fields missing (if any)."""
        # Assuming required_envs is optional default to []
        data = {
            "name": "minimal",
            "description": "Minimal tool",
            "vendor": "Someone",
            "image": "minimal/image:latest"
        }
        item = RegistryItem(**data)
        assert item.name == "minimal"
        assert item.required_envs == []

    def test_registry_item_missing_required(self):
        """Test missing required fields."""
        data = {
            "name": "incomplete"
        }
        with pytest.raises(ValidationError):
            RegistryItem(**data)
