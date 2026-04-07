# DinD Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate from Docker-out-of-Docker (DooD) to Docker-in-Docker (DinD) with TLS to improve security and decouple the backend from host Docker socket.

**Architecture:** We will run a `dind` container alongside the `workspace` and `backend` containers. The backend and workspace will communicate with `dind` via TLS over TCP port 2376. We will inject `AuthService` into `ContainerService` to enforce session validation in the service layer, keeping the FastAPI routers thin.

**Tech Stack:** Docker, docker:dind, FastAPI, Python.

---

### Task 1: Update Devcontainer to use DinD

**Files:**
- Modify: `.devcontainer/docker-compose.devcontainer.yml`
- Modify: `.devcontainer/devcontainer.json`
- Delete: `backend/tests/test_devcontainer_docker_socket.py`
- Delete: `.devcontainer/init-docker-socket.sh`

- [ ] **Step 1: Remove socket tests**

Run: `rm -f backend/tests/test_devcontainer_docker_socket.py .devcontainer/init-docker-socket.sh`
Expected: Files deleted.

- [ ] **Step 2: Update docker-compose.devcontainer.yml**

```yaml
# Update `.devcontainer/docker-compose.devcontainer.yml` to remove socket mounts and add dind
version: "3.8"

services:
  workspace:
    build:
      context: .
      dockerfile: .devcontainer/Dockerfile.workspace
    volumes:
      - ..:/workspace:cached
      - dind-certs:/certs/client:ro
    environment:
      - DOCKER_HOST=tcp://dind:2376
      - DOCKER_TLS_VERIFY=1
      - DOCKER_CERT_PATH=/certs/client
    command: sleep infinity
    depends_on:
      - backend
      - frontend
      - dind

  dind:
    image: docker:dind
    privileged: true
    environment:
      - DOCKER_TLS_CERTDIR=/certs
    volumes:
      - dind-certs:/certs/client
      - dind-data:/var/lib/docker

  backend:
    volumes:
      - ../backend:/app:cached
    environment:
      - DOCKER_HOST=tcp://dind:2376
      - DOCKER_TLS_VERIFY=1
      - DOCKER_CERT_PATH=/certs/client
    depends_on:
      - dind

  frontend:
    volumes:
      - ../frontend:/app:cached
    shm_size: 1gb

volumes:
  dind-certs:
  dind-data:
```

- [ ] **Step 3: Update devcontainer.json**

```json
// Add to `.devcontainer/devcontainer.json` at root level (or merge with existing remoteEnv):
  "remoteEnv": {
    "DOCKER_HOST": "tcp://dind:2376",
    "DOCKER_TLS_VERIFY": "1",
    "DOCKER_CERT_PATH": "/certs/client"
  }
```

- [ ] **Step 4: Commit**

```bash
git add .devcontainer/docker-compose.devcontainer.yml .devcontainer/devcontainer.json
git rm -f backend/tests/test_devcontainer_docker_socket.py .devcontainer/init-docker-socket.sh || true
git commit -m "chore: migrate devcontainer to dind architecture"
```

---

### Task 2: Refactor ContainerService (Dependency Injection & Auth)

**Files:**
- Modify: `backend/app/services/containers.py`

- [ ] **Step 1: Inject AuthService into ContainerService**

```python
# In `backend/app/services/containers.py`
from fastapi import HTTPException, status
from .auth import AuthService
from typing import AsyncIterator, List, Optional, Any

# Update __init__ to accept auth_service
    def __init__(
        self,
        provider: ContainerProvider,
        secret_manager: SecretManager,
        auth_service: AuthService,
        state_store: Optional[StateStore] = None
    ):
        self.provider = provider
        self.secret_manager = secret_manager
        self.auth_service = auth_service
        self._state_store = state_store or StateStore()

# Add helper inside class ContainerService:
    async def _validate_session_and_get(self, session_id: str) -> Any:
        is_valid = await self.auth_service.validate_session(session_id)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        return await self.auth_service.get_session(session_id)
```

- [ ] **Step 2: Add authenticated methods to ContainerService**

```python
# In `backend/app/services/containers.py`
    async def list_containers_with_auth(self, session_id: str, all_containers: bool = True) -> List[ContainerInfo]:
        await self._validate_session_and_get(session_id)
        return await self.list_containers(all_containers)

    async def create_container_with_auth(self, config: ContainerConfig, session_id: str) -> str:
        session = await self._validate_session_and_get(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session state")
        
        try:
            return await self.create_container(config, session_id, session.bw_session_key)
        except ContainerAlreadyExistsError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
        except ContainerUnavailableError:
            raise
        except ContainerError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    async def start_container_with_auth(self, container_id: str, session_id: str) -> bool:
        await self._validate_session_and_get(session_id)
        return await self.start_container(container_id)

    async def stop_container_with_auth(self, container_id: str, session_id: str, timeout: int = 10) -> bool:
        await self._validate_session_and_get(session_id)
        return await self.stop_container(container_id, timeout)

    async def restart_container_with_auth(self, container_id: str, session_id: str, timeout: int = 10) -> bool:
        await self._validate_session_and_get(session_id)
        return await self.restart_container(container_id, timeout)

    async def delete_container_with_auth(self, container_id: str, session_id: str, force: bool = False) -> bool:
        await self._validate_session_and_get(session_id)
        return await self.delete_container(container_id, force)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/containers.py
git commit -m "refactor: add auth checks to container service"
```

---

### Task 3: Thin Controller Refactoring for API

**Files:**
- Modify: `backend/app/api/containers.py`

- [ ] **Step 1: Update DI and Router implementation**

```python
# In `backend/app/api/containers.py`
# Update get_container_service dependency
def get_container_service(
    secret_manager: Annotated[SecretManager, Depends(get_secret_manager)],
    container_provider: Annotated[ContainerProvider, Depends(get_container_provider)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> ContainerService:
    global _container_service, _state_store
    if _container_service is None:
        _state_store = StateStore()
        _state_store.init_schema()
        _container_service = ContainerService(
            container_provider, 
            secret_manager, 
            auth_service,
            state_store=_state_store
        )
    return _container_service

# Remove `_create_container_internal` entirely from the file.

# Simplify `list_containers`
@router.get("", response_model=ContainerListResponse)
async def list_containers(
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
    all: bool = True,
):
    try:
        containers = await container_service.list_containers_with_auth(session_id, all)
        return ContainerListResponse(containers=containers)
    except HTTPException:
        raise
    except ContainerUnavailableError as e:
        _log_docker_unavailable(e)
        return ContainerListResponse(containers=[], warning="Docker daemon is unavailable.")
    except Exception as e:
        logger.error(f"Failed to list containers: {e}")
        return ContainerListResponse(containers=[], warning="Failed to fetch containers.")

# Simplify `create_container`
@router.post("", response_model=ContainerCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_container(
    config: ContainerConfig,
    session_id: Annotated[str, Depends(get_session_id)],
    container_service: Annotated[ContainerService, Depends(get_container_service)],
):
    try:
        container_id = await container_service.create_container_with_auth(config, session_id)
        return ContainerCreateResponse(container_id=container_id, name=config.name, status="running")
    except HTTPException:
        raise
    except ContainerUnavailableError as e:
        raise _docker_unavailable(e) from e
    except Exception as e:
        logger.exception("Unexpected error creating container")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating container") from e

# Apply similar simplifications to install_container, start_container, stop_container, restart_container, and delete_container
# (replace `auth_service.validate_session` and use `container_service.*_with_auth`)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/containers.py
git commit -m "refactor: apply thin controller pattern to containers API"
```
