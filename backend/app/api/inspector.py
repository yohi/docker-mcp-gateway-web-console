"""Inspector API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.inspector import InspectorResponse, PromptInfo, ResourceInfo, ToolInfo
from ..services.auth import AuthService
from ..services.inspector import InspectorError, InspectorService
from .auth import get_session_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspector", tags=["inspector"])

# Service instances
inspector_service = InspectorService()


@router.get("/{container_id}/tools", response_model=List[ToolInfo])
async def get_tools(
    container_id: str,
    session_id: str = Depends(get_session_id),
):
    """
    Get list of tools from an MCP server.
    
    Args:
        container_id: Container ID
        session_id: Current session ID (from auth)
        
    Returns:
        List of ToolInfo objects
        
    Raises:
        HTTPException: If container not found or MCP connection fails
    """
    try:
        tools = await inspector_service.list_tools(container_id)
        return tools
    except InspectorError as e:
        logger.error(f"Failed to get tools for container {container_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tools"
        )


@router.get("/{container_id}/resources", response_model=List[ResourceInfo])
async def get_resources(
    container_id: str,
    session_id: str = Depends(get_session_id),
):
    """
    Get list of resources from an MCP server.
    
    Args:
        container_id: Container ID
        session_id: Current session ID (from auth)
        
    Returns:
        List of ResourceInfo objects
        
    Raises:
        HTTPException: If container not found or MCP connection fails
    """
    try:
        resources = await inspector_service.list_resources(container_id)
        return resources
    except InspectorError as e:
        logger.error(f"Failed to get resources for container {container_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resources"
        )


@router.get("/{container_id}/prompts", response_model=List[PromptInfo])
async def get_prompts(
    container_id: str,
    session_id: str = Depends(get_session_id),
):
    """
    Get list of prompts from an MCP server.
    
    Args:
        container_id: Container ID
        session_id: Current session ID (from auth)
        
    Returns:
        List of PromptInfo objects
        
    Raises:
        HTTPException: If container not found or MCP connection fails
    """
    try:
        prompts = await inspector_service.list_prompts(container_id)
        return prompts
    except InspectorError as e:
        logger.error(f"Failed to get prompts for container {container_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting prompts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve prompts"
        )


@router.get("/{container_id}/capabilities", response_model=InspectorResponse)
async def get_capabilities(
    container_id: str,
    session_id: str = Depends(get_session_id),
):
    """
    Get all capabilities (tools, resources, prompts) from an MCP server.
    
    Args:
        container_id: Container ID
        session_id: Current session ID (from auth)
        
    Returns:
        InspectorResponse with all capabilities
        
    Raises:
        HTTPException: If container not found or MCP connection fails
    """
    try:
        capabilities = await inspector_service.get_all_capabilities(container_id)
        return capabilities
    except InspectorError as e:
        logger.error(f"Failed to get capabilities for container {container_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting capabilities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve capabilities"
        )
