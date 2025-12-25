"""Tests for Official MCP Registry format conversion logic."""

import pytest

from app.models.catalog import CatalogItem
from app.services.catalog import CatalogService


class TestOfficialRegistryConversion:
    """Test suite for Official MCP Registry format conversion."""

    @pytest.fixture
    def catalog_service(self):
        """Create a fresh CatalogService instance for each test."""
        return CatalogService()

    def test_convert_official_registry_flat_format_with_all_fields(self, catalog_service):
        """正常なデータが正しく変換されることを確認する。"""
        # Official Registry flat format with all fields
        official_item = {
            "name": "modelcontextprotocol/awesome-tool",
            "display_name": "Awesome Tool",
            "description": "高速なMCP対応AIツール",
            "homepage_url": "https://awesome.example.com",
            "tags": ["productivity", "ai"],
            "client": {
                "mcp": {
                    "capabilities": ["call_tool", "read_resource"],
                    "transport": {
                        "type": "websocket",
                        "url": "wss://awesome.example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert isinstance(result, CatalogItem)
        assert result.id == "modelcontextprotocol/awesome-tool"
        assert result.name == "Awesome Tool"
        assert result.description == "高速なMCP対応AIツール"
        assert result.vendor == "modelcontextprotocol"
        assert result.homepage_url == "https://awesome.example.com"
        assert result.tags == ["productivity", "ai"]
        assert result.capabilities == ["call_tool", "read_resource"]
        assert str(result.remote_endpoint) == "wss://awesome.example.com/mcp"
        assert result.category == "general"
        assert result.docker_image == ""

    def test_convert_official_registry_flat_format_minimal(self, catalog_service):
        """最小限のフィールドでも変換されることを確認する。"""
        # Minimal Official Registry flat format
        official_item = {
            "name": "modelcontextprotocol/minimal",
            "display_name": "Minimal MCP",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://minimal.example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert isinstance(result, CatalogItem)
        assert result.id == "modelcontextprotocol/minimal"
        assert result.name == "Minimal MCP"
        assert result.description == ""
        assert result.vendor == "modelcontextprotocol"
        assert result.homepage_url is None
        assert result.tags == []
        assert result.capabilities == []
        assert str(result.remote_endpoint) == "https://minimal.example.com/mcp"

    def test_convert_official_registry_missing_name_uses_display_name(self, catalog_service):
        """name が欠落している場合、display_name から ID を生成することを確認する。"""
        official_item = {
            "display_name": "Display Only Tool",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "websocket",
                        "url": "wss://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.id == "display-only-tool"
        assert result.name == "Display Only Tool"
        assert result.vendor == ""

    def test_convert_official_registry_missing_display_name_uses_name(self, catalog_service):
        """display_name が欠落している場合、name を表示名として使用することを確認する。"""
        official_item = {
            "name": "org/name-only-tool",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.id == "org/name-only-tool"
        assert result.name == "org/name-only-tool"
        assert result.vendor == "org"

    def test_convert_official_registry_missing_both_name_and_display_name(self, catalog_service):
        """name と display_name の両方が欠落している場合、アイテムを除外することを確認する。"""
        official_item = {
            "description": "No name or display_name",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is None

    def test_convert_official_registry_invalid_url_fields_are_ignored(self, catalog_service):
        """無効な URL フィールドが除外されることを確認する。"""
        official_item = {
            "name": "test/invalid-urls",
            "display_name": "Invalid URLs Test",
            "homepage_url": "javascript:alert('xss')",  # Invalid scheme
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "file:///etc/passwd"  # Invalid scheme
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.homepage_url is None
        assert result.remote_endpoint is None

    def test_convert_official_registry_non_string_tags_are_filtered(self, catalog_service):
        """tags 配列内の文字列以外の要素がフィルタリングされることを確認する。"""
        official_item = {
            "name": "test/tags-filter",
            "display_name": "Tags Filter Test",
            "tags": ["valid", 123, None, "also-valid", {"key": "value"}],
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.tags == ["valid", "also-valid"]

    def test_convert_official_registry_non_string_capabilities_are_filtered(self, catalog_service):
        """capabilities 配列内の文字列以外の要素がフィルタリングされることを確認する。"""
        official_item = {
            "name": "test/capabilities-filter",
            "display_name": "Capabilities Filter Test",
            "client": {
                "mcp": {
                    "capabilities": ["call_tool", 456, None, "read_resource", []],
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.capabilities == ["call_tool", "read_resource"]

    def test_convert_official_registry_non_array_tags_fallback_to_empty(self, catalog_service):
        """tags が配列以外の場合、空配列にフォールバックすることを確認する。"""
        official_item = {
            "name": "test/non-array-tags",
            "display_name": "Non-Array Tags Test",
            "tags": "not-an-array",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.tags == []

    def test_convert_official_registry_non_array_capabilities_fallback_to_empty(self, catalog_service):
        """capabilities が配列以外の場合、空配列にフォールバックすることを確認する。"""
        official_item = {
            "name": "test/non-array-capabilities",
            "display_name": "Non-Array Capabilities Test",
            "client": {
                "mcp": {
                    "capabilities": "not-an-array",
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.capabilities == []

    def test_convert_official_registry_unknown_fields_are_ignored(self, catalog_service):
        """未知のフィールドが無視されることを確認する。"""
        official_item = {
            "name": "test/unknown-fields",
            "display_name": "Unknown Fields Test",
            "unknown_field_1": "should be ignored",
            "unknown_field_2": {"nested": "also ignored"},
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    },
                    "unknown_mcp_field": "ignored"
                },
                "unknown_client_field": "ignored"
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.id == "test/unknown-fields"
        assert result.name == "Unknown Fields Test"
        # Unknown fields should not cause errors and should be ignored
        assert not hasattr(result, "unknown_field_1")
        assert not hasattr(result, "unknown_field_2")

    def test_convert_official_registry_empty_string_description_normalized(self, catalog_service):
        """空文字列の description が正規化されることを確認する。"""
        official_item = {
            "name": "test/empty-description",
            "display_name": "Empty Description Test",
            "description": "",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert result.description == ""

    def test_convert_official_registry_whitespace_only_strings_normalized(self, catalog_service):
        """空白のみの文字列が正規化されることを確認する。"""
        official_item = {
            "name": "test/whitespace",
            "display_name": "   ",  # Whitespace only
            "description": "  \t\n  ",  # Whitespace only
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        # Whitespace-only display_name should be treated as None, fallback to name
        assert result.name == "test/whitespace"
        # Whitespace-only description should be normalized to empty string
        assert result.description == ""

    def test_convert_official_registry_duplicate_ids_get_suffix(self, catalog_service):
        """重複する ID に suffix が追加されることを確認する。"""
        used_ids = set()

        official_item_1 = {
            "name": "duplicate-id",
            "display_name": "First Item",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example1.com/mcp"
                    }
                }
            }
        }

        official_item_2 = {
            "name": "duplicate-id",
            "display_name": "Second Item",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "https://example2.com/mcp"
                    }
                }
            }
        }

        result_1 = catalog_service._convert_explore_server(official_item_1, used_ids=used_ids)
        result_2 = catalog_service._convert_explore_server(official_item_2, used_ids=used_ids)

        assert result_1 is not None
        assert result_2 is not None
        assert result_1.id == "duplicate-id"
        assert result_2.id == "duplicate-id-2"

    def test_convert_official_registry_http_endpoint_rejected(self, catalog_service):
        """http:// エンドポイントが Pydantic バリデーションで拒否されることを確認する。"""
        from pydantic import ValidationError

        official_item = {
            "name": "test/http-endpoint",
            "display_name": "HTTP Endpoint Test",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "http",
                        "url": "http://localhost:8080/mcp"
                    }
                }
            }
        }

        # http:// scheme is rejected by Pydantic validation
        with pytest.raises(ValidationError) as exc_info:
            catalog_service._convert_explore_server(official_item)

        assert "remote_endpoint" in str(exc_info.value)
        assert "URL scheme should be 'https' or 'wss'" in str(exc_info.value)

    def test_convert_official_registry_wss_endpoint_allowed(self, catalog_service):
        """wss:// エンドポイントが許可されることを確認する。"""
        official_item = {
            "name": "test/wss-endpoint",
            "display_name": "WSS Endpoint Test",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "websocket",
                        "url": "wss://example.com/mcp"
                    }
                }
            }
        }

        result = catalog_service._convert_explore_server(official_item)

        assert result is not None
        assert str(result.remote_endpoint) == "wss://example.com/mcp"

    def test_convert_official_registry_ws_endpoint_rejected(self, catalog_service):
        """ws:// エンドポイントが Pydantic バリデーションで拒否されることを確認する。"""
        from pydantic import ValidationError

        official_item = {
            "name": "test/ws-endpoint",
            "display_name": "WS Endpoint Test",
            "client": {
                "mcp": {
                    "transport": {
                        "type": "websocket",
                        "url": "ws://localhost:9000/mcp"
                    }
                }
            }
        }

        # ws:// scheme is rejected by Pydantic validation
        with pytest.raises(ValidationError) as exc_info:
            catalog_service._convert_explore_server(official_item)

        assert "remote_endpoint" in str(exc_info.value)
        assert "URL scheme should be 'https' or 'wss'" in str(exc_info.value)
