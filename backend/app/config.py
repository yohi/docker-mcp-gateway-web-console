import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER = "PLEASE_SET_OAUTH_TOKEN_ENCRYPTION_KEY"
logger = logging.getLogger(__name__)


def _default_docker_host() -> str:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return f"unix://{runtime_dir}/docker.sock"
    try:
        uid = os.getuid()
    except AttributeError:
        uid = None
    if isinstance(uid, int):
        return f"unix:///run/user/{uid}/docker.sock"
    return "unix:///var/run/docker.sock"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Bitwarden Configuration
    bitwarden_cli_path: str = "/usr/local/bin/bw"
    # Timeout for Bitwarden CLI commands in seconds
    # Prevents hanging on unresponsive Bitwarden CLI operations
    bitwarden_cli_timeout_seconds: int = 30

    # Docker Configuration
    docker_host: str = Field(default_factory=_default_docker_host)

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
    # Official MCP Registry の既定URL
    catalog_official_url: str = "https://registry.modelcontextprotocol.io/v0/servers"
    # GitHub API のレート制限回避用トークン(任意)
    github_token: str = ""
    # 開発用途でのみ HTTP/localhost を許可するフラグ
    allow_insecure_endpoint: bool = Field(default=False, validation_alias="ALLOW_INSECURE_ENDPOINT")

    # CORS Configuration
    cors_origins: str = "http://localhost:3000"

    # OAuth Configuration
    oauth_authorize_url: str = "https://auth.example.com/authorize"
    oauth_token_url: str = "https://auth.example.com/token"
    oauth_client_id: str = "mcp-console"
    oauth_client_secret: str = Field(
        default="", validation_alias="OAUTH_CLIENT_SECRET"
    )
    oauth_redirect_uri: str = "http://localhost:8000/api/catalog/oauth/callback"
    oauth_request_timeout_seconds: int = 10
    # サーバーごとに OAuth エンドポイント等を上書きできるか(カタログ/クライアント由来の値を使用するため慎重に運用する)
    oauth_allow_override: bool = Field(default=False, validation_alias="OAUTH_ALLOW_OVERRIDE")
    # OAuth URL の許可ドメインリスト(カンマ区切り)。空の場合はすべてのドメインを拒否（本番環境では必ず明示的に設定すること）。
    oauth_allowed_domains: str = Field(
        default="", validation_alias="OAUTH_ALLOWED_DOMAINS"
    )
    # アクセス/リフレッシュトークンの暗号化キー(Fernet)。必ず環境変数 OAUTH_TOKEN_ENCRYPTION_KEY で本番用のキーを指定すること。
    oauth_token_encryption_key: str = Field(
        default=OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER,
        validation_alias="OAUTH_TOKEN_ENCRYPTION_KEY",
    )
    oauth_token_encryption_key_id: str = Field(
        default="default", validation_alias="OAUTH_TOKEN_ENCRYPTION_KEY_ID"
    )
    # Credential Encryption (AES-GCM) for OAuth トークンの代替暗号鍵
    credential_encryption_key: str = Field(
        default="", validation_alias="CREDENTIAL_ENCRYPTION_KEY"
    )
    credential_encryption_key_id: str = Field(
        default="credential", validation_alias="CREDENTIAL_ENCRYPTION_KEY_ID"
    )
    # 暗号鍵の永続化パス (env > file > generate の順で利用)
    oauth_token_key_file: str = Field(
        default="data/oauth_encryption.key", validation_alias="OAUTH_TOKEN_ENCRYPTION_KEY_FILE"
    )

    # Application Configuration
    log_level: str = "INFO"
    # Security: Only log request bodies in debug/non-production environments
    # to prevent logging sensitive data (passwords, API keys, PII)
    log_request_body: bool = False
    # CLI 経由のパスワード引数を許可するか(デフォルト: 無効)
    allow_cli_password: bool = Field(
        default=False, validation_alias="AUTH_ALLOW_CLI_PASSWORD"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def catalog_docker_url(self) -> str:
        """Docker カタログ URL の後方互換エイリアス."""
        return self.catalog_default_url

    @property
    def oauth_allowed_domains_list(self) -> list[str]:
        """Parse OAuth allowed domains from comma-separated string."""
        return [domain.strip().lower() for domain in self.oauth_allowed_domains.split(",") if domain.strip()]

    def model_post_init(self, __context: object) -> None:
        """OAuth トークン暗号化キーを env > ファイル > 生成の順で取得し、妥当性を検証する。"""
        env_key = self.oauth_token_encryption_key
        # 1. 環境変数が設定されている場合は優先して検証
        if env_key and env_key.strip() and env_key != OAUTH_TOKEN_ENCRYPTION_KEY_PLACEHOLDER:
            try:
                Fernet(env_key.encode())
                logger.info("環境変数 OAUTH_TOKEN_ENCRYPTION_KEY から暗号鍵を読み込みました。")
                return
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "環境変数 OAUTH_TOKEN_ENCRYPTION_KEY が不正です。32バイトの URL-safe base64 文字列を設定してください。"
                )
                raise exc

        key_path = Path(self.oauth_token_key_file)

        # 2. ファイルが存在する場合は読み込んで検証
        if key_path.exists():
            try:
                key_bytes = key_path.read_bytes().strip()
                key_str = key_bytes.decode("utf-8")
                Fernet(key_str.encode())
                self.oauth_token_encryption_key = key_str
                logger.info("暗号鍵をファイル %s から読み込みました。", key_path)
                return
            except Exception as exc:  # noqa: BLE001
                logger.error("暗号鍵ファイル %s の読み込みに失敗しました。", key_path)
                raise exc

        # 3. いずれも無ければ新規生成し、ファイルへ保存 (600)
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            new_key = Fernet.generate_key().decode("utf-8")
            try:
                key_path.write_text(new_key, encoding="utf-8")
                key_path.chmod(0o600)
                logger.warning(
                    "環境変数 OAUTH_TOKEN_ENCRYPTION_KEY が未設定のため、新規キーを生成し %s に保存しました。"
                    " 運用環境では環境変数またはシークレットでの供給を推奨します。",
                    key_path,
                )
            except PermissionError:
                # ディスク書き込み不可の場合はメモリ上でのみ使用し、再起動時に再生成される
                logger.warning(
                    "暗号鍵ファイル %s への書き込み権限がありません。生成したキーをメモリ上でのみ使用します。"
                    " 永続化したい場合はディレクトリの権限を修正してください。",
                    key_path,
                )
            self.oauth_token_encryption_key = new_key
        except Exception as exc:  # noqa: BLE001
            logger.error("暗号鍵ファイル %s の生成に失敗しました。", key_path)
            raise exc


settings = Settings()
