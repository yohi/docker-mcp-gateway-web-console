"""Property-based tests for Container Service."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from app.models.containers import ContainerConfig, LogEntry
from app.services.auth import AuthService
from app.services.base import ContainerProvider
from app.services.containers import ContainerService
from app.services.secrets import SecretManager
from app.services.state_store import StateStore


@st.composite
def container_config_strategy(draw):
    """Generate valid ContainerConfig objects."""
    name_start = draw(
        st.text(
            min_size=1,
            max_size=1,
            alphabet=st.characters(categories=("Lu", "Ll", "Nd")),
        )
    )
    name_rest = draw(
        st.text(
            min_size=0,
            max_size=29,
            alphabet=st.characters(
                categories=("Lu", "Ll", "Nd"), include_characters="-_."
            ),
        )
    )
    name = name_start + name_rest

    repo = draw(
        st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(
                categories=("Lu", "Ll", "Nd"), include_characters="-_."
            ),
        )
    )
    tag = draw(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                categories=("Lu", "Ll", "Nd"), include_characters="-_."
            ),
        )
    )
    image = f"{repo}:{tag}"

    env = draw(
        st.dictionaries(
            keys=st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(
                    categories=("Lu", "Ll", "Nd"), include_characters="_"
                ),
            ),
            values=st.text(min_size=0, max_size=100),
            max_size=5,
        )
    )

    ports = draw(
        st.dictionaries(
            keys=st.integers(min_value=1, max_value=65535).map(str),
            values=st.integers(min_value=1024, max_value=65535),
            max_size=2,
        )
    )

    return ContainerConfig(name=name, image=image, env=env, ports=ports)


class TestContainerServiceProperties:
    """Property-based tests for ContainerService."""

    def _build_service(self) -> tuple[ContainerService, AsyncMock, AsyncMock, AsyncMock]:
        provider = AsyncMock(spec=ContainerProvider)
        secret_manager = AsyncMock(spec=SecretManager)
        auth_service = AsyncMock(spec=AuthService)
        state_store = MagicMock(spec=StateStore)
        service = ContainerService(
            provider, secret_manager, auth_service, state_store=state_store
        )
        return service, provider, secret_manager, auth_service

    @settings(max_examples=50)
    @given(
        config=container_config_strategy(),
        session_id=st.text(min_size=10, max_size=30),
        bw_session_key=st.text(min_size=20, max_size=50),
    )
    @pytest.mark.asyncio
    async def test_property_12_container_creation_and_start(
        self, config: ContainerConfig, session_id: str, bw_session_key: str
    ) -> None:
        service, provider, secret_manager, auth_service = self._build_service()
        secret_manager.resolve_all.return_value = config.env
        provider.create_container.return_value = "test-container-id"
        auth_service.validate_session.return_value = True
        auth_service.get_session.return_value = SimpleNamespace(
            bw_session_key=bw_session_key
        )

        container_id = await service.create_container_with_auth(config, session_id)

        secret_manager.resolve_all.assert_called_once_with(
            config.env, session_id, bw_session_key
        )
        provider.create_container.assert_called_once_with(
            config,
            service._normalize_container_name(config.name),
            config.env,
        )
        assert container_id == "test-container-id"

    @settings(max_examples=50)
    @given(
        container_id=st.text(
            min_size=10,
            max_size=64,
            alphabet=st.characters(categories=("Lu", "Ll", "Nd")),
        )
    )
    @pytest.mark.asyncio
    async def test_property_13_container_stop(self, container_id: str) -> None:
        service, provider, _, auth_service = self._build_service()
        provider.stop_container.return_value = True
        auth_service.validate_session.return_value = True
        auth_service.get_session.return_value = object()

        result = await service.stop_container_with_auth(container_id, "session-id")

        provider.stop_container.assert_called_once_with(container_id, timeout=10)
        assert result is True

    @settings(max_examples=50)
    @given(
        container_id=st.text(
            min_size=10,
            max_size=64,
            alphabet=st.characters(categories=("Lu", "Ll", "Nd")),
        )
    )
    @pytest.mark.asyncio
    async def test_property_14_container_restart(self, container_id: str) -> None:
        service, provider, _, auth_service = self._build_service()
        provider.restart_container.return_value = True
        auth_service.validate_session.return_value = True
        auth_service.get_session.return_value = object()

        result = await service.restart_container_with_auth(container_id, "session-id")

        provider.restart_container.assert_called_once_with(container_id, timeout=10)
        assert result is True

    @settings(max_examples=50)
    @given(
        container_id=st.text(
            min_size=10,
            max_size=64,
            alphabet=st.characters(categories=("Lu", "Ll", "Nd")),
        )
    )
    @pytest.mark.asyncio
    async def test_property_15_container_deletion(self, container_id: str) -> None:
        service, provider, _, auth_service = self._build_service()
        provider.delete_container.return_value = True
        auth_service.validate_session.return_value = True
        auth_service.get_session.return_value = object()

        result = await service.delete_container_with_auth(container_id, "session-id")

        provider.delete_container.assert_called_once_with(container_id, force=False)
        assert result is True

    @settings(max_examples=50)
    @given(
        container_id=st.text(
            min_size=10,
            max_size=64,
            alphabet=st.characters(categories=("Lu", "Ll", "Nd")),
        )
    )
    @pytest.mark.asyncio
    async def test_property_16_container_logs(self, container_id: str) -> None:
        service, provider, _, _ = self._build_service()
        entries = [
            LogEntry(
                timestamp=datetime(2024, 1, 1, 12, 0, 0),
                message="Log line 1",
                stream="stdout",
            ),
            LogEntry(
                timestamp=datetime(2024, 1, 1, 12, 0, 1),
                message="Error line 1",
                stream="stderr",
            ),
        ]

        async def stream():
            for entry in entries:
                yield entry

        provider.stream_logs = MagicMock(return_value=stream())

        logs = []
        async for log in service.stream_logs(container_id, follow=False):
            logs.append(log)

        provider.stream_logs.assert_called_once_with(container_id, False, 100)
        assert len(logs) == 2
        assert logs[0].message == "Log line 1"
        assert logs[0].stream == "stdout"
        assert logs[1].message == "Error line 1"
        assert logs[1].stream == "stderr"
