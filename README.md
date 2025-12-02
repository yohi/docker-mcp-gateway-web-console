# Docker MCP Gateway Console

Web console for managing Docker-based MCP (Model Context Protocol) servers with Bitwarden integration for secure secret management.

## Features

- 🔐 Bitwarden authentication and secret management
- 🐳 Docker container lifecycle management
- 📦 MCP server catalog browsing and installation
- 🔍 MCP Inspector for analyzing server capabilities
- ⚙️ Gateway configuration editor
- 🔒 Secure secret injection without disk persistence

## Architecture

- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS
- **Backend**: Python 3.11+, FastAPI, Docker SDK
- **Secret Management**: Bitwarden CLI integration
- **Container Management**: Docker Engine

## Prerequisites

- Node.js 18+
- Python 3.11+
- Docker Engine 20.10+
- Bitwarden CLI 2023.x+
- Docker Compose (for development)

## Quick Start

### Development with Docker Compose

1. Clone the repository:
```bash
git clone <repository-url>
cd docker-mcp-gateway-console
```

2. Set up environment variables:
```bash
# Frontend
cp frontend/.env.local.example frontend/.env.local

# Backend
cp backend/.env.example backend/.env
```

3. Start the development environment:
```bash
docker-compose up
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Local Development

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

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

## Environment Variables

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (.env)

```env
BITWARDEN_CLI_PATH=/usr/local/bin/bw
DOCKER_HOST=unix:///var/run/docker.sock
SESSION_TIMEOUT_MINUTES=30
CATALOG_CACHE_TTL_SECONDS=3600
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

## Testing

### Frontend Tests

```bash
cd frontend
npm test
```

### Backend Tests

```bash
cd backend
pytest
```

## Documentation

For detailed documentation, see:
- [Requirements](.kiro/specs/docker-mcp-gateway-console/requirements.md)
- [Design](.kiro/specs/docker-mcp-gateway-console/design.md)
- [Implementation Tasks](.kiro/specs/docker-mcp-gateway-console/tasks.md)

## License

[Add your license here]
