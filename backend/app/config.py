import logging

from cryptography.fernet import Fernet
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER = "PLEASE_SET_OAUTH_TOKEN_ENCRYPTION_KEY"
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Bitwarden Configuration
    bitwarden_cli_path: str = "/usr/local/bin/bw"
    # Timeout for Bitwarden CLI commands in seconds
    # Prevents hanging on unresponsive Bitwarden CLI operations
    bitwarden_cli_timeout_seconds: int = 30

    # Docker Configuration
    docker_host: str = "unix:///var/run/docker.sock"

    # Session Configuration
    session_timeout_minutes: int = 30
    state_db_path: str = "data/state.db"
    credential_retention_days: int = 30
    job_retention_hours: int = 24
    # Local/dev only: True で mTLS 証明書をプレースホルダーとして生成する
    mtls_placeholder_mode: bool = Field(
        default=False, validation_alias="MTLS_PLACEHOLDER_MODE"
    )

    # Catalog Configuration
    catalog_cache_ttl_seconds: int = 3600
    # GitHub catalog fetch concurrency and retry settings
    catalog_github_fetch_concurrency: int = 8
    catalog_github_fetch_retries: int = 2
    catalog_github_fetch_retry_base_delay_seconds: float = 0.5
    # 公式MCPレジストリ (github.com/docker/mcp-registry) を既定とする
    catalog_default_url: str = "https://api.github.com/repos/docker/mcp-registry/contents/servers"
    # GitHub API のレート制限回避用トークン（任意）
    github_token: str = ""

    # CORS Configuration
    cors_origins: str = "http://localhost:3000"

    # OAuth Configuration
    oauth_authorize_url: str = "https://auth.example.com/authorize"
    oauth_token_url: str = "https://auth.example.com/token"
    oauth_client_id: str = "mcp-console"
    oauth_redirect_uri: str = "http://localhost:8000/api/catalog/oauth/callback"
    oauth_request_timeout_seconds: int = 10
    # アクセス/リフレッシュトークンの暗号化キー（Fernet）。必ず環境変数 OAUTH_TOKEN_ENCRYPTION_KEY で本番用のキーを指定すること。
    oauth_token_encryption_key: str = Field(
        default=OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER,
        validation_alias="OAUTH_TOKEN_ENCRYPTION_KEY",
    )
    oauth_token_encryption_key_id: str = Field(
        default="default", validation_alias="OAUTH_TOKEN_ENCRYPTION_KEY_ID"
    )

    # Application Configuration
    log_level: str = "INFO"
    # Security: Only log request bodies in debug/non-production environments
    # to prevent logging sensitive data (passwords, API keys, PII)
    log_request_body: bool = False
    # CLI 経由のパスワード引数を許可するか（デフォルト: 無効）
    allow_cli_password: bool = Field(
        default=False, validation_alias="AUTH_ALLOW_CLI_PASSWORD"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    def model_post_init(self, __context: object) -> None:
        """Ensure OAuth トークン暗号化キーが未設定の場合でも起動できるよう自動生成する。"""
        if (
            not self.oauth_token_encryption_key
            or self.oauth_token_encryption_key.strip() == ""
            or self.oauth_token_encryption_key == OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER
        ):
            self.oauth_token_encryption_key = Fernet.generate_key().decode("utf-8")
            logger.warning(
                "環境変数 OAUTH_TOKEN_ENCRYPTION_KEY が未設定のため、起動時に一時キーを自動生成しました。"
                " 再起動ごとにキーが変わるため、運用環境では必ず環境変数を設定してください。"
                " 一時キー: %s",
                self.oauth_token_encryption_key,
            )


settings = Settings()
