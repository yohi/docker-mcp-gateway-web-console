"""Property-based tests for Inspector Service.

This module contains property-based tests using Hypothesis to verify
correctness properties of the Inspector Service across a wide range of inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, patch

from app.services.inspector import InspectorService, InspectorError
from app.models.inspector import ToolInfo, ResourceInfo, PromptInfo


# Strategies for generating MCP JSON responses

@st.composite
def mcp_tool_strategy(draw):
    """Generate valid MCP tool JSON objects."""
    return {
        "name": draw(st.text(min_size=1)),
        "description": draw(st.text()),
        "inputSchema": draw(st.dictionaries(
            keys=st.text(min_size=1), 
            values=st.text(),
            max_size=3
        ))
    }

@st.composite
def mcp_resource_strategy(draw):
    """Generate valid MCP resource JSON objects."""
    return {
        "uri": draw(st.text(min_size=1)),
        "name": draw(st.text()),
        "description": draw(st.text()),
        "mimeType": draw(st.one_of(st.none(), st.text(min_size=1)))
    }

@st.composite
def mcp_prompt_strategy(draw):
    """Generate valid MCP prompt JSON objects."""
    return {
        "name": draw(st.text(min_size=1)),
        "description": draw(st.text()),
        "arguments": draw(st.lists(
            st.dictionaries(
                keys=st.text(min_size=1), 
                values=st.text(),
                max_size=3
            ),
            max_size=3
        ))
    }


class TestInspectorServiceProperties:
    """Property-based tests for InspectorService."""

    @settings(max_examples=50)
    @given(
        container_id=st.text(min_size=1),
        tools_data=st.lists(mcp_tool_strategy(), max_size=10)
    )
    @pytest.mark.asyncio
    async def test_property_21_list_tools(self, container_id, tools_data):
        """
        **Feature: docker-mcp-gateway-console, Property 21: MCP機能情報の取得 (Tools)**
        
        For any valid MCP tool list response, the system should parse it into ToolInfo objects.
        
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        service = InspectorService()
        
        # Mock internal methods to bypass Docker/Network
        service._get_container_endpoint = AsyncMock(return_value=("http", "http://localhost:8080"))
        service._call_mcp_http = AsyncMock(return_value={"tools": tools_data})
        
        # Execute
        tools = await service.list_tools(container_id)
        
        # Verify
        assert len(tools) == len(tools_data)
        for i, tool in enumerate(tools):
            assert isinstance(tool, ToolInfo)
            assert tool.name == tools_data[i]["name"]
            assert tool.description == tools_data[i]["description"]
            assert tool.input_schema == tools_data[i]["inputSchema"]
            
        service._call_mcp_http.assert_called_once_with(
            "http://localhost:8080", "tools/list"
        )

    @settings(max_examples=50)
    @given(
        container_id=st.text(min_size=1),
        resources_data=st.lists(mcp_resource_strategy(), max_size=10)
    )
    @pytest.mark.asyncio
    async def test_property_21_list_resources(self, container_id, resources_data):
        """
        **Feature: docker-mcp-gateway-console, Property 21: MCP機能情報の取得 (Resources)**
        
        For any valid MCP resource list response, the system should parse it into ResourceInfo objects.
        
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        service = InspectorService()
        
        service._get_container_endpoint = AsyncMock(return_value=("http", "http://localhost:8080"))
        service._call_mcp_http = AsyncMock(return_value={"resources": resources_data})
        
        resources = await service.list_resources(container_id)
        
        assert len(resources) == len(resources_data)
        for i, resource in enumerate(resources):
            assert isinstance(resource, ResourceInfo)
            assert resource.uri == resources_data[i]["uri"]
            assert resource.name == resources_data[i]["name"]
            assert resource.description == resources_data[i]["description"]
            assert resource.mime_type == resources_data[i]["mimeType"]

        service._call_mcp_http.assert_called_once_with(
            "http://localhost:8080", "resources/list"
        )

    @settings(max_examples=50)
    @given(
        container_id=st.text(min_size=1),
        prompts_data=st.lists(mcp_prompt_strategy(), max_size=10)
    )
    @pytest.mark.asyncio
    async def test_property_21_list_prompts(self, container_id, prompts_data):
        """
        **Feature: docker-mcp-gateway-console, Property 21: MCP機能情報の取得 (Prompts)**
        
        For any valid MCP prompt list response, the system should parse it into PromptInfo objects.
        
        **Validates: Requirements 6.1, 6.2, 6.3, 6.5**
        """
        service = InspectorService()
        
        service._get_container_endpoint = AsyncMock(return_value=("http", "http://localhost:8080"))
        service._call_mcp_http = AsyncMock(return_value={"prompts": prompts_data})
        
        prompts = await service.list_prompts(container_id)
        
        assert len(prompts) == len(prompts_data)
        for i, prompt in enumerate(prompts):
            assert isinstance(prompt, PromptInfo)
            assert prompt.name == prompts_data[i]["name"]
            assert prompt.description == prompts_data[i]["description"]
            assert prompt.arguments == prompts_data[i]["arguments"]

        service._call_mcp_http.assert_called_once_with(
            "http://localhost:8080", "prompts/list"
        )

    @settings(max_examples=50)
    @given(container_id=st.text(min_size=1))
    @pytest.mark.asyncio
    async def test_property_22_connection_failure_endpoint(self, container_id):
        """
        **Feature: docker-mcp-gateway-console, Property 22: MCP接続失敗のエラーハンドリング (Endpoint)**
        
        If determining the endpoint fails (InspectorError), it should bubble up.
        
        **Validates: Requirement 6.4**
        """
        service = InspectorService()
        
        service._get_container_endpoint = AsyncMock(side_effect=InspectorError("Container not found"))
        
        with pytest.raises(InspectorError, match="Container not found"):
            await service.list_tools(container_id)

    @settings(max_examples=50)
    @given(container_id=st.text(min_size=1))
    @pytest.mark.asyncio
    async def test_property_22_connection_failure_http(self, container_id):
        """
        **Feature: docker-mcp-gateway-console, Property 22: MCP接続失敗のエラーハンドリング (HTTP)**
        
        If the HTTP call fails (InspectorError), it should bubble up.
        
        **Validates: Requirement 6.4**
        """
        service = InspectorService()
        
        service._get_container_endpoint = AsyncMock(return_value=("http", "http://localhost:8080"))
        service._call_mcp_http = AsyncMock(side_effect=InspectorError("Connection refused"))
        
        with pytest.raises(InspectorError, match="Connection refused"):
            await service.list_tools(container_id)
