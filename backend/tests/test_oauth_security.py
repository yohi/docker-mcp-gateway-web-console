"""OAuth セキュリティ機能（SSRF対策、DNS解決失敗時の挙動）のテスト。"""

import socket
from unittest.mock import patch

import pytest

from app.services.oauth import _is_private_or_local_ip


class TestIsPrivateOrLocalIp:
    """_is_private_or_local_ip 関数のテスト。"""

    def test_public_ip_returns_false(self):
        """パブリックIPアドレスは False を返す。"""
        # GitHub のIPアドレス（例）- 実際のDNS解決に依存
        with patch("socket.gethostbyname", return_value="140.82.121.3"):
            assert _is_private_or_local_ip("github.com") is False

    def test_private_ip_returns_true(self):
        """プライベートIPアドレスは True を返す。"""
        test_cases = [
            ("192.168.1.1", "192.168.1.1"),  # RFC 1918
            ("10.0.0.1", "10.0.0.1"),  # RFC 1918
            ("172.16.0.1", "172.16.0.1"),  # RFC 1918
        ]
        for hostname, ip in test_cases:
            with patch("socket.gethostbyname", return_value=ip):
                assert _is_private_or_local_ip(hostname) is True, f"Failed for {hostname}"

    def test_loopback_ip_returns_true(self):
        """ループバックアドレスは True を返す。"""
        test_cases = [
            ("localhost", "127.0.0.1"),
            ("127.0.0.1", "127.0.0.1"),
            ("127.0.0.2", "127.0.0.2"),
        ]
        for hostname, ip in test_cases:
            with patch("socket.gethostbyname", return_value=ip):
                assert _is_private_or_local_ip(hostname) is True, f"Failed for {hostname}"

    def test_link_local_ip_returns_true(self):
        """リンクローカルアドレスは True を返す。"""
        with patch("socket.gethostbyname", return_value="169.254.1.1"):
            assert _is_private_or_local_ip("link-local.test") is True

    def test_cloud_metadata_endpoint_returns_true(self):
        """クラウドメタデータエンドポイント (169.254.169.254) は True を返す。"""
        with patch("socket.gethostbyname", return_value="169.254.169.254"):
            assert _is_private_or_local_ip("metadata.cloud") is True

    def test_dns_resolution_failure_returns_true(self):
        """DNS解決失敗時は fail-closed として True を返す（安全側に倒す）。

        DNS解決に失敗した場合、一時的なDNS障害やDNS rebinding攻撃の可能性があるため、
        安全性を優先してプライベートとみなし、アクセスを拒否する。
        """
        with patch("socket.gethostbyname", side_effect=socket.gaierror("DNS resolution failed")):
            result = _is_private_or_local_ip("nonexistent.invalid")
            assert result is True, "DNS解決失敗時は fail-closed として True を返すべき"

    def test_dns_resolution_failure_blocks_oauth_url(self):
        """DNS解決に失敗したホスト名は OAuth URL として拒否される。

        このテストは、DNS解決失敗時に _is_private_or_local_ip が True を返すことで、
        _normalize_oauth_url が OAuthError を発生させることを確認する。
        """
        from app.services.oauth import OAuthError, _normalize_oauth_url

        with patch("socket.gethostbyname", side_effect=socket.gaierror("DNS resolution failed")):
            with pytest.raises(OAuthError) as exc_info:
                _normalize_oauth_url(
                    "https://nonexistent.invalid/oauth/token",
                    field_name="token_url",
                )
            assert "プライベートIP" in str(exc_info.value)

    def test_multiple_dns_failures_all_return_true(self):
        """複数の異なるDNS失敗ケースすべてで True を返す。"""
        dns_errors = [
            socket.gaierror("Name or service not known"),
            socket.gaierror("[Errno -2] Name or service not known"),
            socket.gaierror("[Errno -3] Temporary failure in name resolution"),
        ]
        for error in dns_errors:
            with patch("socket.gethostbyname", side_effect=error):
                result = _is_private_or_local_ip("test.invalid")
                assert result is True, f"DNS error {error} should return True"

    def test_value_error_returns_false(self):
        """ValueError（IP形式への変換失敗）は False を返す。

        ValueError は IP アドレス形式の変換失敗を示し、
        DNS 解決の問題とは異なるため、従来通り False を返す。
        """
        with patch("socket.gethostbyname", return_value="invalid-ip-format"):
            with patch("ipaddress.ip_address", side_effect=ValueError("Invalid IP")):
                assert _is_private_or_local_ip("test.example.com") is False
