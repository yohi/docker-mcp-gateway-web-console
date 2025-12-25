import pytest
from app.models.catalog import CatalogErrorCode, CatalogErrorResponse
from app.services.catalog import CatalogError


def test_catalog_error_code_values():
    """全てのエラーコードが定義されていることを確認"""
    assert {item.value for item in CatalogErrorCode} == {
        "invalid_source",
        "rate_limited",
        "upstream_unavailable",
        "internal_error",
    }


def test_catalog_error_defaults():
    """デフォルト値でエラーが生成されることを確認"""
    error = CatalogError("catalog failed")

    assert error.error_code == CatalogErrorCode.INTERNAL_ERROR
    assert error.message == "catalog failed"
    assert error.retry_after_seconds is None


def test_catalog_error_with_retry_after():
    """retry_after_secondsを含むエラーが生成されることを確認"""
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
    """CatalogErrorResponseスキーマが正しく機能することを確認"""
    response = CatalogErrorResponse(
        detail="Upstream registry is temporarily unavailable.",
        error_code=CatalogErrorCode.UPSTREAM_UNAVAILABLE,
        retry_after_seconds=10,
    )

    assert response.detail == "Upstream registry is temporarily unavailable."
    assert response.error_code == CatalogErrorCode.UPSTREAM_UNAVAILABLE
    assert response.retry_after_seconds == 10


# タスク11.4: 構造化エラー生成のテスト


def test_catalog_error_invalid_source_generation():
    """INVALID_SOURCEエラーが正しく生成されることを確認"""
    error = CatalogError(
        "Invalid source value. Allowed: docker, official",
        error_code=CatalogErrorCode.INVALID_SOURCE,
    )

    assert error.error_code == CatalogErrorCode.INVALID_SOURCE
    assert error.message == "Invalid source value. Allowed: docker, official"
    assert error.retry_after_seconds is None


def test_catalog_error_rate_limited_generation():
    """RATE_LIMITEDエラーが正しく生成されることを確認"""
    error = CatalogError(
        "Upstream rate limit exceeded. Please retry later.",
        error_code=CatalogErrorCode.RATE_LIMITED,
        retry_after_seconds=60,
    )

    assert error.error_code == CatalogErrorCode.RATE_LIMITED
    assert error.message == "Upstream rate limit exceeded. Please retry later."
    assert error.retry_after_seconds == 60


def test_catalog_error_upstream_unavailable_generation():
    """UPSTREAM_UNAVAILABLEエラーが正しく生成されることを確認"""
    error = CatalogError(
        "Upstream registry is temporarily unavailable.",
        error_code=CatalogErrorCode.UPSTREAM_UNAVAILABLE,
    )

    assert error.error_code == CatalogErrorCode.UPSTREAM_UNAVAILABLE
    assert error.message == "Upstream registry is temporarily unavailable."
    assert error.retry_after_seconds is None


def test_catalog_error_internal_error_generation():
    """INTERNAL_ERRORエラーが正しく生成されることを確認"""
    error = CatalogError(
        "An internal error occurred.",
        error_code=CatalogErrorCode.INTERNAL_ERROR,
    )

    assert error.error_code == CatalogErrorCode.INTERNAL_ERROR
    assert error.message == "An internal error occurred."
    assert error.retry_after_seconds is None


def test_catalog_error_from_string_error_code():
    """文字列からエラーコードが正しく変換されることを確認"""
    error = CatalogError(
        "Test error",
        error_code="rate_limited",
    )

    assert error.error_code == CatalogErrorCode.RATE_LIMITED
    assert error.message == "Test error"


def test_catalog_error_retry_after_seconds_zero():
    """retry_after_secondsが0の場合も正しく設定されることを確認"""
    error = CatalogError(
        "Retry immediately",
        error_code=CatalogErrorCode.RATE_LIMITED,
        retry_after_seconds=0,
    )

    assert error.error_code == CatalogErrorCode.RATE_LIMITED
    assert error.retry_after_seconds == 0


def test_catalog_error_retry_after_seconds_large_value():
    """retry_after_secondsが大きな値の場合も正しく設定されることを確認"""
    error = CatalogError(
        "Long wait required",
        error_code=CatalogErrorCode.RATE_LIMITED,
        retry_after_seconds=3600,
    )

    assert error.error_code == CatalogErrorCode.RATE_LIMITED
    assert error.retry_after_seconds == 3600


@pytest.mark.parametrize(
    "error_code,expected_code",
    [
        (CatalogErrorCode.INVALID_SOURCE, CatalogErrorCode.INVALID_SOURCE),
        (CatalogErrorCode.RATE_LIMITED, CatalogErrorCode.RATE_LIMITED),
        (CatalogErrorCode.UPSTREAM_UNAVAILABLE, CatalogErrorCode.UPSTREAM_UNAVAILABLE),
        (CatalogErrorCode.INTERNAL_ERROR, CatalogErrorCode.INTERNAL_ERROR),
        ("invalid_source", CatalogErrorCode.INVALID_SOURCE),
        ("rate_limited", CatalogErrorCode.RATE_LIMITED),
        ("upstream_unavailable", CatalogErrorCode.UPSTREAM_UNAVAILABLE),
        ("internal_error", CatalogErrorCode.INTERNAL_ERROR),
    ],
)
def test_catalog_error_all_error_codes(error_code, expected_code):
    """全てのエラーコードが正しく生成されることを確認（パラメータ化テスト）"""
    error = CatalogError(
        "Test message",
        error_code=error_code,
    )

    assert error.error_code == expected_code
    assert error.message == "Test message"


def test_catalog_error_response_without_retry_after():
    """retry_after_secondsなしのCatalogErrorResponseが正しく機能することを確認"""
    response = CatalogErrorResponse(
        detail="Invalid source",
        error_code=CatalogErrorCode.INVALID_SOURCE,
    )

    assert response.detail == "Invalid source"
    assert response.error_code == CatalogErrorCode.INVALID_SOURCE
    assert response.retry_after_seconds is None


def test_catalog_error_response_serialization():
    """CatalogErrorResponseが正しくシリアライズされることを確認"""
    response = CatalogErrorResponse(
        detail="Rate limited",
        error_code=CatalogErrorCode.RATE_LIMITED,
        retry_after_seconds=120,
    )

    serialized = response.model_dump()
    assert serialized == {
        "detail": "Rate limited",
        "error_code": "rate_limited",
        "retry_after_seconds": 120,
    }


def test_catalog_error_response_json_schema():
    """CatalogErrorResponseのJSONスキーマが正しく生成されることを確認"""
    schema = CatalogErrorResponse.model_json_schema()

    assert "detail" in schema["properties"]
    assert "error_code" in schema["properties"]
    assert "retry_after_seconds" in schema["properties"]
    assert "detail" in schema["required"]
    assert "error_code" in schema["required"]
