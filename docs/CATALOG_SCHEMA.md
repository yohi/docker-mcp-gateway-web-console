[日本語 (Japanese)](CATALOG_SCHEMA.ja.md)

# Catalog Schema Documentation

This document describes the schema for MCP Server Catalogs used by the Docker MCP Gateway Console.

## Overview

A catalog is a JSON file that lists available MCP servers with their configuration details. The console fetches this catalog to display available servers for installation.

## Schema Version

Current version: `1.0`

## Root Object

```json
{
  "version": "1.0",
  "metadata": { ... },
  "servers": [ ... ],
  "categories": [ ... ]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (currently "1.0") |
| `metadata` | object | No | Catalog metadata |
| `servers` | array | Yes | Array of server definitions |
| `categories` | array | No | Array of category definitions |

## Metadata Object

```json
{
  "name": "My MCP Catalog",
  "description": "A collection of MCP servers",
  "maintainer": "Your Name",
  "last_updated": "2024-01-01T00:00:00Z"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Catalog name |
| `description` | string | No | Catalog description |
| `maintainer` | string | No | Maintainer name or organization |
| `last_updated` | string | No | ISO 8601 timestamp of last update |

## Server Object

```json
{
  "id": "mcp-server-example",
  "name": "Example MCP Server",
  "description": "An example server",
  "category": "utilities",
  "docker_image": "example/mcp-server:latest",
  "default_env": {
    "PORT": "8080",
    "API_KEY": "{{ bw:item-id:field }}"
  },
  "required_secrets": ["API_KEY"],
  "documentation_url": "https://github.com/example/mcp-server",
  "tags": ["example", "demo"]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (kebab-case recommended) |
| `name` | string | Yes | Display name |
| `description` | string | Yes | Brief description of functionality |
| `category` | string | Yes | Category ID (must match a category in `categories` array) |
| `docker_image` | string | Yes | Docker image name with tag |
| `default_env` | object | No | Default environment variables |
| `required_secrets` | array | No | List of environment variable names that require secrets |
| `documentation_url` | string | No | URL to documentation |
| `tags` | array | No | Array of searchable tags |
| `ports` | object | No | Port mappings (see below) |
| `volumes` | object | No | Volume mappings (see below) |
| `labels` | object | No | Docker labels |

### Environment Variables

Environment variables in `default_env` can use Bitwarden reference notation:

```json
{
  "API_KEY": "{{ bw:item-id:field }}",
  "STATIC_VALUE": "some-value"
}
```

**Bitwarden Reference Format:**
- `{{ bw:item-id:field }}`
- `item-id`: Bitwarden item UUID
- `field`: Field name (password, username, or custom field name)

### Ports Object

```json
{
  "ports": {
    "8080/tcp": 8080,
    "9090/tcp": 9090
  }
}
```

Maps container ports to host ports.

### Volumes Object

```json
{
  "volumes": {
    "/data": "/host/path/data",
    "/config": "/host/path/config"
  }
}
```

Maps container paths to host paths.

## Category Object

```json
{
  "id": "utilities",
  "name": "Utilities",
  "description": "General-purpose utility servers"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (kebab-case recommended) |
| `name` | string | Yes | Display name |
| `description` | string | No | Category description |

## Standard Categories

Recommended category IDs:

- `utilities` - General-purpose utilities
- `development` - Development tools
- `communication` - Messaging and communication
- `database` - Database management
- `ai` - AI and machine learning
- `cloud` - Cloud services
- `payments` - Payment processing
- `project-management` - Project management
- `productivity` - Productivity tools
- `security` - Security tools
- `monitoring` - Monitoring and observability
- `testing` - Testing tools

## Complete Example

```json
{
  "version": "1.0",
  "metadata": {
    "name": "Example MCP Catalog",
    "description": "A sample catalog",
    "maintainer": "Example Org",
    "last_updated": "2024-01-01T00:00:00Z"
  },
  "servers": [
    {
      "id": "mcp-server-github",
      "name": "GitHub MCP Server",
      "description": "Interact with GitHub repositories and issues",
      "category": "development",
      "docker_image": "mcp/github:latest",
      "default_env": {
        "PORT": "8080",
        "GITHUB_TOKEN": "{{ bw:github-token:token }}",
        "GITHUB_API_URL": "https://api.github.com"
      },
      "required_secrets": ["GITHUB_TOKEN"],
      "documentation_url": "https://github.com/example/mcp-github",
      "tags": ["github", "git", "version-control"],
      "ports": {
        "8080/tcp": 8080
      }
    },
    {
      "id": "mcp-server-postgres",
      "name": "PostgreSQL MCP Server",
      "description": "Execute SQL queries on PostgreSQL",
      "category": "database",
      "docker_image": "mcp/postgres:latest",
      "default_env": {
        "PORT": "8080",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "mydb",
        "POSTGRES_USER": "{{ bw:postgres-creds:username }}",
        "POSTGRES_PASSWORD": "{{ bw:postgres-creds:password }}"
      },
      "required_secrets": ["POSTGRES_USER", "POSTGRES_PASSWORD"],
      "documentation_url": "https://github.com/example/mcp-postgres",
      "tags": ["postgresql", "database", "sql"]
    }
  ],
  "categories": [
    {
      "id": "development",
      "name": "Development",
      "description": "Development and version control tools"
    },
    {
      "id": "database",
      "name": "Database",
      "description": "Database management and query tools"
    }
  ]
}
```

## Validation Rules

1. **Required Fields**: All required fields must be present
2. **Unique IDs**: Server and category IDs must be unique within the catalog
3. **Valid Categories**: Server `category` must reference a defined category ID
4. **Docker Images**: Must be valid Docker image names
5. **URLs**: Must be valid HTTP/HTTPS URLs
6. **Bitwarden References**: Must follow the format `{{ bw:item-id:field }}`

## Hosting Your Catalog

### Option 1: GitHub

Host your catalog in a GitHub repository:

```
https://raw.githubusercontent.com/username/repo/main/catalog.json
```

### Option 2: Static Hosting

Host on any static file server:
- AWS S3
- Google Cloud Storage
- Netlify
- Vercel
- Your own web server

### Option 3: CDN

Use a CDN for better performance:
- Cloudflare
- AWS CloudFront
- Fastly

## Best Practices

1. **Keep it Updated**: Regularly update the `last_updated` timestamp
2. **Semantic Versioning**: Use semantic versioning for Docker image tags
3. **Clear Descriptions**: Write clear, concise descriptions
4. **Useful Tags**: Add relevant tags for better searchability
5. **Documentation**: Always provide a documentation URL
6. **Test Images**: Ensure all Docker images are publicly accessible
7. **Security**: Never include actual secrets in the catalog
8. **Validation**: Validate your catalog JSON before publishing

## Testing Your Catalog

1. **JSON Validation**: Use a JSON validator to check syntax
2. **Schema Validation**: Validate against the schema
3. **Manual Testing**: Load the catalog in the console and test installation
4. **Image Availability**: Verify all Docker images can be pulled

## Example Validation Script

```bash
#!/bin/bash
# validate-catalog.sh

# Check JSON syntax
jq empty catalog.json || exit 1

# Check required fields
jq -e '.version' catalog.json > /dev/null || exit 1
jq -e '.servers' catalog.json > /dev/null || exit 1

# Check server IDs are unique
DUPLICATES=$(jq -r '.servers[].id' catalog.json | sort | uniq -d)
if [ -n "$DUPLICATES" ]; then
  echo "Duplicate server IDs found: $DUPLICATES"
  exit 1
fi

echo "Catalog validation passed!"
```

## Updating the Catalog

When you update your catalog:

1. Update the `last_updated` timestamp
2. Increment version numbers for changed servers
3. Test all changes locally
4. Commit and push to your hosting location
5. The console will automatically fetch updates based on cache TTL

## Support

For questions or issues with the catalog schema:
- Review this documentation
- Check the sample catalog: `docs/sample-catalog.json`
- Open an issue on GitHub
