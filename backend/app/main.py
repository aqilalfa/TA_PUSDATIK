"""
Main FastAPI application for SPBE RAG System
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import sys

from app.config import settings
from app.api.routes import health, users, sessions, chat, models
from app.api.documents import router as doc_mgmt_router
from app.api.rag_documents import router as rag_doc_router
from app.api.auth_routes import router as auth_router
from app.database import init_database

# Silence noisy SQLAlchemy SQL logging
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _handle_startup_failure(component: str, error: Exception, environment: str) -> None:
    """Fail fast for critical startup dependencies in production."""
    message = f"{component} failed: {error}"
    if environment.strip().lower() == "production":
        logger.error(f"[FAIL] {message}")
        raise error
    logger.warning(f"[WARN] {message}")


# Setup logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL,
)
logger.add(
    f"{settings.LOG_DIR}/app_{{time}}.log",
    rotation="100 MB",
    retention="30 days",
    level="DEBUG",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("[START] Starting SPBE RAG System...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize database (ORM create_all)
    try:
        init_database()
        logger.success("[OK] Database initialized")
    except Exception as e:
        _handle_startup_failure("Database initialization", e, settings.ENVIRONMENT)

    # Jalankan schema migrations (idempotent — aman dipanggil setiap startup)
    try:
        import importlib.util
        from pathlib import Path as _Path
        from app.database import engine as _engine
        _db_path = str(_engine.url).replace("sqlite:///", "").replace("sqlite://", "")

        _migrations_dir = _Path(__file__).parent.parent / "scripts" / "migrations"
        for _mig_path in sorted(_migrations_dir.glob("[0-9][0-9][0-9]_*.py")):
            _module_name = f"migration_{_mig_path.stem}"
            _spec = importlib.util.spec_from_file_location(_module_name, _mig_path)
            if _spec is None or _spec.loader is None:
                raise RuntimeError(f"Unable to load migration module: {_mig_path}")
            _migration = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_migration)
            if hasattr(_migration, "run"):
                _migration.run(_db_path)
    except Exception as e:
        _handle_startup_failure("Schema migration", e, settings.ENVIRONMENT)

    # User provisioning is intentionally explicit. Run backend/seed_users.py only
    # in controlled development environments; application startup never creates accounts.

    # Pre-load embedding model & Qdrant connection in background thread
    # This prevents the first chat request from blocking the async event loop
    try:
        from app.core.rag.langchain_engine import langchain_engine
        logger.info("[WAIT] Pre-loading embedding model (this may take 30-60s)...")
        await langchain_engine.preload()
        logger.success("[OK] RAG engine ready")
    except Exception as e:
        logger.warning(f"[WARN] RAG engine preload failed (will retry on first request): {e}")

    logger.success("[OK] Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down SPBE RAG System...")


# Create FastAPI app
app = FastAPI(
    title="SPBE RAG System API",
    description="API for SPBE Legal Document RAG System with Agentic AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(doc_mgmt_router)  # prefix sudah ada di router: /api/documents
app.include_router(rag_doc_router)   # prefix: /api/rag/documents (citation popup & PDF serve)
app.include_router(models.router, prefix="/api/models", tags=["Models"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "SPBE RAG System API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
