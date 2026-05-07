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
from app.database import init_database, SessionLocal

# Silence noisy SQLAlchemy SQL logging
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


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
    logger.info("🚀 Starting SPBE RAG System...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize database (ORM create_all)
    try:
        init_database()
        logger.success("✓ Database initialized")
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")

    # Jalankan schema migrations (idempotent — aman dipanggil setiap startup)
    try:
        import importlib.util
        from pathlib import Path as _Path
        _mig_path = _Path(__file__).parent.parent / "scripts" / "migrations" / "001_add_doc_metadata_columns.py"
        _spec = importlib.util.spec_from_file_location("migration_001", _mig_path)
        _migration = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_migration)
        from app.database import engine as _engine
        _db_path = str(_engine.url).replace("sqlite:///", "").replace("sqlite://", "")
        _migration.run(_db_path)
    except Exception as e:
        logger.warning(f"⚠ Schema migration warning: {e}")

    # Pastikan default user (id=1) ada — dibutuhkan oleh chat session system
    try:
        from app.models.db_models import User
        db = SessionLocal()
        try:
            default_user = db.query(User).filter(User.id == 1).first()
            if not default_user:
                default_user = User(id=1, name="Default User", email=None)
                db.add(default_user)
                db.commit()
                logger.success("✓ Default user created (id=1)")
            else:
                logger.info("✓ Default user exists (id=1)")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"⚠ Could not ensure default user: {e}")

    # Pre-load embedding model & Qdrant connection in background thread
    # This prevents the first chat request from blocking the async event loop
    try:
        from app.core.rag.langchain_engine import langchain_engine
        logger.info("⏳ Pre-loading embedding model (this may take 30-60s)...")
        await langchain_engine.preload()
        logger.success("✓ RAG engine ready")
    except Exception as e:
        logger.warning(f"⚠ RAG engine preload failed (will retry on first request): {e}")

    logger.success("✓ Application startup complete")

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
