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
| `DOCKER_HOST` | Docker daemon socket | `unix:///var/run/docker.sock` | `tcp://localhost:2375` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SESSION_TIMEOUT_MINUTES` | Session inactivity timeout | `30` | `60` |
| `CATALOG_CACHE_TTL_SECONDS` | Catalog cache time-to-live | `3600` | `7200` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000` | `https://app.example.com,https://admin.example.com` |
| `LOG_LEVEL` | Logging level | `INFO` | `DEBUG`, `WARNING`, `ERROR` |
| `SECRET_CACHE_TTL_SECONDS` | Secret cache time-to-live | `1800` | `3600` |
| `MAX_LOG_LINES` | Maximum log lines to stream | `1000` | `5000` |
| `CATALOG_DEFAULT_URL` | Default catalog URL | - | `https://example.com/catalog.json` |

### Example `.env`

```env
# Bitwarden Configuration
BITWARDEN_CLI_PATH=/usr/local/bin/bw

# Docker Configuration
DOCKER_HOST=unix:///var/run/docker.sock

# Session Management
SESSION_TIMEOUT_MINUTES=30

# Catalog Configuration
CATALOG_CACHE_TTL_SECONDS=3600
CATALOG_DEFAULT_URL=https://raw.githubusercontent.com/example/mcp-catalog/main/catalog.json

# Security
CORS_ORIGINS=http://localhost:3000

# Logging
LOG_LEVEL=INFO

# Performance
SECRET_CACHE_TTL_SECONDS=1800
MAX_LOG_LINES=1000
```

## Docker Compose Environment Variables

When using Docker Compose, you can override these variables in a `.env` file at the project root:

```env
# Frontend
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# Backend
BACKEND_PORT=8000
BITWARDEN_CLI_PATH=/usr/local/bin/bw
DOCKER_HOST=unix:///var/run/docker.sock
SESSION_TIMEOUT_MINUTES=30
LOG_LEVEL=INFO
```

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
