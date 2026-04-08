import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from fastapi import HTTPException
from app.services.containers import ContainerService, AuthenticationError, ContainerError
from app.services.base import ContainerProvider
from app.models.containers import ContainerConfig

@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=ContainerProvider)
    provider.create_container = AsyncMock(return_value="test-container-id")
    provider.close = MagicMock()
    type(provider).identifier = PropertyMock(return_value="test-host")
    return provider

@pytest.fixture
def mock_secret_manager():
    sm = MagicMock()
    sm.resolve_all = AsyncMock(return_value={})
    return sm

@pytest.fixture
def mock_auth_service():
    auth = MagicMock()
    auth.validate_session = AsyncMock(return_value=True)
    auth.get_session = AsyncMock(return_value=MagicMock(bw_session_key="test-key"))
    return auth

@pytest.mark.asyncio
async def test_create_container_with_auth_success(mock_provider, mock_secret_manager, mock_auth_service):
    svc = ContainerService(
        provider=mock_provider,
        secret_manager=mock_secret_manager,
        auth_service=mock_auth_service,
    )
    config = ContainerConfig(name="test", image="alpine")
    
    container_id = await svc.create_container_with_auth(config, "test-sid")
    
    assert container_id == "test-container-id"
    mock_auth_service.get_session.assert_awaited_once_with("test-sid")
    mock_provider.create_container.assert_awaited_once()

@pytest.mark.asyncio
async def test_create_container_auth_failure(mock_provider, mock_secret_manager, mock_auth_service):
    mock_auth_service.get_session = AsyncMock(return_value=None)
    svc = ContainerService(
        provider=mock_provider,
        secret_manager=mock_secret_manager,
        auth_service=mock_auth_service,
    )
    config = ContainerConfig(name="test", image="alpine")
    
    # AuthenticationError is also mapped to HTTPException in with_auth methods
    with pytest.raises(HTTPException) as excinfo:
        await svc.create_container_with_auth(config, "bad-sid")
    assert excinfo.value.status_code == 401

@pytest.mark.asyncio
async def test_create_container_compensation_on_start_failure(mock_provider, mock_secret_manager, mock_auth_service):
    # provider.create_container が例外を投げるケース（start() 失敗のシミュレーション）
    mock_provider.create_container.side_effect = Exception("Start failed")
    
    svc = ContainerService(
        provider=mock_provider,
        secret_manager=mock_secret_manager,
        auth_service=mock_auth_service,
    )
    config = ContainerConfig(name="test", image="alpine")
    
    with pytest.raises(HTTPException) as excinfo:
        await svc.create_container_with_auth(config, "test-sid")
    assert excinfo.value.status_code == 400
    assert "Start failed" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_create_container_compensation_on_503(mock_provider, mock_secret_manager, mock_auth_service):
    # status_code=503 の例外を投げる
    e = Exception("Provider unavailable")
    e.status_code = 503
    mock_provider.create_container.side_effect = e
    
    svc = ContainerService(
        provider=mock_provider,
        secret_manager=mock_secret_manager,
        auth_service=mock_auth_service,
    )
    config = ContainerConfig(name="test", image="alpine")
    
    with pytest.raises(HTTPException) as excinfo:
        await svc.create_container_with_auth(config, "test-sid")
    assert excinfo.value.status_code == 503
    assert "503" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_create_container_compensation_on_409(mock_provider, mock_secret_manager, mock_auth_service):
    # status_code=409 の例外を投げる
    e = Exception("Already exists")
    e.status_code = 409
    mock_provider.create_container.side_effect = e
    
    svc = ContainerService(
        provider=mock_provider,
        secret_manager=mock_secret_manager,
        auth_service=mock_auth_service,
    )
    config = ContainerConfig(name="test", image="alpine")
    
    # 409 は ContainerAlreadyExistsError (ContainerError のサブクラス) に変換され、HTTPException(409) になる
    with pytest.raises(HTTPException) as excinfo:
        await svc.create_container_with_auth(config, "test-sid")
    assert excinfo.value.status_code == 409
    assert "既に使用されています" in str(excinfo.value.detail)
