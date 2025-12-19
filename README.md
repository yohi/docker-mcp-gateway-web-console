[日本語 (Japanese)](README.ja.md)

# Docker MCP Gateway Console

A comprehensive web console for managing Docker-based MCP (Model Context Protocol) servers with Bitwarden integration for secure secret management. This application provides a user-friendly interface to deploy, configure, and monitor MCP servers while keeping your API keys and sensitive credentials secure.

## Features

- 🔐 **Bitwarden Authentication**: Secure login using Bitwarden API keys or master password
- 🐳 **Container Lifecycle Management**: Start, stop, restart, and delete MCP server containers
- 📦 **Catalog Browser**: Browse and install MCP servers from curated catalogs
- 🔍 **MCP Inspector**: Analyze server capabilities (Tools, Resources, Prompts)
- ⚙️ **Gateway Config Editor**: Visual editor for MCP gateway configuration
- 🔒 **Secure Secret Injection**: Reference Bitwarden secrets without storing them on disk
- 📊 **Real-time Monitoring**: Live container status updates and log streaming
- 🎨 **Modern UI**: Responsive design with Tailwind CSS

## Architecture

- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS
- **Backend**: Python 3.14, FastAPI, Docker SDK
- **Secret Management**: Bitwarden CLI integration with in-memory caching
- **Container Management**: Docker Engine with real-time log streaming
- **Communication**: REST API + WebSocket for log streaming

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js 22+**: [Download](https://nodejs.org/)
- **Python 3.14+**: [Download](https://www.python.org/downloads/)
- **Docker Engine 20.10+**: [Install Docker](https://docs.docker.com/engine/install/)
- **Bitwarden CLI 2023.x+**: [Install Bitwarden CLI](https://bitwarden.com/help/cli/)
- **Docker Compose**: Usually included with Docker Desktop
- **Bitwarden Account**: You'll need a Bitwarden account with a vault containing your secrets

### Installing Bitwarden CLI

```bash
# macOS (using Homebrew)
brew install bitwarden-cli

# Linux (using npm)
npm install -g @bitwarden/cli

# Verify installation
bw --version
```

## Quick Start

**New to the project?** Check out the [Quick Start Guide](docs/QUICK_START.md) for a 5-minute setup!

### Option 1: Development with DevContainer (Recommended for VS Code)

This project includes a DevContainer configuration that provides a consistent development environment with Python 3.14 and Node.js 22 pre-installed.
The container forwards ports 3000 (frontend) and 8000 (backend API), and runs a post-create script to install backend/frontend dependencies.

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd docker-mcp-gateway-console
    ```

2.  **Open in VS Code:**
    ```bash
    code .
    ```

3.  **Reopen in Container:**
    - When prompted, click "Reopen in Container".
    - Or open the Command Palette (Ctrl+Shift+P / Cmd+Shift+P) and run "Dev Containers: Reopen in Container".

4.  **Start Services:**
    The DevContainer automatically installs dependencies (via `.devcontainer/post-create.sh`). You can start the services from the integrated terminal:
    ```bash
    # Backend
    cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    # Frontend (in a new terminal)
    cd frontend && npm run dev
    ```

### Option 2: Development with Docker Compose

1. **Clone the repository:**
```bash
git clone <repository-url>
cd docker-mcp-gateway-console
```

2. **Set up environment variables:**
```bash
# Frontend
cp frontend/.env.local.example frontend/.env.local
# Edit frontend/.env.local if needed

# Backend
cp backend/.env.example backend/.env
# Edit backend/.env if needed
```

3. **Start the development environment:**
```bash
docker-compose up
```

4. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

5. **Login with Bitwarden:**
   - Open http://localhost:3000
   - Enter your Bitwarden email and API key (or master password)
   - Start managing your MCP servers!

### Option 3: Local Development (Without Docker Compose)

This option is useful for development when you want to run services individually.

### Running E2E Tests

To run the complete E2E test suite:

```bash
# Using the provided script
./scripts/run-e2e-tests.sh

# Or manually with Docker Compose
docker-compose -f docker-compose.test.yml up -d frontend backend
cd frontend
npm run test:e2e
```

See [frontend/e2e/README.md](frontend/e2e/README.md) for detailed testing documentation.

#### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at http://localhost:8000

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.local.example .env.local
# Edit .env.local with your backend URL

# Run the frontend
npm run dev
```

Frontend will be available at http://localhost:3000

## Infrastructure Notes

- **DevContainer**: DevContainer support is implemented via scripts and a workspace image under `.devcontainer/` (this repository does not include a `.devcontainer/docker-compose.devcontainer.yml` or a `workspace` service definition in the repo).
- **Docker Socket**: `.devcontainer/init-docker-socket.sh` detects an available Docker socket (rootful `/var/run/docker.sock` and rootless sockets under `$XDG_RUNTIME_DIR/docker.sock` or `/run/user/<uid>/docker.sock`) and prints `DOCKER_SOCKET=...` for consumption by the container tooling.
- **Workspace Image**: `.devcontainer/Dockerfile.workspace` defines the unified development image, based on Python `3.14.2-slim` and a pinned Node.js `22.21.1`, and includes the Docker CLI. After updating the base image, rebuild the devcontainer to pick up the new image.
- **Post-create Setup**: `.devcontainer/post-create.sh` performs post-create provisioning by installing backend Python dependencies (`pip install -r backend/requirements.txt`) and frontend dependencies (`npm ci` in `frontend/`), logging output to `.devcontainer/.post-create.log`.

## Project Structure

```
docker-mcp-gateway-console/
├── frontend/                 # Next.js frontend application
│   ├── app/                 # Next.js App Router pages
│   ├── components/          # React components
│   ├── lib/                 # Utility functions
│   └── public/              # Static assets
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── api/            # API route handlers
│   │   ├── models/         # Pydantic models
│   │   ├── services/       # Business logic services
│   │   ├── config.py       # Configuration management
│   │   └── main.py         # FastAPI application
│   └── tests/              # Backend tests
├── docker-compose.yml       # Development environment
└── README.md
```

## Usage Guide

### First Time Setup

1. **Prepare your Bitwarden Vault:**
   - Create items in Bitwarden for your API keys and secrets
   - Note the item IDs (you can find these in the Bitwarden web vault URL)

2. **Login to the Console:**
   - Navigate to http://localhost:3000
   - Enter your Bitwarden email
   - Choose authentication method:
     - **API Key** (recommended): Generate from Bitwarden settings
     - **Master Password**: Your Bitwarden master password

3. **Browse the Catalog:**
   - Go to the Catalog page
   - Search for MCP servers by keyword or category
   - Click "Install" on any server you want to deploy

4. **Configure and Launch:**
   - Fill in the container configuration
   - Use Bitwarden reference notation for secrets: `{{ bw:item-id:field }}`
   - Example: `{{ bw:abc123:password }}` references the "password" field of item "abc123"
   - Click "Start Container"

5. **Monitor and Inspect:**
   - View container status on the Dashboard
   - Click "Logs" to see real-time output
   - Click "Inspect" to view MCP server capabilities (Tools, Resources, Prompts)

### Bitwarden Reference Notation

To securely reference secrets from your Bitwarden vault:

**Format:** `{{ bw:item-id:field }}`

**Examples:**
- `{{ bw:a1b2c3d4:password }}` - References the password field
- `{{ bw:e5f6g7h8:api_key }}` - References a custom field named "api_key"
- `{{ bw:i9j0k1l2:username }}` - References the username field

**Finding Item IDs:**
1. Open Bitwarden web vault
2. Click on an item
3. The item ID is in the URL: `https://vault.bitwarden.com/#/vault?itemId=YOUR-ITEM-ID`

## Configuration

See [ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) for detailed configuration options.

## Testing

We provide a unified test runner script that works across host, DevContainer, and CI environments.

### Unified Test Runner (Recommended)

```bash
# Run all tests (Backend, Frontend, E2E)
./scripts/run-tests.sh all

# Run specific test suites
./scripts/run-tests.sh backend
./scripts/run-tests.sh frontend
./scripts/run-tests.sh e2e
```

### Manual Test Execution

#### Frontend Unit Tests

```bash
cd frontend
npm test
```

#### Frontend E2E Tests

```bash
cd frontend

# Install Playwright browsers (first time only)
npx playwright install

# Run E2E tests
npm run test:e2e

# Run E2E tests with UI mode
npm run test:e2e:ui

# Run E2E tests in headed mode
npm run test:e2e:headed
```

Note: these `test:e2e*` scripts are defined in `frontend/package.json` (there is no `package.json` at the repository root).

See [frontend/e2e/README.md](frontend/e2e/README.md) for detailed E2E testing documentation.

#### Backend Tests

```bash
cd backend
pytest
```

## Deployment

For production deployment instructions, see [DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Troubleshooting

### Common Issues

### DevContainer fails to start
- Ensure Docker is running.
- Try `Dev Containers: Rebuild Container` from VS Code.
- Check if ports 3000 or 8000 are already in use on your host.

### Docker socket permission denied in DevContainer
- If using Linux, ensure your user is in the `docker` group.
- For rootless Docker, ensure the socket path is correctly detected (check `.devcontainer/init-docker-socket.sh`).

**"Bitwarden CLI not found"**
- Ensure Bitwarden CLI is installed: `bw --version`
- Update `BITWARDEN_CLI_PATH` in backend `.env` file

**"Cannot connect to Docker daemon"**
- Ensure Docker is running: `docker ps`
- Check `DOCKER_HOST` in backend `.env` file
- On Linux, ensure your user is in the `docker` group

**"Session timeout"**
- Sessions expire after 30 minutes of inactivity
- Simply log in again to create a new session

**"Container fails to start"**
- Check container logs in the UI
- Verify Bitwarden references are correct
- Ensure the Docker image exists and is accessible

### Getting Help

- Check the [FAQ](docs/FAQ.md)
- Review [Requirements](.kiro/specs/docker-mcp-gateway-console/requirements.md)
- Review [Design Documentation](.kiro/specs/docker-mcp-gateway-console/design.md)

## Documentation

### Getting Started
- [Quick Start Guide](docs/QUICK_START.md) - Get up and running in 5 minutes
- [FAQ](docs/FAQ.md) - Frequently asked questions

### Configuration & Deployment
- [Environment Variables](docs/ENVIRONMENT_VARIABLES.md) - Complete configuration reference
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions

### Development
- [Architecture Documentation](docs/ARCHITECTURE.md) - System architecture and design
- [Contributing Guide](CONTRIBUTING.md) - How to contribute to the project
- [API Documentation](http://localhost:8000/docs) - Interactive API docs (when running)
- [E2E Testing Guide](frontend/e2e/README.md) - End-to-end testing documentation

### Catalog
- [Catalog Schema](docs/CATALOG_SCHEMA.md) - How to create your own catalog
- [Sample Catalog](docs/sample-catalog.json) - Example catalog file

### Specifications
- [Requirements Specification](.kiro/specs/docker-mcp-gateway-console/requirements.md)
- [Design Document](.kiro/specs/docker-mcp-gateway-console/design.md)
- [Implementation Tasks](.kiro/specs/docker-mcp-gateway-console/tasks.md)

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) before submitting pull requests.

### How to Contribute

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Security

- Secrets are never written to disk
- All secrets are stored in memory only during the session
- Sessions automatically expire after 30 minutes of inactivity
- Use HTTPS in production environments

## License

[Add your license here]
