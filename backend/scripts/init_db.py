#!/usr/bin/env python3
"""
Initialize database for SPBE RAG System
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_database, engine
from app.models.db_models import (
    User,
    Session,
    Conversation,
    Document,
    Chunk,
    EvaluationResult,
)
from loguru import logger


def main():
    logger.info("🔧 Initializing SPBE RAG database...")

    try:
        # Create all tables
        init_database()

        # Verify tables were created
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        logger.success(f"✓ Database initialized successfully!")
        logger.info(f"  Created tables: {', '.join(tables)}")

        # Create default user if not exists
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            existing_user = db.query(User).first()
            if not existing_user:
                default_user = User(name="Default User", email="user@bssn.go.id")
                db.add(default_user)
                db.commit()
                logger.info(f"✓ Created default user (ID: {default_user.id})")
        finally:
            db.close()

        logger.success("🎉 Database initialization complete!")

    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
