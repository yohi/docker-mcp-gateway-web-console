"""Tests for Config API endpoints."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.config import GatewayConfig, ServerConfig
from app.services.config import ConfigService

client = TestClient(app)


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
def setup_config_service(temp_config_file, monkeypatch):
    """Setup config service with temporary file."""
    # Replace the config service in the API module
    from app.api import config as config_api
    
    test_service = ConfigService(config_path=str(temp_config_file))
    monkeypatch.setattr(config_api, "config_service", test_service)
    
    return test_service


@pytest.fixture
def sample_config_dict():
    """Sample configuration as dictionary."""
    return {
        "version": "1.0",
        "servers": [
            {
                "name": "test-server-1",
                "container_id": "abc123",
                "enabled": True,
                "config": {
                    "port": 8080,
                    "api_key": "{{ bw:item-1:api_key }}"
                }
            }
        ],
        "global_settings": {
            "log_level": "INFO"
        }
    }


class TestConfigAPI:
    """Test suite for Config API endpoints."""

    def test_read_gateway_config_empty(self, setup_config_service):
        """Test reading config when file doesn't exist."""
        response = client.get("/api/config/gateway")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "config" in data
        assert data["config"]["version"] == "1.0"
        assert data["config"]["servers"] == []
        assert data["config"]["global_settings"] == {}

    def test_write_and_read_gateway_config(self, setup_config_service, sample_config_dict):
        """Test writing and reading configuration."""
        # Write config
        response = client.put(
            "/api/config/gateway",
            json={"config": sample_config_dict}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "successfully" in data["message"].lower()
        
        # Read it back
        response = client.get("/api/config/gateway")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["config"]["version"] == sample_config_dict["version"]
        assert len(data["config"]["servers"]) == 1
        assert data["config"]["servers"][0]["name"] == "test-server-1"

    def test_write_invalid_config(self, setup_config_service):
        """Test writing invalid configuration."""
        invalid_config = {
            "version": "1.0",
            "servers": [
                {"name": "server-1", "container_id": "abc123"},
                {"name": "server-1", "container_id": "def456"}  # Duplicate name
            ]
        }
        
        response = client.put(
            "/api/config/gateway",
            json={"config": invalid_config}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "duplicate" in data["detail"].lower()

    def test_validate_gateway_config_valid(self, setup_config_service, sample_config_dict):
        """Test validating valid configuration."""
        response = client.post(
            "/api/config/gateway/validate",
            json={"config": sample_config_dict}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert len(data["errors"]) == 0

    def test_validate_gateway_config_invalid(self, setup_config_service):
        """Test validating invalid configuration."""
        invalid_config = {
            "version": "1.0",
            "servers": [
                {"name": "server-1", "container_id": "abc123"},
                {"name": "server-1", "container_id": "def456"}  # Duplicate name
            ]
        }
        
        response = client.post(
            "/api/config/gateway/validate",
            json={"config": invalid_config}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is False
        assert len(data["errors"]) > 0
        assert any("duplicate" in error.lower() for error in data["errors"])

    def test_validate_with_warnings(self, setup_config_service):
        """Test validation with warnings."""
        config_with_warnings = {
            "version": "1.0",
            "servers": [
                {
                    "name": "server-1",
                    "container_id": "abc123",
                    "config": {"api_key": "{{ bw:item-1:api_key }}"}
                }
            ]
        }
        
        response = client.post(
            "/api/config/gateway/validate",
            json={"config": config_with_warnings}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert len(data["warnings"]) > 0
        assert any("bitwarden" in warning.lower() for warning in data["warnings"])

    def test_backup_gateway_config(self, setup_config_service, sample_config_dict):
        """Test creating a backup of configuration."""
        # First write a config
        client.put(
            "/api/config/gateway",
            json={"config": sample_config_dict}
        )
        
        # Create backup
        response = client.post("/api/config/gateway/backup")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "backup_path" in data
        assert "backup_" in data["backup_path"]

    def test_backup_nonexistent_config(self, setup_config_service):
        """Test backup when no config exists."""
        response = client.post("/api/config/gateway/backup")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert "no configuration" in data["message"].lower()

    def test_write_config_with_bitwarden_references(self, setup_config_service):
        """Test writing config with Bitwarden references."""
        config_with_refs = {
            "version": "1.0",
            "servers": [
                {
                    "name": "server-1",
                    "container_id": "abc123",
                    "config": {
                        "api_key": "{{ bw:item-1:api_key }}",
                        "password": "{{ bw:item-2:password }}"
                    }
                }
            ]
        }
        
        response = client.put(
            "/api/config/gateway",
            json={"config": config_with_refs}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        # Should have warnings about Bitwarden references
        assert "warning" in data["message"].lower()

    def test_write_empty_servers_config(self, setup_config_service):
        """Test writing config with no servers."""
        empty_config = {
            "version": "1.0",
            "servers": []
        }
        
        response = client.put(
            "/api/config/gateway",
            json={"config": empty_config}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        # Should have warnings about no servers
        assert "warning" in data["message"].lower()

    def test_roundtrip_config(self, setup_config_service, sample_config_dict):
        """Test that config survives write-read roundtrip through API."""
        # Write config
        write_response = client.put(
            "/api/config/gateway",
            json={"config": sample_config_dict}
        )
        assert write_response.status_code == 200
        
        # Read it back
        read_response = client.get("/api/config/gateway")
        assert read_response.status_code == 200
        
        read_data = read_response.json()
        
        # Should match original
        assert read_data["config"]["version"] == sample_config_dict["version"]
        assert len(read_data["config"]["servers"]) == len(sample_config_dict["servers"])
        assert read_data["config"]["servers"][0]["name"] == sample_config_dict["servers"][0]["name"]
        assert read_data["config"]["servers"][0]["container_id"] == sample_config_dict["servers"][0]["container_id"]
        assert read_data["config"]["global_settings"] == sample_config_dict["global_settings"]

    def test_write_config_missing_required_fields(self, setup_config_service):
        """Test writing config with missing required fields."""
        invalid_config = {
            "version": "1.0",
            "servers": [
                {
                    "name": "server-1"
                    # Missing container_id
                }
            ]
        }
        
        response = client.put(
            "/api/config/gateway",
            json={"config": invalid_config}
        )
        
        # Should fail validation
        assert response.status_code == 422  # Unprocessable Entity (Pydantic validation)

    def test_validate_config_missing_required_fields(self, setup_config_service):
        """Test validating config with missing required fields."""
        invalid_config = {
            "version": "1.0",
            "servers": [
                {
                    "name": "server-1"
                    # Missing container_id
                }
            ]
        }
        
        response = client.post(
            "/api/config/gateway/validate",
            json={"config": invalid_config}
        )
        
        # Should fail validation at Pydantic level
        assert response.status_code == 422  # Unprocessable Entity
