"""Property-based tests for Container Service.

This module contains property-based tests using Hypothesis to verify
correctness properties of the Container Service across a wide range of inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch
import docker
from docker.errors import NotFound

from app.services.containers import ContainerService, ContainerError
from app.models.containers import ContainerConfig
from app.services.secrets import SecretManager


# Custom strategies
@st.composite
def container_config_strategy(draw):
    """Generate valid ContainerConfig objects."""
    # Docker names: must start with alphanumeric, can contain [-_.]
    name_start = draw(st.text(
        min_size=1,
        max_size=1,
        alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'))
    ))
    name_rest = draw(st.text(
        min_size=0,
        max_size=29,
        alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'), include_characters='-_.')
    ))
    name = name_start + name_rest
    
    # Docker images: use valid format like "repo:tag" or "registry/repo:tag"
    repo = draw(st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'), include_characters='-_.')
    ))
    tag = draw(st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'), include_characters='-_.')
    ))
    image = f"{repo}:{tag}"
    
    env = draw(st.dictionaries(
        keys=st.text(
            min_size=1, 
            max_size=20, 
            alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'), include_characters='_')
        ),
        values=st.text(min_size=0, max_size=100),
        max_size=5
    ))
    
    # Valid port mappings (1-65535)
    ports = draw(st.dictionaries(
        keys=st.integers(min_value=1, max_value=65535).map(str),  # container port as string
        values=st.integers(min_value=1024, max_value=65535),      # host port
        max_size=2
    ))
    
    return ContainerConfig(
        name=name,
        image=image,
        env=env,
        ports=ports
    )


class TestContainerServiceProperties:
    """Property-based tests for ContainerService."""

    @settings(max_examples=50)
    @given(
        config=container_config_strategy(),
        session_id=st.text(min_size=10, max_size=30),
        bw_session_key=st.text(min_size=20, max_size=50)
    )
    @pytest.mark.asyncio
    async def test_property_12_container_creation_and_start(
        self,
        config,
        session_id,
        bw_session_key
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 12: コンテナ作成と起動**
        
        For any valid container configuration, the system should create a Docker
        container, start it, and return the container ID.
        
        This property verifies:
        1. Secret resolution is called with correct arguments
        2. Docker container create is called with correct image, name, env, and ports
        3. Docker container start is called
        4. The returned ID matches the created container's ID
        
        **Validates: Requirement 4.1**
        """
        # Mock SecretManager
        mock_secret_manager = AsyncMock(spec=SecretManager)
        # resolve_all simply returns the env as-is (simulating no secrets or resolved secrets)
        mock_secret_manager.resolve_all.return_value = config.env
        
        container_service = ContainerService(mock_secret_manager)
        
        # Mock Docker Client and Container
        with patch('app.services.containers.docker.DockerClient') as MockDockerClient:
            mock_client = MockDockerClient.return_value
            mock_client.ping.return_value = True
            
            mock_container = MagicMock()
            mock_container.id = "test-container-id"
            mock_client.containers.create.return_value = mock_container
            
            # Execute
            container_id = await container_service.create_container(
                config,
                session_id,
                bw_session_key
            )
            
            # Verify
            # 1. Secret resolution
            mock_secret_manager.resolve_all.assert_called_once_with(
                config.env, session_id, bw_session_key
            )
            
            # 2. Container creation
            # Prepare expected ports format: '80/tcp': 8080
            expected_ports = {f"{k}/tcp": v for k, v in config.ports.items()}
            
            mock_client.containers.create.assert_called_once()
            call_kwargs = mock_client.containers.create.call_args[1]
            
            assert call_kwargs['image'] == config.image
            assert call_kwargs['name'] == config.name
            assert call_kwargs['environment'] == config.env
            assert call_kwargs['ports'] == expected_ports
            assert call_kwargs['detach'] is True
            
            # 3. Container start
            mock_container.start.assert_called_once()
            
            # 4. Return ID
            assert container_id == "test-container-id"


    @settings(max_examples=50)
    @given(container_id=st.text(min_size=10, max_size=64, alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'))))
    @pytest.mark.asyncio
    async def test_property_13_container_stop(self, container_id):
        """
        **Feature: docker-mcp-gateway-console, Property 13: コンテナ停止**
        
        For any running container, stopping it should change its status to 'stopped'.
        
        This property verifies:
        1. Docker container stop is called
        2. The method returns True upon success
        
        **Validates: Requirement 4.2**
        """
        mock_secret_manager = AsyncMock(spec=SecretManager)
        container_service = ContainerService(mock_secret_manager)
        
        with patch('app.services.containers.docker.DockerClient') as MockDockerClient:
            mock_client = MockDockerClient.return_value
            mock_client.ping.return_value = True
            
            mock_container = MagicMock()
            mock_client.containers.get.return_value = mock_container
            
            # Execute
            result = await container_service.stop_container(container_id)
            
            # Verify
            mock_client.containers.get.assert_called_once_with(container_id)
            mock_container.stop.assert_called_once()
            assert result is True


    @settings(max_examples=50)
    @given(container_id=st.text(min_size=10, max_size=64, alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'))))
    @pytest.mark.asyncio
    async def test_property_14_container_restart(self, container_id):
        """
        **Feature: docker-mcp-gateway-console, Property 14: コンテナ再起動**
        
        For any stopped container, restarting it should change its status to 'running'.
        
        This property verifies:
        1. Docker container restart is called
        2. The method returns True upon success
        
        **Validates: Requirement 4.3**
        """
        mock_secret_manager = AsyncMock(spec=SecretManager)
        container_service = ContainerService(mock_secret_manager)
        
        with patch('app.services.containers.docker.DockerClient') as MockDockerClient:
            mock_client = MockDockerClient.return_value
            mock_client.ping.return_value = True
            
            mock_container = MagicMock()
            mock_client.containers.get.return_value = mock_container
            
            # Execute
            result = await container_service.restart_container(container_id)
            
            # Verify
            mock_client.containers.get.assert_called_once_with(container_id)
            mock_container.restart.assert_called_once()
            assert result is True


    @settings(max_examples=50)
    @given(container_id=st.text(min_size=10, max_size=64, alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'))))
    @pytest.mark.asyncio
    async def test_property_15_container_deletion(self, container_id):
        """
        **Feature: docker-mcp-gateway-console, Property 15: コンテナ削除**
        
        For any container, deleting it should remove it from the system.
        
        This property verifies:
        1. Docker container remove is called
        2. The method returns True upon success
        
        **Validates: Requirement 4.4**
        """
        mock_secret_manager = AsyncMock(spec=SecretManager)
        container_service = ContainerService(mock_secret_manager)
        
        with patch('app.services.containers.docker.DockerClient') as MockDockerClient:
            mock_client = MockDockerClient.return_value
            mock_client.ping.return_value = True
            
            mock_container = MagicMock()
            mock_client.containers.get.return_value = mock_container
            
            # Execute
            result = await container_service.delete_container(container_id)
            
            # Verify
            mock_client.containers.get.assert_called_once_with(container_id)
            mock_container.remove.assert_called_once()
            assert result is True


    @settings(max_examples=50)
    @given(container_id=st.text(min_size=10, max_size=64, alphabet=st.characters(categories=('Lu', 'Ll', 'Nd'))))
    @pytest.mark.asyncio
    async def test_property_16_container_logs(self, container_id):
        """
        **Feature: docker-mcp-gateway-console, Property 16: コンテナログの取得**
        
        For any running container, the system should be able to retrieve its logs.
        
        This property verifies:
        1. Docker container logs method is called with correct parameters
        2. Log entries are parsed correctly (stdout/stderr, timestamp)
        
        **Validates: Requirement 4.5**
        """
        mock_secret_manager = AsyncMock(spec=SecretManager)
        container_service = ContainerService(mock_secret_manager)
        
        with patch('app.services.containers.docker.DockerClient') as MockDockerClient:
            mock_client = MockDockerClient.return_value
            mock_client.ping.return_value = True
            
            mock_container = MagicMock()
            mock_client.containers.get.return_value = mock_container
            
            # Mock log stream generator
            # Format: (stdout_bytes, stderr_bytes)
            # Note: stream_logs expects an iterator that yields these tuples
            
            mock_stream_data = [
                (b"2024-01-01T12:00:00.000000000Z Log line 1", None),
                (None, b"2024-01-01T12:00:01.000000000Z Error line 1"),
            ]
            mock_container.logs.return_value = iter(mock_stream_data)
            
            # Execute
            logs = []
            async for log in container_service.stream_logs(container_id, follow=False):
                logs.append(log)
            
            # Verify
            mock_client.containers.get.assert_called_once_with(container_id)
            mock_container.logs.assert_called_once()
            
            assert len(logs) == 2
            assert logs[0].message == "Log line 1"
            assert logs[0].stream == "stdout"
            assert logs[1].message == "Error line 1"
            assert logs[1].stream == "stderr"