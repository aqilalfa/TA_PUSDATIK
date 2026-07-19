import os

from app.auth.local_authenticator import get_password_hash
from app.config import settings
from app.database import SessionLocal
from app.models.db_models import User


def seed_development_users() -> None:
    if settings.ENVIRONMENT.strip().lower() == "production":
        raise RuntimeError("Refusing to seed development users in production")

    password = os.environ.get("SEED_USER_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("SEED_USER_PASSWORD must be set explicitly")

    password_hash = get_password_hash(password)
    users = (
        {
            "name": "Admin PUSDATIK",
            "email": "admin@bssn.go.id",
            "roles": '["admin_pusdatik"]',
            "department": "PUSDATIK",
        },
        {
            "name": "Evaluator SPBE",
            "email": "evaluator@bssn.go.id",
            "roles": '["staff"]',
            "department": "DEPUTI_EVALUASI",
        },
    )

    db = SessionLocal()
    try:
        for values in users:
            user = db.query(User).filter(User.email == values["email"]).first()
            if user is None:
                user = User(**values, hashed_password=password_hash)
                db.add(user)
            else:
                user.name = values["name"]
                user.hashed_password = password_hash
                user.roles = values["roles"]
                user.department = values["department"]
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_development_users()
