"""
Integration tests for catalog API upstream error handling:
- Rate limiting (429 Too Many Requests)
- Upstream unavailability (503 Service Unavailable)
- Timeout errors

Requirements: 4.1, 4.2
"""

import pytest
from datetime import datetime, timedelta
from email.utils import formatdate
from unittest.mock import patch, AsyncMock
from httpx import Response
from app.main import app
from app.models.catalog import CatalogErrorCode
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    """Clear catalog cache before each test to ensure test isolation."""
    from app.api.catalog import catalog_service
    catalog_service._cache.clear()
    yield
    catalog_service._cache.clear()


@pytest.mark.asyncio
async def test_upstream_rate_limit_returns_429():
    """
    Test that when upstream returns 429, API returns 429 with structured error.
    Verifies that Retry-After header is extracted and included in response.

    Requirements: 4.1
    """
    # Mock upstream 429 response
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "60"}
    mock_response.raise_for_status.side_effect = None

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        # Verify 429 response
        assert response.status_code == 429
        data = response.json()

        # Verify structured error response
        assert "error_code" in data
        assert data["error_code"] == "rate_limited"
        assert "detail" in data
        assert "retry_after_seconds" in data
        assert data["retry_after_seconds"] == 60


@pytest.mark.asyncio
async def test_upstream_rate_limit_without_retry_after():
    """
    Test that when upstream returns 429 without Retry-After header,
    API still returns 429 with error_code but retry_after_seconds is None.

    Requirements: 4.1
    """
    # Mock upstream 429 response without Retry-After
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 429
    mock_response.headers = {}
    mock_response.raise_for_status.side_effect = None

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        # Verify 429 response
        assert response.status_code == 429
        data = response.json()

        # Verify structured error response
        assert data["error_code"] == "rate_limited"
        # retry_after_seconds should be omitted when not provided (exclude_none=True)
        assert "retry_after_seconds" not in data


@pytest.mark.asyncio
async def test_upstream_rate_limit_with_datetime_retry_after():
    """
    Test that when upstream returns 429 with HTTP-date Retry-After header,
    API correctly parses it and converts to seconds.

    Requirements: 4.1
    """
    # Generate a future HTTP-date for Retry-After header (now + 60 seconds)
    future_time = datetime.utcnow() + timedelta(seconds=60)
    retry_after_date = formatdate(timeval=future_time.timestamp(), usegmt=True)

    # Mock upstream 429 response with HTTP-date Retry-After
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": retry_after_date}
    mock_response.raise_for_status.side_effect = None

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        # Verify 429 response
        assert response.status_code == 429
        data = response.json()

        # Verify structured error response
        assert data["error_code"] == "rate_limited"
        assert "retry_after_seconds" in data
        # Should contain a non-negative integer (parsed from HTTP-date)
        assert isinstance(data["retry_after_seconds"], int)
        assert data["retry_after_seconds"] >= 0


@pytest.mark.asyncio
async def test_search_endpoint_rate_limit_returns_429():
    """
    Test that search endpoint also handles upstream rate limiting correctly.
    Verifies consistency between /api/catalog and /api/catalog/search endpoints.

    Requirements: 4.1
    """
    # Mock upstream 429 response
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "120"}
    mock_response.raise_for_status.side_effect = None

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog/search?source=docker&q=test")

        # Verify 429 response
        assert response.status_code == 429
        data = response.json()

        # Verify structured error response
        assert data["error_code"] == "rate_limited"
        assert data["retry_after_seconds"] == 120


@pytest.mark.asyncio
async def test_upstream_timeout_returns_503():
    """
    Test that when upstream times out, API returns 503 with structured error.

    Requirements: 4.2
    """
    import httpx

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        # Simulate timeout exception
        mock_client.get.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        # Verify 503 response
        assert response.status_code == 503
        data = response.json()

        # Verify structured error response
        assert "error_code" in data
        assert data["error_code"] == "upstream_unavailable"
        assert "detail" in data
        # retry_after_seconds should not be present for upstream unavailability
        assert "retry_after_seconds" not in data


@pytest.mark.asyncio
async def test_upstream_5xx_error_returns_503():
    """
    Test that when upstream returns 5xx error, API returns 503 with structured error.

    Requirements: 4.2
    """
    # Mock upstream 500 response
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 500
    mock_response.headers = {}
    mock_response.raise_for_status.side_effect = None

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        # Verify 503 response
        assert response.status_code == 503
        data = response.json()

        # Verify structured error response
        assert data["error_code"] == "upstream_unavailable"
        assert "detail" in data


@pytest.mark.asyncio
async def test_upstream_connection_error_returns_503():
    """
    Test that when upstream connection fails, API returns 503 with structured error.

    Requirements: 4.2
    """
    import httpx

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        # Simulate connection error
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog?source=docker")

        # Verify 503 response
        assert response.status_code == 503
        data = response.json()

        # Verify structured error response
        assert data["error_code"] == "upstream_unavailable"
        assert "detail" in data


@pytest.mark.asyncio
async def test_search_endpoint_upstream_timeout_returns_503():
    """
    Test that search endpoint also handles upstream timeout correctly.
    Verifies consistency between /api/catalog and /api/catalog/search endpoints.

    Requirements: 4.2
    """
    import httpx

    with patch("app.services.catalog.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_class.return_value = mock_client

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/catalog/search?source=official&q=test")

        # Verify 503 response
        assert response.status_code == 503
        data = response.json()

        # Verify structured error response
        assert data["error_code"] == "upstream_unavailable"
