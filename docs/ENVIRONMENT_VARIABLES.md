[日本語 (Japanese)](ENVIRONMENT_VARIABLES.ja.md)

# Environment Variables

This document describes all environment variables used by the Docker MCP Gateway Console.

## Frontend Environment Variables

Create a `.env.local` file in the `frontend/` directory:

### Required Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000` | `https://api.example.com` |

### Example `.env.local`

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Backend Environment Variables

Create a `.env` file in the `backend/` directory:

### Required Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `BITWARDEN_CLI_PATH` | Path to Bitwarden CLI executable | `/usr/local/bin/bw` | `/usr/bin/bw` |
| `DOCKER_HOST` | Docker daemon endpoint used by the backend service | `unix:///run/user/<uid>/docker.sock` | `unix:///var/run/docker.sock` |
| `DOCKER_SOCKET_PATH` | Actual Unix socket path when using `unix://` in local/prod Compose | `/run/user/<uid>/docker.sock` | `/var/run/docker.sock` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SESSION_TIMEOUT_MINUTES` | Session inactivity timeout | `30` | `60` |
| `CATALOG_CACHE_TTL_SECONDS` | Catalog cache time-to-live | `3600` | `7200` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000` | `https://app.example.com,https://admin.example.com` |
| `LOG_LEVEL` | Logging level | `INFO` | `DEBUG`, `WARNING`, `ERROR` |
| `SECRET_CACHE_TTL_SECONDS` | Secret cache time-to-live | `1800` | `3600` |
| `MAX_LOG_LINES` | Maximum log lines to stream | `1000` | `5000` |
| `CATALOG_OFFICIAL_URL` | Official MCP Registry URL | `https://registry.modelcontextprotocol.io/v0/servers` | `https://registry.example.com/v0/servers` |
| `CATALOG_OFFICIAL_MAX_PAGES` | Maximum number of pages to fetch from Official Registry (1 page = 30 items) | `20` | `50` |
| `CATALOG_OFFICIAL_FETCH_TIMEOUT` | Total timeout seconds for fetching all pages | `60` | `120` |
| `CATALOG_OFFICIAL_PAGE_DELAY` | Delay in milliseconds between page fetches | `100` | `200` |
| `CATALOG_DOCKER_URL` | Docker MCP Catalog URL (Recommended replacement for `CATALOG_DEFAULT_URL`) | Value of `CATALOG_DEFAULT_URL` | `https://example.com/docker_catalog.json` |
| `CATALOG_DEFAULT_URL` | Default catalog URL (**Deprecated**) | - | `https://example.com/catalog.json` |
| `REMOTE_MCP_ALLOWED_DOMAINS` | Allowed remote MCP server domains (comma-separated). Empty means deny-all. | `""` | `api.example.com,*.trusted.com` |
| `REMOTE_MCP_MAX_CONNECTIONS` | Maximum concurrent SSE connections to remote servers | `20` | `5` |
| `ALLOW_INSECURE_ENDPOINT` | Allow HTTP/localhost endpoints (Dev only) | `false` | `true` |

**Note**: For catalog URL migration, please refer to the [Migration Guide](migrations/mcp-registry-source-selector.md).

### Example `.env`

```env
# Bitwarden Configuration
BITWARDEN_CLI_PATH=/usr/local/bin/bw

# Docker Configuration
# Nested variable expansion is not supported when running directly (python-dotenv).
# Use a concrete path. If unset, the backend will attempt to guess it automatically.
DOCKER_HOST=unix:///run/user/1000/docker.sock
# Override when the socket path differs
# DOCKER_SOCKET_PATH=/run/user/1000/docker.sock

# Session Management
SESSION_TIMEOUT_MINUTES=30

# Catalog Configuration
CATALOG_CACHE_TTL_SECONDS=3600

# Docker Catalog (Old CATALOG_DEFAULT_URL)
# Recommended: Use the new CATALOG_DOCKER_URL
CATALOG_DOCKER_URL=https://raw.githubusercontent.com/example/mcp-catalog/main/catalog.json
# CATALOG_DEFAULT_URL is still valid for backward compatibility but deprecated
# CATALOG_DEFAULT_URL=...

# Official Registry
CATALOG_OFFICIAL_URL=https://registry.modelcontextprotocol.io/v0/servers
CATALOG_OFFICIAL_MAX_PAGES=20
CATALOG_OFFICIAL_FETCH_TIMEOUT=60
CATALOG_OFFICIAL_PAGE_DELAY=100

# Remote MCP Configuration
REMOTE_MCP_ALLOWED_DOMAINS=api.example.com,*.trusted.com
REMOTE_MCP_MAX_CONNECTIONS=20
ALLOW_INSECURE_ENDPOINT=false

# Security
CORS_ORIGINS=http://localhost:3000

# Logging
LOG_LEVEL=INFO

# Performance
SECRET_CACHE_TTL_SECONDS=1800
MAX_LOG_LINES=1000
```

**Note**: If `DOCKER_HOST` is unset, the backend automatically selects an appropriate 
socket path (e.g., `unix:///run/user/<uid>/docker.sock`) based on `XDG_RUNTIME_DIR` 
or the current UID.

## Docker Compose Environment Variables

When using Docker Compose, you can override these variables in a `.env` file at the project root.
Variable expansion is available within the Compose YAML:

```env
# Frontend
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# Backend
BACKEND_PORT=8000
BITWARDEN_CLI_PATH=/usr/local/bin/bw
# Variable expansion is supported when passed through Compose YAML
DOCKER_HOST=${DOCKER_HOST:-unix://${DOCKER_SOCKET_PATH:-/run/user/${UID:-1000}/docker.sock}}
DOCKER_SOCKET_PATH=/run/user/${UID:-1000}/docker.sock
LOG_LEVEL=INFO
```

If you're running Docker under another user or with a rootful daemon, set
`DOCKER_SOCKET_PATH` to the actual socket location.
While Compose volume mounts usually follow this path automatically, if your 
`docker-compose.yml` uses a fixed mount path (e.g., `/run/user/${UID:-1000}/docker.sock`), 
you must ensure the Compose-side path matches your setting.

For the DevContainer DinD setup, the backend/workspace containers use
`DOCKER_HOST=tcp://dind:2376`, `DOCKER_TLS_VERIFY=1`, and
`DOCKER_CERT_PATH=/certs/client` instead of a host socket mount.

## Production Considerations

### Security

1. **Use HTTPS**: Always use HTTPS in production
   ```env
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

2. **Restrict CORS**: Limit CORS origins to your production domains
   ```env
   CORS_ORIGINS=https://yourdomain.com
   ```

3. **Secure Docker Socket**: Consider using Docker over TLS
   ```env
   DOCKER_HOST=tcp://docker-host:2376
   DOCKER_TLS_VERIFY=1
   DOCKER_CERT_PATH=/path/to/certs
   ```

### Performance

1. **Adjust Cache TTLs**: Increase cache durations for better performance
   ```env
   CATALOG_CACHE_TTL_SECONDS=7200
   SECRET_CACHE_TTL_SECONDS=3600
   ```

2. **Optimize Logging**: Use appropriate log levels
   ```env
   LOG_LEVEL=WARNING  # Less verbose in production
   ```

### Monitoring

1. **Enable Debug Logging** (for troubleshooting):
   ```env
   LOG_LEVEL=DEBUG
   ```

2. **Increase Log Retention**:
   ```env
   MAX_LOG_LINES=5000
   ```

## Environment-Specific Configurations

### Development

```env
LOG_LEVEL=DEBUG
SESSION_TIMEOUT_MINUTES=60
CATALOG_CACHE_TTL_SECONDS=300
```

### Staging

```env
LOG_LEVEL=INFO
SESSION_TIMEOUT_MINUTES=30
CATALOG_CACHE_TTL_SECONDS=1800
CORS_ORIGINS=https://staging.yourdomain.com
```

### Production

```env
LOG_LEVEL=WARNING
SESSION_TIMEOUT_MINUTES=30
CATALOG_CACHE_TTL_SECONDS=3600
CORS_ORIGINS=https://yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

## Validation

The backend validates environment variables on startup. If required variables are missing or invalid, the application will fail to start with an error message indicating which variables need attention.

## Secrets Management

**Important**: Never commit `.env` files to version control. Always use `.env.example` files as templates.

Add to `.gitignore`:
```
.env
.env.local
.env.*.local
```
