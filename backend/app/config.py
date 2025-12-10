from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Catalog Configuration
    catalog_cache_ttl_seconds: int = 3600
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
    # アクセス/リフレッシュトークンの暗号化キー（Fernet）。環境変数 OAUTH_TOKEN_ENCRYPTION_KEY で必ず上書きすること。
    oauth_token_encryption_key: str = ""
    oauth_token_encryption_key_id: str = "default"

    # Application Configuration
    log_level: str = "INFO"
    # Security: Only log request bodies in debug/non-production environments
    # to prevent logging sensitive data (passwords, API keys, PII)
    log_request_body: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
