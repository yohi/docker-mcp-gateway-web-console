"""Property-based tests for configuration service."""

import pytest
from hypothesis import given, strategies as st
import tempfile
from pathlib import Path
import json
from unittest.mock import patch, Mock

from app.models.config import GatewayConfig, ServerConfig
from app.services.config import ConfigService, ConfigError


# Strategies
@st.composite
def valid_server_config_strategy(draw):
    """Generate a valid ServerConfig."""
    name = draw(st.text(min_size=1).map(lambda x: x.strip()).filter(lambda x: len(x) > 0))
    container_id = draw(st.text(min_size=1).map(lambda x: x.strip()).filter(lambda x: len(x) > 0))
    enabled = draw(st.booleans())
    # Simple config dict
    config = draw(st.dictionaries(st.text(min_size=1), st.text()))
    
    return ServerConfig(
        name=name,
        container_id=container_id,
        enabled=enabled,
        config=config
    )

@st.composite
def valid_gateway_config_strategy(draw):
    """Generate a valid GatewayConfig with unique server names and container IDs."""
    version = draw(st.text(min_size=1).map(lambda x: x.strip()).filter(lambda x: len(x) > 0))
    global_settings = draw(st.dictionaries(st.text(min_size=1), st.text()))
    
    # Generate list of servers ensuring uniqueness
    servers_list = draw(st.lists(valid_server_config_strategy(), max_size=10))
    
    # Filter to ensure uniqueness
    unique_servers = []
    seen_names = set()
    seen_ids = set()
    
    for server in servers_list:
        if server.name not in seen_names and server.container_id not in seen_ids:
            unique_servers.append(server)
            seen_names.add(server.name)
            seen_ids.add(server.container_id)
            
    return GatewayConfig(
        version=version,
        servers=unique_servers,
        global_settings=global_settings
    )


class TestConfigProperties:
    """Property-based tests for ConfigService."""

    @given(config=valid_gateway_config_strategy())
    @pytest.mark.asyncio
    async def test_settings_loading_property(self, config):
        """
        **Feature: docker-mcp-gateway-console, Property 17: 設定の読み込み**
        
        For any existing valid Gateway configuration file, the system should be able
        to correctly read and parse its content.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(config.model_dump_json())
            temp_path = Path(f.name)
            
        try:
            service = ConfigService(config_path=str(temp_path))
            loaded_config = await service.read_gateway_config()
            
            # Verify structure matches
            assert loaded_config.version == config.version
            assert len(loaded_config.servers) == len(config.servers)
            assert loaded_config.global_settings == config.global_settings
            
            # Verify server details (checking first one if exists)
            if config.servers:
                assert loaded_config.servers[0].name == config.servers[0].name
                assert loaded_config.servers[0].container_id == config.servers[0].container_id
                
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @given(config=valid_gateway_config_strategy())
    @pytest.mark.asyncio
    async def test_settings_roundtrip_property(self, config):
        """
        **Feature: docker-mcp-gateway-console, Property 18: 設定のラウンドトリップ**
        
        For any valid Gateway configuration, saving it and then reading it back
        should yield the identical configuration.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            service = ConfigService(config_path=str(temp_path))
            
            # Write
            success = await service.write_gateway_config(config)
            assert success is True
            
            # Read back
            loaded_config = await service.read_gateway_config()
            
            # Compare
            assert loaded_config.model_dump() == config.model_dump()
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
            # Clean up potential atomic write artifacts
            backup_files = list(temp_path.parent.glob(f"{temp_path.stem}.backup_*.json"))
            for b in backup_files:
                b.unlink()

    @given(config=valid_gateway_config_strategy())
    @pytest.mark.asyncio
    async def test_reject_invalid_config_property(self, config):
        """
        **Feature: docker-mcp-gateway-console, Property 19: 無効な設定の拒否**
        
        The system should reject configuration with duplicate server names or container IDs.
        """
        if not config.servers:
            return  # Skip empty server list
            
        service = ConfigService(config_path="dummy.json")
        
        # Create duplicate name scenario
        duplicate_name_config = config.model_copy(deep=True)
        # Add a duplicate of the first server
        duplicate_name_config.servers.append(
            ServerConfig(
                name=config.servers[0].name,
                container_id="unique-id-12345", # Different ID
                enabled=True
            )
        )
        
        # Validation should fail
        result = await service.validate_config(duplicate_name_config)
        assert result.valid is False
        assert any("duplicate server names" in e.lower() for e in result.errors)
        
        # Write attempt should raise ConfigError
        with pytest.raises(ConfigError):
            await service.write_gateway_config(duplicate_name_config)
            
        # Create duplicate ID scenario
        duplicate_id_config = config.model_copy(deep=True)
        duplicate_id_config.servers.append(
            ServerConfig(
                name="unique-name-12345", # Different name
                container_id=config.servers[0].container_id,
                enabled=True
            )
        )
        
        result = await service.validate_config(duplicate_id_config)
        assert result.valid is False
        assert any("duplicate container" in e.lower() for e in result.errors)

    @given(config=valid_gateway_config_strategy())
    @pytest.mark.asyncio
    async def test_write_failure_handling_property(self, config):
        """
        **Feature: docker-mcp-gateway-console, Property 20: 設定書き込み失敗のエラーハンドリング**
        
        If disk write fails (e.g. permission error), the system should handle it gracefully
        and raise an appropriate error.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            service = ConfigService(config_path=str(temp_path))
            
            # Simulate write permission error using patch on open
            # Note: We need to patch where open() is called.
            # Since ConfigService likely uses 'open' or 'aiofiles.open', we target that.
            # Assuming standard open for now based on typical implementation, or we can patch the write method itself partially?
            # Safer to patch the actual write operation or make the path read-only (but running as root/user might override).
            # Let's patch 'builtins.open' carefully or better, patch json.dump to fail.
            
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                 with pytest.raises(ConfigError) as exc_info:
                    await service.write_gateway_config(config)
                 
                 assert "failed to save" in str(exc_info.value).lower() or "permission denied" in str(exc_info.value).lower()

        finally:
            if temp_path.exists():
                temp_path.unlink()
