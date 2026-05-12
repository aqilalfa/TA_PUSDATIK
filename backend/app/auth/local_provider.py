"""Local authentication provider backed by SQLite user records."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.local_authenticator import verify_password
from app.models.db_models import User


class LocalAuthProvider:
    """Authenticate against the local user table."""

    provider_name = "local"

    def authenticate(self, username: str, password: str, db: Session) -> User | None:
        user = db.query(User).filter(User.email == username).first()
        if not user or not user.hashed_password:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user
