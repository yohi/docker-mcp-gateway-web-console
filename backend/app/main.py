import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, catalog, config, containers, inspector
from app.config import settings
from app.services.auth import AuthError
from app.services.catalog import CatalogError
from app.services.config import ConfigError
from app.services.containers import ContainerError
from app.services.inspector import InspectorError
from app.services.secrets import SecretError

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Docker MCP Gateway Console API")
    yield
    logger.info("Shutting down Docker MCP Gateway Console API")


app = FastAPI(
    title="Docker MCP Gateway Console API",
    description="Backend API for managing Docker-based MCP servers",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router)
app.include_router(config.router)
app.include_router(containers.router, prefix="/api")
app.include_router(inspector.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Docker MCP Gateway Console API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Global exception handlers


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    """
    Handle authentication errors.
    
    **Validates: Requirements 10.1, 10.2**
    """
    logger.warning(f"Authentication error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error_code": "AUTH_ERROR",
            "message": str(exc),
            "detail": "Authentication failed. Please check your credentials and try again.",
        },
    )


@app.exception_handler(CatalogError)
async def catalog_error_handler(request: Request, exc: CatalogError):
    """
    Handle catalog-related errors.
    
    **Validates: Requirements 10.1, 10.2**
    """
    logger.error(f"Catalog error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error_code": "CATALOG_ERROR",
            "message": str(exc),
            "detail": "Failed to fetch catalog data. The catalog service may be temporarily unavailable.",
        },
    )


@app.exception_handler(ConfigError)
async def config_error_handler(request: Request, exc: ConfigError):
    """
    Handle configuration errors.
    
    **Validates: Requirements 10.1, 10.2**
    """
    logger.error(f"Configuration error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "CONFIG_ERROR",
            "message": str(exc),
            "detail": "Configuration error. Please check your configuration and try again.",
        },
    )


@app.exception_handler(ContainerError)
async def container_error_handler(request: Request, exc: ContainerError):
    """
    Handle container operation errors.
    
    **Validates: Requirements 10.1, 10.2**
    """
    logger.error(f"Container error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "CONTAINER_ERROR",
            "message": str(exc),
            "detail": "Container operation failed. Please check the container status and Docker daemon connection.",
        },
    )


@app.exception_handler(InspectorError)
async def inspector_error_handler(request: Request, exc: InspectorError):
    """
    Handle MCP inspector errors.
    
    **Validates: Requirements 10.1, 10.2**
    """
    logger.error(f"Inspector error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "INSPECTOR_ERROR",
            "message": str(exc),
            "detail": "Failed to inspect MCP server. Please ensure the container is running and accessible.",
        },
    )


@app.exception_handler(SecretError)
async def secret_error_handler(request: Request, exc: SecretError):
    """
    Handle secret management errors.
    
    **Validates: Requirements 10.1, 10.2**
    """
    logger.error(f"Secret error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "SECRET_ERROR",
            "message": str(exc),
            "detail": "Failed to resolve secret reference. Please check your Bitwarden vault and reference notation.",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors.
    
    **Validates: Requirements 10.1, 10.2**
    """
    logger.warning(f"Validation error: {exc}")
    errors = exc.errors()
    error_messages = []
    
    for error in errors:
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "detail": "; ".join(error_messages),
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle all other unexpected exceptions.
    
    **Validates: Requirements 10.1, 10.5**
    
    Logs detailed error information while returning a user-friendly message.
    """
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": "The server encountered an unexpected error. Please try again later or contact support if the problem persists.",
        },
    )
