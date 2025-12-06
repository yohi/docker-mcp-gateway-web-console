# Architecture Documentation

This document provides a detailed overview of the Docker MCP Gateway Console architecture.

## System Overview

The Docker MCP Gateway Console is a three-tier web application designed to manage Docker-based MCP servers with secure secret management through Bitwarden integration.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │           Next.js Frontend (React)                  │    │
│  │  • Authentication UI                                │    │
│  │  • Catalog Browser                                  │    │
│  │  • Container Dashboard                              │    │
│  │  • Config Editor                                    │    │
│  │  • MCP Inspector                                    │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS / WebSocket
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Auth Service │  │Catalog Service│  │Container Svc │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │Config Service│  │Inspector Svc  │  │Secret Manager│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                │                        │
                │                        │
                ▼                        ▼
┌──────────────────────┐    ┌──────────────────────┐
│   Docker Engine      │    │  Bitwarden Vault     │
│  • Container CRUD    │    │  • Secret Storage    │
│  • Log Streaming     │    │  • API/CLI Access    │
└──────────────────────┘    └──────────────────────┘
```

## Component Architecture

### Frontend Layer

#### Technology Stack
- **Framework**: Next.js 14 with App Router
- **UI Library**: React 18
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: React Context API + SWR
- **HTTP Client**: Fetch API
- **WebSocket**: Native WebSocket API

#### Key Components

1. **Authentication Module** (`/app/auth`)
   - Login form with Bitwarden integration
   - Session management
   - Protected route wrapper

2. **Catalog Browser** (`/app/catalog`)
   - Server listing and search
   - Category filtering
   - Installation workflow

3. **Container Dashboard** (`/app/dashboard`, `/app/containers`)
   - Container list with status
   - Lifecycle controls (start/stop/restart/delete)
   - Real-time log viewer
   - Container configurator

4. **Config Editor** (`/app/config`)
   - Gateway configuration form
   - Bitwarden reference input
   - Real-time validation

5. **MCP Inspector** (`/app/inspector`)
   - Tools list viewer
   - Resources list viewer
   - Prompts list viewer

#### Data Flow

```
User Action → Component → API Call → Backend
                ↓
         State Update (SWR/Context)
                ↓
            UI Re-render
```

### Backend Layer

#### Technology Stack
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Validation**: Pydantic
- **Docker Integration**: Docker SDK for Python
- **Bitwarden Integration**: Bitwarden CLI
- **Async Runtime**: asyncio

#### Service Architecture

```
┌─────────────────────────────────────────────────┐
│              API Layer (FastAPI)                 │
│  • Route handlers                                │
│  • Request validation                            │
│  • Response serialization                        │
│  • Error handling                                │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│              Service Layer                       │
│  ┌──────────────────────────────────────────┐  │
│  │ Auth Service                              │  │
│  │  • Bitwarden authentication              │  │
│  │  • Session management                    │  │
│  │  • Token validation                      │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Secret Manager                            │  │
│  │  • Reference parsing                     │  │
│  │  • Bitwarden CLI interaction             │  │
│  │  • In-memory caching                     │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Container Service                         │  │
│  │  • Docker API interaction                │  │
│  │  • Container lifecycle                   │  │
│  │  • Log streaming                         │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Catalog Service                           │  │
│  │  • Catalog fetching                      │  │
│  │  • Search and filtering                  │  │
│  │  • Caching                               │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Config Service                            │  │
│  │  • Configuration CRUD                    │  │
│  │  • Validation                            │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Inspector Service                         │  │
│  │  • MCP protocol communication            │  │
│  │  • Capability discovery                  │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│           External Integrations                  │
│  • Docker Engine                                 │
│  • Bitwarden CLI                                 │
│  • MCP Servers                                   │
└─────────────────────────────────────────────────┘
```

## Data Models

### Core Entities

#### Session
```python
class Session:
    session_id: str          # UUID v4
    user_email: str          # Bitwarden email
    bw_session_key: str      # Bitwarden CLI session
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
```

#### Container Configuration
```python
class ContainerConfig:
    name: str
    image: str
    env: Dict[str, str]      # May contain Bitwarden references
    ports: Dict[str, int]
    volumes: Dict[str, str]
    labels: Dict[str, str]
```

#### Catalog Item
```python
class CatalogItem:
    id: str
    name: str
    description: str
    category: str
    docker_image: str
    default_env: Dict[str, str]
    required_secrets: List[str]
    documentation_url: str
    tags: List[str]
```

## Security Architecture

### Authentication Flow

```
1. User enters credentials
   ↓
2. Frontend sends to /api/auth/login
   ↓
3. Backend authenticates with Bitwarden CLI
   ↓
4. Session created with UUID
   ↓
5. Session ID returned to frontend
   ↓
6. Frontend stores in memory (Context)
   ↓
7. All subsequent requests include session ID
```

### Secret Management Flow

```
1. User enters Bitwarden reference: {{ bw:item-id:field }}
   ↓
2. Reference stored in configuration (not resolved)
   ↓
3. On container start:
   a. Parse all Bitwarden references
   b. Check in-memory cache
   c. If not cached, fetch from Bitwarden
   d. Cache in memory (session-scoped)
   e. Inject into container environment
   ↓
4. Container starts with resolved secrets
   ↓
5. On session end: Clear all cached secrets
```

### Security Principles

1. **No Disk Persistence**: Secrets never written to disk
2. **Memory-Only Storage**: Secrets kept in memory during session
3. **Session Isolation**: Each session has isolated cache
4. **Automatic Cleanup**: Secrets cleared on logout/timeout
5. **Minimal Exposure**: Secrets only exposed to target containers

## Communication Patterns

### REST API

Standard request/response for most operations:

```
GET /api/containers
→ Returns list of containers

POST /api/containers
→ Creates new container

PUT /api/config/gateway
→ Updates gateway configuration
```

### WebSocket

Real-time log streaming:

```
WebSocket /api/containers/{id}/logs
→ Streams container logs in real-time
→ Bidirectional communication
→ Automatic reconnection on disconnect
```

### Event Flow

```
Frontend Event → API Request → Service Logic → External System
                                      ↓
Frontend Update ← API Response ← Service Response
```

## Caching Strategy

### Catalog Cache

- **Location**: Backend memory
- **TTL**: 1 hour (configurable)
- **Invalidation**: Manual refresh or TTL expiry
- **Purpose**: Reduce external HTTP requests

### Secret Cache

- **Location**: Backend memory (per session)
- **TTL**: Session lifetime
- **Invalidation**: Session end
- **Purpose**: Reduce Bitwarden API calls

### Frontend Cache (SWR)

- **Location**: Browser memory
- **TTL**: Configurable per endpoint
- **Revalidation**: On focus, on reconnect
- **Purpose**: Improve UI responsiveness

## Deployment Architecture

### Development

```
┌─────────────────────────────────────┐
│      Docker Compose                  │
│  ┌──────────┐  ┌──────────┐        │
│  │ Frontend │  │ Backend  │        │
│  │  :3000   │  │  :8000   │        │
│  └──────────┘  └──────────┘        │
└─────────────────────────────────────┘
         │              │
         └──────┬───────┘
                │
         Host Docker Engine
```

### Production

```
┌─────────────────────────────────────────────┐
│              Nginx (Reverse Proxy)           │
│         :80 (HTTP) → :443 (HTTPS)           │
└─────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌──────────────┐    ┌──────────────┐
│   Frontend   │    │   Backend    │
│   Container  │    │   Container  │
│    :3000     │    │    :8000     │
└──────────────┘    └──────────────┘
                           │
                           ▼
                  ┌──────────────┐
                  │Docker Engine │
                  └──────────────┘
```

## Scalability Considerations

### Current Limitations

- Single-server deployment
- In-memory session storage
- No horizontal scaling

### Future Improvements

1. **Session Storage**: Move to Redis for distributed sessions
2. **Load Balancing**: Support multiple backend instances
3. **Database**: Add persistent storage for configurations
4. **Message Queue**: Add queue for long-running operations
5. **Caching Layer**: Distributed cache (Redis/Memcached)

## Performance Optimization

### Frontend

1. **Code Splitting**: Next.js automatic code splitting
2. **Image Optimization**: Next.js Image component
3. **Lazy Loading**: Dynamic imports for heavy components
4. **Caching**: SWR for data fetching and caching

### Backend

1. **Async Operations**: FastAPI async endpoints
2. **Connection Pooling**: Docker SDK connection reuse
3. **Caching**: In-memory caching for frequently accessed data
4. **Streaming**: WebSocket for log streaming

## Monitoring and Observability

### Logging

- **Frontend**: Browser console (development)
- **Backend**: Structured logging with levels
- **Containers**: Docker logs accessible via UI

### Health Checks

- **Frontend**: HTTP endpoint check
- **Backend**: `/health` endpoint
- **Containers**: Docker health checks

### Metrics (Future)

- Request latency
- Error rates
- Container resource usage
- Cache hit rates

## Error Handling

### Frontend

```
Try/Catch → Error Boundary → Toast Notification
                ↓
         Log to Console (dev)
```

### Backend

```
Exception → Exception Handler → HTTP Error Response
                ↓
         Log with Context
```

## Testing Strategy

### Unit Tests

- **Frontend**: Jest + React Testing Library
- **Backend**: pytest

### Integration Tests

- **Backend**: pytest with Docker test containers
- **Frontend**: Component integration tests

### E2E Tests

- **Tool**: Playwright
- **Coverage**: Critical user flows

## Technology Decisions

### Why Next.js?

- Server-side rendering for better SEO
- App Router for modern routing
- Built-in optimization
- Great developer experience

### Why FastAPI?

- High performance
- Automatic API documentation
- Type safety with Pydantic
- Async support

### Why Bitwarden?

- Industry-standard security
- CLI available for automation
- Self-hosting option
- Free tier available

### Why Docker?

- Isolation for MCP servers
- Easy deployment
- Resource management
- Wide adoption

## Future Architecture

### Planned Improvements

1. **Microservices**: Split backend into smaller services
2. **Event-Driven**: Add message queue for async operations
3. **Multi-Tenancy**: Support multiple users/organizations
4. **Kubernetes**: Support K8s in addition to Docker
5. **GraphQL**: Consider GraphQL for more flexible API

## References

- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [Bitwarden CLI](https://bitwarden.com/help/cli/)
- [MCP Protocol](https://modelcontextprotocol.io/)
