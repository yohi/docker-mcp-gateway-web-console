"""Tests for Secret Manager service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.secrets import SecretManager


class TestSecretManager:
    """Test suite for SecretManager."""

    @pytest.fixture
    def secret_manager(self):
        """Create a SecretManager instance for testing."""
        return SecretManager()

    def test_is_valid_reference(self, secret_manager):
        """Test validation of Bitwarden reference notation."""
        # Valid references
        assert secret_manager.is_valid_reference("{{ bw:abc123:password }}")
        assert secret_manager.is_valid_reference("{{bw:item-id:field}}")
        assert secret_manager.is_valid_reference("{{ bw:a1b2c3:username }}")
        
        # Invalid references
        assert not secret_manager.is_valid_reference("invalid")
        assert not secret_manager.is_valid_reference("{{ bw:only-one }}")
        assert not secret_manager.is_valid_reference("bw:abc:def")

    def test_parse_reference_valid(self, secret_manager):
        """Test parsing of valid Bitwarden references."""
        item_id, field = secret_manager.parse_reference("{{ bw:abc123:password }}")
        assert item_id == "abc123"
        assert field == "password"
        
        item_id, field = secret_manager.parse_reference("{{bw:item-id:field}}")
        assert item_id == "item-id"
        assert field == "field"

    def test_parse_reference_invalid(self, secret_manager):
        """Test error handling for invalid references."""
        with pytest.raises(ValueError):
            secret_manager.parse_reference("invalid")
        
        with pytest.raises(ValueError):
            secret_manager.parse_reference("{{ bw:only-one }}")

    @pytest.mark.asyncio
    async def test_cache_operations(self, secret_manager):
        """Test cache set and get operations."""
        session_id = "test-session"
        key = "item123:password"
        value = "secret-value"
        
        # Initially, cache should be empty
        cached = await secret_manager.get_from_cache(key, session_id)
        assert cached is None
        
        # Set cache
        await secret_manager.set_cache(key, value, session_id)
        
        # Retrieve from cache
        cached = await secret_manager.get_from_cache(key, session_id)
        assert cached == value

    @pytest.mark.asyncio
    async def test_cache_expiry(self, secret_manager):
        """Test that cache entries expire correctly."""
        session_id = "test-session"
        key = "item123:password"
        value = "secret-value"
        
        # Set cache with very short TTL
        secret_manager._cache_ttl = timedelta(seconds=0)
        await secret_manager.set_cache(key, value, session_id)
        
        # Cache should be expired immediately
        cached = await secret_manager.get_from_cache(key, session_id)
        assert cached is None

    def test_clear_session_cache(self, secret_manager):
        """Test clearing session cache."""
        session_id = "test-session"
        secret_manager._cache[session_id] = {
            "key1": ("value1", datetime.now() + timedelta(hours=1)),
            "key2": ("value2", datetime.now() + timedelta(hours=1))
        }
        
        secret_manager.clear_session_cache(session_id)
        
        assert session_id not in secret_manager._cache

    def test_extract_field_value_login_fields(self, secret_manager):
        """Test extraction of login fields from Bitwarden item data."""
        item_data = {
            "login": {
                "password": "test-password",
                "username": "test-user",
                "totp": "test-totp"
            },
            "notes": "test-notes"
        }
        
        assert secret_manager._extract_field_value(item_data, "password") == "test-password"
        assert secret_manager._extract_field_value(item_data, "username") == "test-user"
        assert secret_manager._extract_field_value(item_data, "totp") == "test-totp"
        assert secret_manager._extract_field_value(item_data, "notes") == "test-notes"

    def test_extract_field_value_custom_fields(self, secret_manager):
        """Test extraction of custom fields from Bitwarden item data."""
        item_data = {
            "fields": [
                {"name": "api_key", "value": "test-api-key"},
                {"name": "secret_token", "value": "test-token"}
            ]
        }
        
        assert secret_manager._extract_field_value(item_data, "api_key") == "test-api-key"
        assert secret_manager._extract_field_value(item_data, "secret_token") == "test-token"

    def test_extract_field_value_not_found(self, secret_manager):
        """Test extraction returns None for non-existent fields."""
        item_data = {"login": {"password": "test"}}
        
        assert secret_manager._extract_field_value(item_data, "nonexistent") is None

    @pytest.mark.asyncio
    async def test_resolve_all_simple(self, secret_manager):
        """Test resolving references in a simple configuration."""
        config = {
            "API_KEY": "plain-value",
            "PASSWORD": "{{ bw:item123:password }}",
            "PORT": "8080"
        }
        
        session_id = "test-session"
        bw_session_key = "test-bw-key"
        
        # Mock the resolve_reference method
        async def mock_resolve(ref, sid, bw_key):
            if ref == "{{ bw:item123:password }}":
                return "resolved-password"
            return ref
        
        secret_manager.resolve_reference = mock_resolve
        
        resolved = await secret_manager.resolve_all(config, session_id, bw_session_key)
        
        assert resolved["API_KEY"] == "plain-value"
        assert resolved["PASSWORD"] == "resolved-password"
        assert resolved["PORT"] == "8080"

    @pytest.mark.asyncio
    async def test_resolve_all_nested(self, secret_manager):
        """Test resolving references in nested configuration."""
        config = {
            "database": {
                "host": "localhost",
                "password": "{{ bw:db-item:password }}"
            },
            "api": {
                "key": "{{ bw:api-item:key }}"
            }
        }
        
        session_id = "test-session"
        bw_session_key = "test-bw-key"
        
        # Mock the resolve_reference method
        async def mock_resolve(ref, sid, bw_key):
            if ref == "{{ bw:db-item:password }}":
                return "db-password"
            elif ref == "{{ bw:api-item:key }}":
                return "api-key"
            return ref
        
        secret_manager.resolve_reference = mock_resolve
        
        resolved = await secret_manager.resolve_all(config, session_id, bw_session_key)
        
        assert resolved["database"]["password"] == "db-password"
        assert resolved["api"]["key"] == "api-key"

    @pytest.mark.asyncio
    async def test_resolve_all_with_lists(self, secret_manager):
        """Test resolving references in lists."""
        config = {
            "secrets": [
                "{{ bw:item1:password }}",
                "plain-value",
                "{{ bw:item2:key }}"
            ]
        }
        
        session_id = "test-session"
        bw_session_key = "test-bw-key"
        
        # Mock the resolve_reference method
        async def mock_resolve(ref, sid, bw_key):
            if ref == "{{ bw:item1:password }}":
                return "password1"
            elif ref == "{{ bw:item2:key }}":
                return "key2"
            return ref
        
        secret_manager.resolve_reference = mock_resolve
        
        resolved = await secret_manager.resolve_all(config, session_id, bw_session_key)
        
        assert resolved["secrets"] == ["password1", "plain-value", "key2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
