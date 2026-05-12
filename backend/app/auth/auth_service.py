"""Authentication service and provider factory."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.auth.ldap_provider import LDAPAuthProvider, LDAPUnavailableError
from app.auth.local_provider import LocalAuthProvider


def get_auth_provider():
    """Return the default auth provider for the current environment."""

    provider_name = settings.AUTH_PROVIDER.strip().lower()
    if provider_name == "ldap" and settings.LDAP_ENABLED:
        return LDAPAuthProvider()
    return LocalAuthProvider()


def authenticate_user(username: str, password: str, db: Session):
    """Authenticate a user using the configured provider strategy."""

    provider_name = settings.AUTH_PROVIDER.strip().lower()

    if provider_name == "local":
        return LocalAuthProvider().authenticate(username, password, db)

    if provider_name == "ldap":
        if not settings.LDAP_ENABLED:
            return None
        return LDAPAuthProvider().authenticate(username, password, db)

    if provider_name == "hybrid":
        if settings.LDAP_ENABLED:
            try:
                ldap_user = LDAPAuthProvider().authenticate(username, password, db)
                if ldap_user is not None:
                    return ldap_user
            except LDAPUnavailableError:
                if not settings.LDAP_FALLBACK_TO_LOCAL:
                    raise

        if settings.LDAP_FALLBACK_TO_LOCAL:
            return LocalAuthProvider().authenticate(username, password, db)

        return None

    return LocalAuthProvider().authenticate(username, password, db)
