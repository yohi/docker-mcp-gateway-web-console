"""Gateway configuration API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.config import (
    ConfigPathInfo,
    ConfigReadResponse,
    ConfigWriteRequest,
    ConfigWriteResponse,
    ValidationResult,
)
from ..services.config import ConfigError, ConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

# Singleton instances for dependency injection
_config_service: ConfigService = None


def get_config_service() -> ConfigService:
    """Dependency to get the configuration service instance (singleton)."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


@router.get("/path", response_model=ConfigPathInfo)
async def get_config_path(
    config_service: ConfigService = Depends(get_config_service)
):
    """
    Get the current configuration file path.
    """
    path = config_service.get_config_path()
    import os
    return ConfigPathInfo(
        path=str(path),
        exists=path.exists(),
        is_writable=os.access(path, os.W_OK) if path.exists() else os.access(path.parent, os.W_OK)
    )


@router.post("/path", response_model=ConfigPathInfo)
async def update_config_path(
    info: ConfigPathInfo,
    config_service: ConfigService = Depends(get_config_service)
):
    """
    Update the configuration file path.
    """
    config_service.set_config_path(info.path)
    return await get_config_path(config_service)


@router.get("/gateway", response_model=ConfigReadResponse)
async def read_gateway_config(
    config_service: ConfigService = Depends(get_config_service)
):
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
async def write_gateway_config(
    request: ConfigWriteRequest,
    config_service: ConfigService = Depends(get_config_service)
):
    """
    Write Gateway configuration to file.

    Args:
        request: ConfigWriteRequest with the new configuration
        config_service: Configuration service instance

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
async def validate_gateway_config(
    request: ConfigWriteRequest,
    config_service: ConfigService = Depends(get_config_service)
):
    """
    Validate Gateway configuration without saving.

    This endpoint allows clients to validate configuration before saving.

    Args:
        request: ConfigWriteRequest with the configuration to validate
        config_service: Configuration service instance

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
async def backup_gateway_config(
    config_service: ConfigService = Depends(get_config_service)
):
    """
    Create a backup of the current Gateway configuration.

    Args:
        config_service: Configuration service instance

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
