# Project Structure

## Organization Philosophy

Separation of concerns between Frontend (UI/Interaction) and Backend (System/Docker ops).

## Directory Patterns

### Frontend Application
**Location**: `/frontend/`
**Purpose**: Next.js web application
- `app/`: App Router pages and layouts
- `components/`: Reusable UI components
- `lib/`: Utilities and hooks

### Backend Application
**Location**: `/backend/`
**Purpose**: REST API and orchestration
- `app/api/`: Route handlers
- `app/services/`: Core business logic (Docker, Auth)
- `app/models/`: Pydantic data schemas

## Naming Conventions

- **React Components**: PascalCase (e.g., `ServerCard.tsx`)
- **Python Modules**: snake_case (e.g., `docker_service.py`)
- **API Routes**: Kebab-case URLs, grouped by resource

## Import Organization

- **Frontend**: Prefer `@/` alias for root-relative imports.
- **Backend**: Absolute imports from `app.` (e.g., `from app.models import User`).

## Code Organization Principles

- **Services Layer**: Backend logic should reside in `services/`, not route handlers.
- **Secret Safety**: Secrets are never stored on disk; passed via environment or in-memory.
