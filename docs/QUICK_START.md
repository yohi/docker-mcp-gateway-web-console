[日本語 (Japanese)](QUICK_START.ja.md)

# Quick Start Guide

Get up and running with Docker MCP Gateway Console in 5 minutes!

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Docker installed and running
- [ ] Node.js 18+ installed
- [ ] Python 3.11+ installed
- [ ] Bitwarden CLI installed
- [ ] A Bitwarden account with at least one item containing secrets

## Step 1: Install Bitwarden CLI (2 minutes)

### macOS
```bash
brew install bitwarden-cli
```

### Linux
```bash
npm install -g @bitwarden/cli
```

### Verify Installation
```bash
bw --version
# Should output: 2023.x.x or later
```

## Step 2: Clone and Setup (2 minutes)

```bash
# Clone the repository
git clone <repository-url>
cd docker-mcp-gateway-console

# Copy environment files
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env

# Start with Docker Compose
docker-compose up -d
```

## Step 3: Access the Application (30 seconds)

Open your browser and navigate to:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs

## Step 4: Login with Bitwarden (1 minute)

### Option A: Using API Key (Recommended)

1. Go to Bitwarden web vault → Settings → Security → Keys
2. Click "View API Key"
3. Copy your `client_id` and `client_secret`
4. In the console login page:
   - Enter your Bitwarden email
   - Select "API Key" method
   - Paste your credentials
   - Click "Login"

### Option B: Using Master Password

1. In the console login page:
   - Enter your Bitwarden email
   - Select "Master Password" method
   - Enter your master password
   - Click "Login"

## Step 5: Deploy Your First MCP Server (2 minutes)

### Prepare a Secret in Bitwarden

1. Open Bitwarden web vault
2. Create a new item (e.g., "GitHub Token")
3. Add a custom field named "token" with your GitHub personal access token
4. Note the item ID from the URL

### Install from Catalog

1. Click "Catalog" in the navigation
2. Search for "GitHub" (or any server you want)
3. Click "Install"
4. Configure the environment variables:
   - For `GITHUB_TOKEN`, enter: `{{ bw:YOUR-ITEM-ID:token }}`
   - Replace `YOUR-ITEM-ID` with your actual Bitwarden item ID
5. Click "Start Container"

### Verify It's Running

1. Go to "Dashboard"
2. You should see your container with status "Running"
3. Click "Logs" to see the container output
4. Click "Inspect" to see available Tools, Resources, and Prompts

## What's Next?

### Explore Features

- **Dashboard**: Monitor all your running containers
- **Catalog**: Browse and install more MCP servers
- **Config Editor**: Manage your gateway configuration
- **Inspector**: Analyze MCP server capabilities

### Add More Servers

Repeat Step 5 to add more MCP servers from the catalog.

### Create Custom Configurations

1. Click "New Container" in the Dashboard
2. Enter any Docker image
3. Configure environment variables with Bitwarden references
4. Start the container

## Common First-Time Issues

### "Bitwarden CLI not found"

**Solution:**
```bash
# Verify installation
which bw

# If not found, install it
npm install -g @bitwarden/cli

# Update backend .env
echo "BITWARDEN_CLI_PATH=$(which bw)" >> backend/.env
```

### "Cannot connect to Docker daemon"

**Solution:**
```bash
# Check Docker is running
docker ps

# On Linux, add user to docker group
sudo usermod -aG docker $USER
# Then log out and back in
```

### "Invalid Bitwarden reference"

**Solution:**
- Double-check the item ID in Bitwarden web vault URL
- Ensure field name matches exactly (case-sensitive)
- Format must be: `{{ bw:item-id:field }}`

### "Session expired"

**Solution:**
- Sessions expire after 30 minutes of inactivity
- Simply log in again

## Quick Reference

### Bitwarden Reference Format

```
{{ bw:item-id:field }}
```

**Examples:**
- `{{ bw:abc123:password }}` - Password field
- `{{ bw:def456:username }}` - Username field
- `{{ bw:ghi789:api_key }}` - Custom field named "api_key"

### Finding Item IDs

1. Open Bitwarden web vault
2. Click on an item
3. Look at the URL: `...?itemId=YOUR-ITEM-ID`

### Useful Commands

```bash
# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Update and restart
git pull
docker-compose up -d --build
```

## Getting Help

- **Documentation**: Check the [main README](../README.md)
- **FAQ**: See [FAQ.md](FAQ.md)
- **Issues**: Report bugs on GitHub
- **Logs**: Check application logs for errors

## Next Steps

1. **Read the Full Documentation**: [README.md](../README.md)
2. **Explore Environment Variables**: [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md)
3. **Learn About Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
4. **Create Your Own Catalog**: [CATALOG_SCHEMA.md](CATALOG_SCHEMA.md)

## Tips for Success

1. **Start Simple**: Begin with one or two servers
2. **Use API Keys**: Easier than master password authentication
3. **Organize Secrets**: Keep your Bitwarden vault organized
4. **Check Logs**: Always check container logs if something doesn't work
5. **Read Docs**: Each MCP server may have specific requirements

## Example Workflow

Here's a typical workflow after setup:

1. **Morning**: Log in to the console
2. **Browse**: Check the catalog for new servers
3. **Install**: Add a server you need (e.g., Slack integration)
4. **Configure**: Set up environment variables with Bitwarden references
5. **Deploy**: Start the container
6. **Monitor**: Check logs and status
7. **Use**: The MCP server is now available for your AI tools
8. **Evening**: Containers keep running, session expires automatically

## Congratulations! 🎉

You're now ready to manage MCP servers with secure secret management!

For more advanced usage, check out the full documentation.
