# Frequently Asked Questions (FAQ)

## General Questions

### What is Docker MCP Gateway Console?

Docker MCP Gateway Console is a web-based management interface for Docker-based MCP (Model Context Protocol) servers. It provides secure secret management through Bitwarden integration, allowing you to deploy and manage MCP servers without storing sensitive credentials on disk.

### What is MCP (Model Context Protocol)?

MCP is a protocol that enables AI models to interact with external tools, resources, and data sources. MCP servers provide specific capabilities (like file system access, API integrations, database queries) that AI models can use.

### Why use Bitwarden for secret management?

Bitwarden provides:
- Secure, encrypted storage for API keys and credentials
- Easy reference system without storing secrets in configuration files
- Centralized secret management across multiple services
- Industry-standard security practices

## Installation & Setup

### Do I need a Bitwarden account?

Yes, you need a Bitwarden account to use this application. The free tier is sufficient for personal use.

### Can I use Bitwarden self-hosted?

Yes, the application works with both Bitwarden cloud and self-hosted instances. Configure the Bitwarden CLI to point to your self-hosted instance.

### What if I don't have Docker installed?

Docker is required to run MCP servers as containers. Follow the [Docker installation guide](https://docs.docker.com/engine/install/) for your operating system.

### Can I run this on Windows?

Yes, but Docker Desktop for Windows is required. The application works best on Linux or macOS for production use.

## Authentication & Security

### How do I get a Bitwarden API key?

1. Log in to your Bitwarden web vault
2. Go to Settings → Security → Keys
3. Click "View API Key"
4. Copy your client_id and client_secret

### Is my master password stored anywhere?

No. If you authenticate with your master password, it's used only to obtain a session token and is immediately discarded from memory.

### How long do sessions last?

Sessions expire after 30 minutes of inactivity by default. This can be configured via the `SESSION_TIMEOUT_MINUTES` environment variable.

### Are my secrets stored on disk?

No. All secrets are kept in memory only during your session and are never written to disk or log files.

### What happens to cached secrets when I log out?

All cached secrets are immediately cleared from memory when you log out or when your session expires.

## Using the Application

### How do I reference a Bitwarden secret?

Use the format: `{{ bw:item-id:field }}`

Example: `{{ bw:abc123:password }}`

Where:
- `abc123` is the Bitwarden item ID
- `password` is the field name (password, username, or custom field)

### How do I find my Bitwarden item ID?

1. Open Bitwarden web vault
2. Click on an item
3. Look at the URL: `https://vault.bitwarden.com/#/vault?itemId=YOUR-ITEM-ID`
4. Copy the item ID from the URL

### Can I use custom fields in Bitwarden?

Yes! Create custom fields in your Bitwarden items and reference them by name:
`{{ bw:item-id:my_custom_field }}`

### What if a container fails to start?

1. Check the container logs in the UI
2. Verify all Bitwarden references are correct
3. Ensure the Docker image exists and is accessible
4. Check that required environment variables are set

### How do I update a running container?

1. Stop the container
2. Update the configuration if needed
3. Restart the container

Or delete and recreate the container with new settings.

## Catalog

### Where does the catalog come from?

The catalog is fetched from a URL specified in your configuration. You can use the provided sample catalog or create your own.

### Can I create my own catalog?

Yes! Create a JSON file following the catalog schema (see `docs/sample-catalog.json`) and host it anywhere accessible via HTTP/HTTPS.

### How often is the catalog refreshed?

The catalog is cached for 1 hour by default (configurable via `CATALOG_CACHE_TTL_SECONDS`). You can manually refresh by reloading the page.

### Can I add servers not in the catalog?

Yes! Use the "New Container" option to manually configure and start any Docker image.

## MCP Inspector

### What does the Inspector show?

The Inspector displays:
- **Tools**: Functions the MCP server provides
- **Resources**: Data sources the server can access
- **Prompts**: Pre-defined prompt templates

### Why can't I inspect a container?

Possible reasons:
- Container is not running
- MCP server hasn't fully started yet
- Network connectivity issues
- MCP server doesn't support the inspection protocol

### How do I know what parameters a tool needs?

The Inspector shows the input schema for each tool, including required and optional parameters.

## Troubleshooting

### "Bitwarden CLI not found" error

**Solution:**
1. Install Bitwarden CLI: `npm install -g @bitwarden/cli`
2. Verify installation: `bw --version`
3. Update `BITWARDEN_CLI_PATH` in backend `.env` file

### "Cannot connect to Docker daemon" error

**Solution:**
1. Ensure Docker is running: `docker ps`
2. Check Docker socket permissions
3. On Linux, add your user to the docker group: `sudo usermod -aG docker $USER`
4. Verify `DOCKER_HOST` in backend `.env` file

### "Session expired" message

**Solution:**
Simply log in again. Sessions expire after 30 minutes of inactivity for security.

### Container logs not showing

**Solution:**
1. Ensure the container is running
2. Check browser console for WebSocket errors
3. Verify backend is accessible
4. Try refreshing the page

### "Invalid Bitwarden reference" error

**Solution:**
1. Verify the item ID is correct
2. Ensure the field name matches exactly (case-sensitive)
3. Check that you have access to the item in your vault
4. Verify the reference format: `{{ bw:item-id:field }}`

### Frontend can't connect to backend

**Solution:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `NEXT_PUBLIC_API_URL` in frontend `.env.local`
3. Ensure CORS is configured correctly in backend
4. Check firewall rules

### Docker image pull fails

**Solution:**
1. Check internet connectivity
2. Verify the image name is correct
3. For private images, ensure Docker is authenticated
4. Check Docker Hub rate limits

## Performance

### Why is the catalog slow to load?

The first load fetches from the remote URL. Subsequent loads use the cache. Increase `CATALOG_CACHE_TTL_SECONDS` for longer caching.

### Can I run multiple containers simultaneously?

Yes, there's no limit on the number of containers you can run, subject to your system resources.

### How much memory does the application use?

- Frontend: ~100-200MB
- Backend: ~200-300MB
- Each MCP container: Varies by server (typically 50-500MB)

### How do I optimize performance?

1. Increase cache TTLs for catalog and secrets
2. Use Docker image caching
3. Allocate sufficient system resources
4. Use SSD storage for Docker

## Development

### How do I contribute?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

### How do I run tests?

```bash
# Frontend tests
cd frontend
npm test

# Backend tests
cd backend
pytest

# E2E tests
cd frontend
npm run test:e2e
```

### Where is the API documentation?

When running the backend, visit http://localhost:8000/docs for interactive API documentation.

### Can I extend the application?

Yes! The application is designed to be extensible:
- Add new catalog sources
- Create custom MCP server integrations
- Extend the UI with new features
- Add new secret management backends

## Deployment

### Can I deploy this to production?

Yes! See the [Deployment Guide](DEPLOYMENT.md) for detailed instructions.

### What are the minimum server requirements?

- 2 CPU cores
- 4GB RAM
- 20GB disk space
- Linux OS (Ubuntu 22.04 LTS recommended)

### Do I need HTTPS in production?

Yes, HTTPS is strongly recommended for production to protect credentials and session tokens.

### Can I use a different reverse proxy?

Yes, while the guide uses Nginx, you can use Caddy, Traefik, or any other reverse proxy.

### How do I backup my data?

See the [Deployment Guide](DEPLOYMENT.md) backup section. Key items to backup:
- Configuration files (.env)
- Gateway configurations
- SSL certificates

## Support

### Where can I get help?

1. Check this FAQ
2. Review the [documentation](../README.md)
3. Check [GitHub Issues](repository-url/issues)
4. Review application logs

### How do I report a bug?

1. Check if the issue already exists in GitHub Issues
2. Gather relevant information (logs, steps to reproduce)
3. Create a new issue with detailed description

### How do I request a feature?

Create a GitHub Issue with the "enhancement" label and describe:
- The feature you'd like
- Why it would be useful
- Any implementation ideas

### Is there a community?

Check the repository for links to:
- Discord server
- Discussion forums
- Mailing lists

## License & Legal

### What license is this under?

[Check the LICENSE file in the repository]

### Can I use this commercially?

[Depends on the license - update based on your chosen license]

### Are there any usage restrictions?

Follow the terms of the license and ensure compliance with:
- Bitwarden's terms of service
- Docker's terms of service
- Any third-party MCP server licenses
