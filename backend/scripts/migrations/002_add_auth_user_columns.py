"""
Migration 002: Add authentication provider columns to users.

Existing SQLite databases created before LDAP/local auth support do not have
the users.auth_provider and users.external_id columns. SQLAlchemy create_all()
does not alter existing tables, so login queries fail without this migration.
"""

import sqlite3
from pathlib import Path

from loguru import logger


def run(db_path: str) -> bool:
    """Add missing user auth columns idempotently."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        columns_to_add = [
            ("auth_provider", "TEXT DEFAULT 'local'"),
            ("external_id", "TEXT"),
        ]

        added_cols = []
        for col_name, col_def in columns_to_add:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                added_cols.append(col_name)

        cursor.execute(
            "UPDATE users SET auth_provider = 'local' "
            "WHERE auth_provider IS NULL OR auth_provider = ''"
        )

        if added_cols:
            logger.success(f"Migration 002: Added columns to users: {added_cols}")
        else:
            logger.debug("Migration 002: users table sudah up-to-date")

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Migration 002 failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    db_path = Path(__file__).parent.parent.parent / "data" / "spbe_rag.db"
    if not db_path.exists():
        print(f"Database tidak ditemukan: {db_path}")
        sys.exit(1)

    print(f"Running migration on: {db_path}")
    success = run(str(db_path))
    sys.exit(0 if success else 1)
