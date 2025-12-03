"""Inspector Service for MCP protocol communication."""

import asyncio
import json
import logging
from typing import List, Optional

import docker
import httpx
from docker.errors import DockerException, NotFound

from ..models.inspector import InspectorResponse, PromptInfo, ResourceInfo, ToolInfo

logger = logging.getLogger(__name__)


class InspectorError(Exception):
    """Custom exception for Inspector errors."""
    pass


class InspectorService:
    """
    Manages MCP protocol communication with running containers.
    
    Responsibilities:
    - Connect to MCP servers running in Docker containers
    - Retrieve available tools, resources, and prompts
    - Handle MCP protocol communication errors
    """

    def __init__(self):
        """Initialize the Inspector Service."""
        self._docker_client: Optional[docker.DockerClient] = None

    def _get_docker_client(self) -> docker.DockerClient:
        """
        Get or create Docker client.
        
        Returns:
            Docker client instance
            
        Raises:
            InspectorError: If Docker client cannot be created
        """
        if self._docker_client is None:
            try:
                self._docker_client = docker.from_env()
                # Test connection
                self._docker_client.ping()
            except DockerException as e:
                raise InspectorError(f"Failed to connect to Docker daemon: {e}") from e
        
        return self._docker_client

    async def _get_container_endpoint(self, container_id: str) -> tuple[str, str]:
        """
        Get the MCP endpoint for a container.
        
        This method inspects the container to determine how to connect to the MCP server.
        It looks for:
        1. MCP_ENDPOINT environment variable
        2. Exposed ports (defaults to port 8080)
        3. Container network information
        
        Args:
            container_id: Container ID
            
        Returns:
            Tuple of (endpoint_type, endpoint_url)
            endpoint_type: "http" or "stdio"
            endpoint_url: URL for HTTP or container name for stdio
            
        Raises:
            InspectorError: If container not found or endpoint cannot be determined
        """
        try:
            client = self._get_docker_client()
            
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_id)
            )
            
            # Check for MCP_ENDPOINT environment variable
            env_vars = container.attrs.get("Config", {}).get("Env", [])
            for env_var in env_vars:
                if env_var.startswith("MCP_ENDPOINT="):
                    endpoint = env_var.split("=", 1)[1]
                    if endpoint.startswith("http"):
                        return ("http", endpoint)
                    elif endpoint == "stdio":
                        return ("stdio", container.name)
            
            # Check for exposed ports
            ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            if ports:
                # Look for common MCP ports
                for port_key in ["8080/tcp", "3000/tcp", "5000/tcp"]:
                    if port_key in ports and ports[port_key]:
                        host_port = ports[port_key][0]["HostPort"]
                        return ("http", f"http://localhost:{host_port}")
            
            # Default to stdio if no HTTP endpoint found
            return ("stdio", container.name)
            
        except NotFound as e:
            raise InspectorError(f"Container not found: {container_id}") from e
        except DockerException as e:
            raise InspectorError(f"Failed to inspect container: {e}") from e

    async def _call_mcp_http(
        self,
        endpoint: str,
        method: str,
        params: Optional[dict] = None
    ) -> dict:
        """
        Call an MCP server via HTTP/JSON-RPC.
        
        Args:
            endpoint: HTTP endpoint URL
            method: MCP method name (e.g., "tools/list")
            params: Optional parameters for the method
            
        Returns:
            Response data
            
        Raises:
            InspectorError: If the request fails
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # MCP uses JSON-RPC 2.0
                request_data = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params or {}
                }
                
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    raise InspectorError(
                        f"HTTP request failed with status {response.status_code}: {response.text}"
                    )
                
                data = response.json()
                
                # Check for JSON-RPC error
                if "error" in data:
                    error = data["error"]
                    raise InspectorError(
                        f"MCP error: {error.get('message', 'Unknown error')}"
                    )
                
                return data.get("result", {})
                
        except httpx.TimeoutException as e:
            raise InspectorError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise InspectorError(f"Request failed: {e}") from e
        except json.JSONDecodeError as e:
            raise InspectorError(f"Invalid JSON response: {e}") from e

    async def _call_mcp_stdio(
        self,
        container_name: str,
        method: str,
        params: Optional[dict] = None
    ) -> dict:
        """
        Call an MCP server via stdio (docker exec).
        
        Args:
            container_name: Container name
            method: MCP method name
            params: Optional parameters
            
        Returns:
            Response data
            
        Raises:
            InspectorError: If the request fails
        """
        try:
            client = self._get_docker_client()
            
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.get(container_name)
            )
            
            # Prepare JSON-RPC request
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params or {}
            }
            
            request_json = json.dumps(request_data)
            
            # Execute command in container
            exec_result = await loop.run_in_executor(
                None,
                lambda: container.exec_run(
                    cmd=["mcp"],
                    stdin=request_json.encode('utf-8'),
                    stdout=True,
                    stderr=True,
                )
            )
            
            if exec_result.exit_code != 0:
                stderr = exec_result.output.decode("utf-8", errors="replace")
                raise InspectorError(f"MCP command failed: {stderr}")
            
            # Parse response
            output = exec_result.output.decode("utf-8", errors="replace")
            data = json.loads(output)
            
            # Check for JSON-RPC error
            if "error" in data:
                error = data["error"]
                raise InspectorError(
                    f"MCP error: {error.get('message', 'Unknown error')}"
                )
            
            return data.get("result", {})
            
        except NotFound as e:
            raise InspectorError(f"Container not found: {container_name}") from e
        except json.JSONDecodeError as e:
            raise InspectorError(f"Invalid JSON response: {e}") from e
        except DockerException as e:
            raise InspectorError(f"Docker operation failed: {e}") from e

    async def connect_to_mcp(self, container_id: str) -> tuple[str, str]:
        """
        Establish connection parameters for an MCP server.
        
        Args:
            container_id: Container ID
            
        Returns:
            Tuple of (endpoint_type, endpoint_url)
            
        Raises:
            InspectorError: If connection cannot be established
        """
        return await self._get_container_endpoint(container_id)

    async def list_tools(self, container_id: str) -> List[ToolInfo]:
        """
        List all tools provided by an MCP server.
        
        Args:
            container_id: Container ID
            
        Returns:
            List of ToolInfo objects
            
        Raises:
            InspectorError: If the request fails
        """
        try:
            endpoint_type, endpoint = await self._get_container_endpoint(container_id)
            
            if endpoint_type == "http":
                result = await self._call_mcp_http(endpoint, "tools/list")
            else:
                result = await self._call_mcp_stdio(endpoint, "tools/list")
            
            # Parse tools from result
            tools = []
            for tool_data in result.get("tools", []):
                tools.append(ToolInfo(
                    name=tool_data.get("name", ""),
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {})
                ))
            
            return tools
            
        except InspectorError:
            raise
        except Exception as e:
            raise InspectorError(f"Failed to list tools: {e}") from e

    async def list_resources(self, container_id: str) -> List[ResourceInfo]:
        """
        List all resources provided by an MCP server.
        
        Args:
            container_id: Container ID
            
        Returns:
            List of ResourceInfo objects
            
        Raises:
            InspectorError: If the request fails
        """
        try:
            endpoint_type, endpoint = await self._get_container_endpoint(container_id)
            
            if endpoint_type == "http":
                result = await self._call_mcp_http(endpoint, "resources/list")
            else:
                result = await self._call_mcp_stdio(endpoint, "resources/list")
            
            # Parse resources from result
            resources = []
            for resource_data in result.get("resources", []):
                resources.append(ResourceInfo(
                    uri=resource_data.get("uri", ""),
                    name=resource_data.get("name", ""),
                    description=resource_data.get("description", ""),
                    mime_type=resource_data.get("mimeType")
                ))
            
            return resources
            
        except InspectorError:
            raise
        except Exception as e:
            raise InspectorError(f"Failed to list resources: {e}") from e

    async def list_prompts(self, container_id: str) -> List[PromptInfo]:
        """
        List all prompts provided by an MCP server.
        
        Args:
            container_id: Container ID
            
        Returns:
            List of PromptInfo objects
            
        Raises:
            InspectorError: If the request fails
        """
        try:
            endpoint_type, endpoint = await self._get_container_endpoint(container_id)
            
            if endpoint_type == "http":
                result = await self._call_mcp_http(endpoint, "prompts/list")
            else:
                result = await self._call_mcp_stdio(endpoint, "prompts/list")
            
            # Parse prompts from result
            prompts = []
            for prompt_data in result.get("prompts", []):
                prompts.append(PromptInfo(
                    name=prompt_data.get("name", ""),
                    description=prompt_data.get("description", ""),
                    arguments=prompt_data.get("arguments", [])
                ))
            
            return prompts
            
        except InspectorError:
            raise
        except Exception as e:
            raise InspectorError(f"Failed to list prompts: {e}") from e

    async def get_all_capabilities(self, container_id: str) -> InspectorResponse:
        """
        Get all capabilities (tools, resources, prompts) from an MCP server.
        
        Args:
            container_id: Container ID
            
        Returns:
            InspectorResponse with all capabilities
            
        Raises:
            InspectorError: If any request fails
        """
        try:
            # Fetch all capabilities concurrently
            tools_task = self.list_tools(container_id)
            resources_task = self.list_resources(container_id)
            prompts_task = self.list_prompts(container_id)
            
            tools, resources, prompts = await asyncio.gather(
                tools_task,
                resources_task,
                prompts_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(tools, Exception):
                logger.error(f"Failed to fetch tools: {tools}")
                tools = []
            
            if isinstance(resources, Exception):
                logger.error(f"Failed to fetch resources: {resources}")
                resources = []
            
            if isinstance(prompts, Exception):
                logger.error(f"Failed to fetch prompts: {prompts}")
                prompts = []
            
            return InspectorResponse(
                tools=tools,
                resources=resources,
                prompts=prompts
            )
            
        except Exception as e:
            raise InspectorError(f"Failed to get capabilities: {e}") from e

    def close(self):
        """Close the Docker client connection."""
        if self._docker_client is not None:
            self._docker_client.close()
            self._docker_client = None
