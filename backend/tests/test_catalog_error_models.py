from app.models.catalog import CatalogErrorCode, CatalogErrorResponse
from app.services.catalog import CatalogError


def test_catalog_error_code_values():
    assert {item.value for item in CatalogErrorCode} == {
        "invalid_source",
        "rate_limited",
        "upstream_unavailable",
        "internal_error",
    }


def test_catalog_error_defaults():
    error = CatalogError("catalog failed")

    assert error.error_code == CatalogErrorCode.INTERNAL_ERROR
    assert error.message == "catalog failed"
    assert error.retry_after_seconds is None


def test_catalog_error_with_retry_after():
    error = CatalogError(
        "rate limited",
        error_code=CatalogErrorCode.RATE_LIMITED,
        retry_after_seconds=30,
    )

    assert error.error_code == CatalogErrorCode.RATE_LIMITED
    assert error.message == "rate limited"
    assert error.retry_after_seconds == 30
    assert str(error) == "rate limited"


def test_catalog_error_response_schema():
    response = CatalogErrorResponse(
        detail="Upstream registry is temporarily unavailable.",
        error_code=CatalogErrorCode.UPSTREAM_UNAVAILABLE,
        retry_after_seconds=10,
    )

    assert response.detail == "Upstream registry is temporarily unavailable."
    assert response.error_code == CatalogErrorCode.UPSTREAM_UNAVAILABLE
    assert response.retry_after_seconds == 10
