"""Config Service for Gateway configuration management."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from ..config import settings
from ..models.config import GatewayConfig, ValidationResult

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Custom exception for configuration-related errors."""

    pass


class ConfigService:
    """
    Manages Gateway configuration file operations.

    Responsibilities:
    - Read Gateway configuration from file
    - Write Gateway configuration to file
    - Validate configuration data
    - Handle file I/O errors
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Config Service.

        Args:
            config_path: Path to the gateway configuration file.
                        Defaults to './gateway_config.json' if not specified.
        """
        if config_path is None:
            # Default to gateway_config.json in the current working directory
            config_path = os.path.join(os.getcwd(), "gateway_config.json")

        self.config_path = Path(config_path)
        logger.info(f"Config service initialized with path: {self.config_path}")

    async def read_gateway_config(self) -> GatewayConfig:
        """
        Read Gateway configuration from file.

        Returns:
            GatewayConfig object with the current configuration

        Raises:
            ConfigError: If file cannot be read or parsed
        """
        try:
            # Check if file exists
            if not self.config_path.exists():
                logger.info(f"Config file not found at {self.config_path}, creating default config")
                # Return default empty configuration
                return GatewayConfig()

            # Check if file is empty
            if self.config_path.stat().st_size == 0:
                logger.info(f"Config file is empty at {self.config_path}, creating default config")
                return GatewayConfig()

            # Read file content
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                raise ConfigError(f"Invalid JSON in configuration file: {e}") from e
            except IOError as e:
                raise ConfigError(f"Failed to read configuration file: {e}") from e

            # Parse and validate configuration
            try:
                config = GatewayConfig(**data)
                logger.info(f"Successfully loaded configuration with {len(config.servers)} servers")
                return config
            except ValidationError as e:
                raise ConfigError(f"Invalid configuration format: {e}") from e

        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"Unexpected error reading configuration: {e}") from e

    async def write_gateway_config(self, config: GatewayConfig) -> bool:
        """
        Write Gateway configuration to file.

        Args:
            config: GatewayConfig object to write

        Returns:
            True if write was successful

        Raises:
            ConfigError: If validation fails or file cannot be written
        """
        try:
            # Validate configuration before writing
            validation_result = await self.validate_config(config)
            if not validation_result.valid:
                error_msg = "; ".join(validation_result.errors)
                raise ConfigError(f"Configuration validation failed: {error_msg}")

            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict and write to file
            config_dict = config.model_dump()

            try:
                # Write to temporary file first for atomic operation
                temp_path = self.config_path.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)

                # Rename to actual file (atomic on most systems)
                temp_path.replace(self.config_path)

                logger.info(f"Successfully wrote configuration to {self.config_path}")
                return True

            except IOError as e:
                raise ConfigError(f"Failed to write configuration file: {e}") from e

        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"Unexpected error writing configuration: {e}") from e

    async def validate_config(self, config: GatewayConfig) -> ValidationResult:
        """
        Validate Gateway configuration.

        This method performs comprehensive validation including:
        - Schema validation (handled by Pydantic)
        - Business logic validation
        - Duplicate detection

        Args:
            config: GatewayConfig object to validate

        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []

        try:
            # Pydantic validation is already done when creating the GatewayConfig object
            # Here we add additional business logic validation

            # Check for duplicate server names
            server_names = [server.name for server in config.servers]
            duplicate_names = [name for name in server_names if server_names.count(name) > 1]
            if duplicate_names:
                unique_duplicates = list(set(duplicate_names))
                errors.append(f"Duplicate server names found: {', '.join(unique_duplicates)}")

            # Check for duplicate container IDs
            container_ids = [server.container_id for server in config.servers]
            duplicate_ids = [cid for cid in container_ids if container_ids.count(cid) > 1]
            if duplicate_ids:
                unique_duplicate_ids = list(set(duplicate_ids))
                errors.append(
                    f"Duplicate container IDs found: {', '.join(unique_duplicate_ids)}"
                )

            # Warn if no servers are configured
            if not config.servers:
                warnings.append("No servers configured")

            # Warn if all servers are disabled
            if config.servers and all(not server.enabled for server in config.servers):
                warnings.append("All servers are disabled")

            # Check for Bitwarden reference notation in config
            # This is just a warning, not an error, as references are valid
            for server in config.servers:
                if self._contains_bitwarden_reference(server.config):
                    warnings.append(
                        f"Server '{server.name}' contains Bitwarden references "
                        f"that will be resolved at runtime"
                    )

            valid = len(errors) == 0

            if valid:
                logger.debug("Configuration validation passed")
            else:
                logger.warning(f"Configuration validation failed: {errors}")

            return ValidationResult(valid=valid, errors=errors, warnings=warnings)

        except Exception as e:
            logger.error(f"Error during configuration validation: {e}")
            return ValidationResult(
                valid=False, errors=[f"Validation error: {str(e)}"], warnings=warnings
            )

    def _contains_bitwarden_reference(self, config_dict: dict) -> bool:
        """
        Check if a configuration dictionary contains Bitwarden reference notation.

        Args:
            config_dict: Dictionary to check

        Returns:
            True if any value contains Bitwarden reference notation
        """
        import re

        # Pattern for Bitwarden reference: {{ bw:item-id:field }}
        bw_pattern = re.compile(r"\{\{\s*bw:[^}]+\}\}")

        def check_value(value):
            """Recursively check values for Bitwarden references."""
            if isinstance(value, str):
                return bool(bw_pattern.search(value))
            elif isinstance(value, dict):
                return any(check_value(v) for v in value.values())
            elif isinstance(value, list):
                return any(check_value(item) for item in value)
            return False

        return check_value(config_dict)

    async def backup_config(self) -> Optional[Path]:
        """
        Create a backup of the current configuration file.

        Returns:
            Path to the backup file if successful, None if no config exists

        Raises:
            ConfigError: If backup creation fails
        """
        try:
            if not self.config_path.exists():
                logger.info("No configuration file to backup")
                return None

            # Check if file is empty
            if self.config_path.stat().st_size == 0:
                logger.info("Configuration file is empty, no backup needed")
                return None

            # Create backup with timestamp
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.config_path.with_suffix(f".backup_{timestamp}.json")

            # Copy current config to backup
            import shutil

            shutil.copy2(self.config_path, backup_path)

            logger.info(f"Created configuration backup at {backup_path}")
            return backup_path

        except Exception as e:
            raise ConfigError(f"Failed to create configuration backup: {e}") from e

    def get_config_path(self) -> Path:
        """
        Get the path to the configuration file.

        Returns:
            Path object for the configuration file
        """
        return self.config_path
