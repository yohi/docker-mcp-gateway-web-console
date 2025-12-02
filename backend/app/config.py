from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Bitwarden Configuration
    bitwarden_cli_path: str = "/usr/local/bin/bw"

    # Docker Configuration
    docker_host: str = "unix:///var/run/docker.sock"

    # Session Configuration
    session_timeout_minutes: int = 30

    # Catalog Configuration
    catalog_cache_ttl_seconds: int = 3600

    # CORS Configuration
    cors_origins: str = "http://localhost:3000"

    # Application Configuration
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
