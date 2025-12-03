"""Gateway configuration API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, status

from ..models.config import (
    ConfigReadResponse,
    ConfigWriteRequest,
    ConfigWriteResponse,
    ValidationResult,
)
from ..services.config import ConfigError, ConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

# Initialize config service
config_service = ConfigService()


@router.get("/gateway", response_model=ConfigReadResponse)
async def read_gateway_config():
    """
    Read the current Gateway configuration.

    Returns:
        ConfigReadResponse with the current configuration

    Raises:
        HTTPException: If configuration cannot be read
    """
    try:
        config = await config_service.read_gateway_config()
        return ConfigReadResponse(config=config)

    except ConfigError as e:
        logger.error(f"Failed to read gateway config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read configuration: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error reading gateway config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while reading configuration",
        ) from e


@router.put("/gateway", response_model=ConfigWriteResponse)
async def write_gateway_config(request: ConfigWriteRequest):
    """
    Write Gateway configuration to file.

    Args:
        request: ConfigWriteRequest with the new configuration

    Returns:
        ConfigWriteResponse indicating success

    Raises:
        HTTPException: If configuration is invalid or cannot be written
    """
    try:
        # Validate configuration first
        validation_result = await config_service.validate_config(request.config)

        if not validation_result.valid:
            error_msg = "; ".join(validation_result.errors)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid configuration: {error_msg}",
            )

        # Write configuration
        success = await config_service.write_gateway_config(request.config)

        if success:
            message = "Configuration saved successfully"
            if validation_result.warnings:
                warnings_str = "; ".join(validation_result.warnings)
                message += f" (Warnings: {warnings_str})"

            return ConfigWriteResponse(success=True, message=message)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save configuration",
            )

    except HTTPException:
        raise
    except ConfigError as e:
        logger.error(f"Failed to write gateway config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Configuration error: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error writing gateway config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving configuration",
        ) from e


@router.post("/gateway/validate", response_model=ValidationResult)
async def validate_gateway_config(request: ConfigWriteRequest):
    """
    Validate Gateway configuration without saving.

    This endpoint allows clients to validate configuration before saving.

    Args:
        request: ConfigWriteRequest with the configuration to validate

    Returns:
        ValidationResult with validation status and any errors/warnings
    """
    try:
        validation_result = await config_service.validate_config(request.config)
        return validation_result

    except Exception as e:
        logger.error(f"Error validating gateway config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}",
        ) from e


@router.post("/gateway/backup")
async def backup_gateway_config():
    """
    Create a backup of the current Gateway configuration.

    Returns:
        Dict with backup file path

    Raises:
        HTTPException: If backup creation fails
    """
    try:
        backup_path = await config_service.backup_config()

        if backup_path is None:
            return {"success": False, "message": "No configuration file to backup"}

        return {
            "success": True,
            "message": "Backup created successfully",
            "backup_path": str(backup_path),
        }

    except ConfigError as e:
        logger.error(f"Failed to create backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error creating backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating backup",
        ) from e
