"""Tests for Config Service."""

import json
import tempfile
from pathlib import Path

import pytest

from app.models.config import GatewayConfig, ServerConfig
from app.services.config import ConfigError, ConfigService


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()
    
    # Also cleanup any backup files
    for backup in temp_path.parent.glob(f"{temp_path.stem}.backup_*.json"):
        backup.unlink()


@pytest.fixture
def config_service(temp_config_file):
    """Create a ConfigService instance with a temporary file."""
    return ConfigService(config_path=str(temp_config_file))


@pytest.fixture
def sample_gateway_config():
    """Sample gateway configuration for testing."""
    return GatewayConfig(
        version="1.0",
        servers=[
            ServerConfig(
                name="test-server-1",
                container_id="abc123",
                enabled=True,
                config={
                    "port": 8080,
                    "api_key": "{{ bw:item-1:api_key }}"
                }
            ),
            ServerConfig(
                name="test-server-2",
                container_id="def456",
                enabled=False,
                config={
                    "model": "gpt-4"
                }
            )
        ],
        global_settings={
            "log_level": "INFO",
            "timeout": 30
        }
    )


class TestConfigService:
    """Test suite for ConfigService."""

    @pytest.mark.asyncio
    async def test_read_nonexistent_config(self, config_service):
        """Test reading config when file doesn't exist returns default."""
        config = await config_service.read_gateway_config()
        
        assert config is not None
        assert config.version == "1.0"
        assert len(config.servers) == 0
        assert config.global_settings == {}

    @pytest.mark.asyncio
    async def test_write_and_read_config(self, config_service, sample_gateway_config):
        """Test writing and reading configuration."""
        # Write config
        success = await config_service.write_gateway_config(sample_gateway_config)
        assert success is True
        
        # Read it back
        config = await config_service.read_gateway_config()
        
        assert config.version == sample_gateway_config.version
        assert len(config.servers) == len(sample_gateway_config.servers)
        assert config.servers[0].name == "test-server-1"
        assert config.servers[0].container_id == "abc123"
        assert config.servers[0].enabled is True
        assert config.servers[1].name == "test-server-2"
        assert config.servers[1].enabled is False
        assert config.global_settings == sample_gateway_config.global_settings

    @pytest.mark.asyncio
    async def test_config_roundtrip(self, config_service, sample_gateway_config):
        """Test that config survives write-read roundtrip."""
        # Write config
        await config_service.write_gateway_config(sample_gateway_config)
        
        # Read it back
        config = await config_service.read_gateway_config()
        
        # Should be identical
        assert config.model_dump() == sample_gateway_config.model_dump()

    @pytest.mark.asyncio
    async def test_validate_valid_config(self, config_service, sample_gateway_config):
        """Test validation of valid configuration."""
        result = await config_service.validate_config(sample_gateway_config)
        
        assert result.valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_duplicate_server_names(self, config_service):
        """Test validation fails with duplicate server names."""
        config = GatewayConfig(
            version="1.0",
            servers=[
                ServerConfig(name="server-1", container_id="abc123"),
                ServerConfig(name="server-1", container_id="def456")
            ]
        )
        
        result = await config_service.validate_config(config)
        
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("duplicate server names" in error.lower() for error in result.errors)

    @pytest.mark.asyncio
    async def test_validate_duplicate_container_ids(self, config_service):
        """Test validation fails with duplicate container IDs."""
        config = GatewayConfig(
            version="1.0",
            servers=[
                ServerConfig(name="server-1", container_id="abc123"),
                ServerConfig(name="server-2", container_id="abc123")
            ]
        )
        
        result = await config_service.validate_config(config)
        
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("duplicate container" in error.lower() for error in result.errors)

    @pytest.mark.asyncio
    async def test_validate_empty_servers_warning(self, config_service):
        """Test validation warns when no servers configured."""
        config = GatewayConfig(version="1.0", servers=[])
        
        result = await config_service.validate_config(config)
        
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("no servers" in warning.lower() for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_all_disabled_warning(self, config_service):
        """Test validation warns when all servers are disabled."""
        config = GatewayConfig(
            version="1.0",
            servers=[
                ServerConfig(name="server-1", container_id="abc123", enabled=False),
                ServerConfig(name="server-2", container_id="def456", enabled=False)
            ]
        )
        
        result = await config_service.validate_config(config)
        
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("all servers are disabled" in warning.lower() for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_bitwarden_reference_warning(self, config_service):
        """Test validation warns about Bitwarden references."""
        config = GatewayConfig(
            version="1.0",
            servers=[
                ServerConfig(
                    name="server-1",
                    container_id="abc123",
                    config={"api_key": "{{ bw:item-1:api_key }}"}
                )
            ]
        )
        
        result = await config_service.validate_config(config)
        
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("bitwarden" in warning.lower() for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_write_invalid_config_fails(self, config_service):
        """Test writing invalid config fails."""
        config = GatewayConfig(
            version="1.0",
            servers=[
                ServerConfig(name="server-1", container_id="abc123"),
                ServerConfig(name="server-1", container_id="def456")  # Duplicate name
            ]
        )
        
        with pytest.raises(ConfigError) as exc_info:
            await config_service.write_gateway_config(config)
        
        assert "validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_read_invalid_json(self, config_service, temp_config_file):
        """Test reading file with invalid JSON."""
        # Write invalid JSON
        with open(temp_config_file, "w") as f:
            f.write("{ invalid json }")
        
        with pytest.raises(ConfigError) as exc_info:
            await config_service.read_gateway_config()
        
        assert "invalid json" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_read_invalid_config_format(self, config_service, temp_config_file):
        """Test reading file with invalid config format."""
        # Write valid JSON but invalid config structure (servers must be a list, not a string)
        with open(temp_config_file, "w") as f:
            json.dump({"version": "1.0", "servers": "not-a-list"}, f)
        
        with pytest.raises(ConfigError) as exc_info:
            await config_service.read_gateway_config()
        
        assert "invalid configuration format" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_backup_config(self, config_service, sample_gateway_config):
        """Test creating a backup of configuration."""
        # Write initial config
        await config_service.write_gateway_config(sample_gateway_config)
        
        # Create backup
        backup_path = await config_service.backup_config()
        
        assert backup_path is not None
        assert backup_path.exists()
        assert "backup_" in backup_path.name
        
        # Verify backup content matches original
        with open(backup_path, "r") as f:
            backup_data = json.load(f)
        
        original_data = sample_gateway_config.model_dump()
        assert backup_data == original_data

    @pytest.mark.asyncio
    async def test_backup_nonexistent_config(self, config_service):
        """Test backup returns None when no config exists."""
        backup_path = await config_service.backup_config()
        assert backup_path is None

    @pytest.mark.asyncio
    async def test_get_config_path(self, config_service, temp_config_file):
        """Test getting configuration file path."""
        path = config_service.get_config_path()
        assert path == temp_config_file

    @pytest.mark.asyncio
    async def test_atomic_write(self, config_service, sample_gateway_config):
        """Test that write operation is atomic (uses temp file)."""
        # This test verifies the implementation uses atomic write
        # by checking that a .tmp file is not left behind
        await config_service.write_gateway_config(sample_gateway_config)
        
        config_path = config_service.get_config_path()
        temp_path = config_path.with_suffix(".tmp")
        
        # Temp file should not exist after successful write
        assert not temp_path.exists()
        
        # Actual config file should exist
        assert config_path.exists()


class TestConfigModels:
    """Test suite for Config models."""

    def test_server_config_creation(self):
        """Test creating a ServerConfig."""
        server = ServerConfig(
            name="test-server",
            container_id="abc123",
            enabled=True,
            config={"port": 8080}
        )
        
        assert server.name == "test-server"
        assert server.container_id == "abc123"
        assert server.enabled is True
        assert server.config["port"] == 8080

    def test_server_config_defaults(self):
        """Test ServerConfig with default values."""
        server = ServerConfig(
            name="test-server",
            container_id="abc123"
        )
        
        assert server.enabled is True
        assert server.config == {}

    def test_server_config_empty_name_fails(self):
        """Test that empty server name is rejected."""
        with pytest.raises(ValueError) as exc_info:
            ServerConfig(name="", container_id="abc123")
        
        assert "name cannot be empty" in str(exc_info.value).lower()

    def test_server_config_empty_container_id_fails(self):
        """Test that empty container ID is rejected."""
        with pytest.raises(ValueError) as exc_info:
            ServerConfig(name="test-server", container_id="")
        
        assert "container id cannot be empty" in str(exc_info.value).lower()

    def test_server_config_whitespace_trimming(self):
        """Test that whitespace is trimmed from name and container_id."""
        server = ServerConfig(
            name="  test-server  ",
            container_id="  abc123  "
        )
        
        assert server.name == "test-server"
        assert server.container_id == "abc123"

    def test_gateway_config_creation(self):
        """Test creating a GatewayConfig."""
        config = GatewayConfig(
            version="1.0",
            servers=[
                ServerConfig(name="server-1", container_id="abc123")
            ],
            global_settings={"timeout": 30}
        )
        
        assert config.version == "1.0"
        assert len(config.servers) == 1
        assert config.global_settings["timeout"] == 30

    def test_gateway_config_defaults(self):
        """Test GatewayConfig with default values."""
        config = GatewayConfig()
        
        assert config.version == "1.0"
        assert config.servers == []
        assert config.global_settings == {}

    def test_gateway_config_empty_version_fails(self):
        """Test that empty version is rejected."""
        with pytest.raises(ValueError) as exc_info:
            GatewayConfig(version="")
        
        assert "version cannot be empty" in str(exc_info.value).lower()


class TestBitwardenReferenceDetection:
    """Test suite for Bitwarden reference detection."""

    @pytest.mark.asyncio
    async def test_detect_simple_reference(self, config_service):
        """Test detection of simple Bitwarden reference."""
        config_dict = {
            "api_key": "{{ bw:item-1:api_key }}"
        }
        
        assert config_service._contains_bitwarden_reference(config_dict) is True

    @pytest.mark.asyncio
    async def test_detect_nested_reference(self, config_service):
        """Test detection of nested Bitwarden reference."""
        config_dict = {
            "database": {
                "password": "{{ bw:db-item:password }}"
            }
        }
        
        assert config_service._contains_bitwarden_reference(config_dict) is True

    @pytest.mark.asyncio
    async def test_detect_reference_in_list(self, config_service):
        """Test detection of Bitwarden reference in list."""
        config_dict = {
            "secrets": [
                "{{ bw:item-1:secret1 }}",
                "{{ bw:item-2:secret2 }}"
            ]
        }
        
        assert config_service._contains_bitwarden_reference(config_dict) is True

    @pytest.mark.asyncio
    async def test_no_reference(self, config_service):
        """Test that non-reference strings are not detected."""
        config_dict = {
            "api_key": "plain-text-key",
            "port": 8080
        }
        
        assert config_service._contains_bitwarden_reference(config_dict) is False

    @pytest.mark.asyncio
    async def test_reference_with_whitespace(self, config_service):
        """Test detection of reference with whitespace."""
        config_dict = {
            "api_key": "{{  bw:item-1:api_key  }}"
        }
        
        assert config_service._contains_bitwarden_reference(config_dict) is True
