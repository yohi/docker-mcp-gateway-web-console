# Technology Stack

## Architecture

Client-Server architecture with Next.js frontend communicating with a Python FastAPI backend. The backend manages local Docker daemon and interacts with Bitwarden CLI.

## Core Technologies

- **Language**: TypeScript (Frontend), Python 3.11+ (Backend)
- **Framework**: Next.js 14 (App Router), FastAPI
- **Runtime**: Node.js (Frontend Build), Python (Backend)
- **Styling**: Tailwind CSS

## Key Libraries

### Frontend
- **SWR**: Data fetching and caching
- **React 18**: UI Library

### Backend
- **Docker SDK**: Container management
- **Pydantic**: Data validation
- **Uvicorn**: ASGI Server

## Development Standards

### Type Safety
- TypeScript strict mode for frontend.
- Python type hints with Pydantic for backend.

### Testing
- **Frontend**: Jest (Unit), Playwright (E2E)
- **Backend**: Pytest

## Development Environment

### Required Tools
- Docker Engine & Docker Compose
- Node.js 18+
- Python 3.11+
- Bitwarden CLI

### Common Commands
```bash
# Start Dev
docker-compose up

# Backend Tests
cd backend && pytest

# Frontend E2E
cd frontend && npm run test:e2e
```
