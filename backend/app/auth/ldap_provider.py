"""LDAP authentication provider with shadow-user provisioning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.auth.role_mapper import map_directory_groups_to_roles, serialize_roles
from app.models.db_models import User


class LDAPUnavailableError(RuntimeError):
    """Raised when LDAP cannot be reached or initialized."""


class DirectoryClient(Protocol):
    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        ...


@dataclass
class LDAPDirectoryClient:
    """Optional real LDAP client. Lazily imports ldap3 only when used."""

    server_url: str = settings.LDAP_SERVER_URL
    base_dn: str = settings.LDAP_BASE_DN
    domain: str = settings.LDAP_DOMAIN
    timeout: int = settings.LDAP_TIMEOUT
    retry_count: int = settings.LDAP_RETRY_COUNT

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        try:
            from ldap3 import ALL, Connection, Server
        except ImportError as exc:
            raise LDAPUnavailableError("ldap3 is not installed") from exc

        user_dn = f"{username}@{self.domain}"

        for attempt in range(self.retry_count):
            try:
                server = Server(self.server_url, get_info=ALL, connect_timeout=self.timeout)
                connection = Connection(
                    server,
                    user=user_dn,
                    password=password,
                    raise_exceptions=True,
                    auto_bind=True,
                )
                try:
                    connection.search(
                        search_base=self.base_dn,
                        search_filter=f"(sAMAccountName={username})",
                        attributes=["memberOf", "department", "displayName", "mail", "employeeID"],
                    )
                    if not connection.entries:
                        return None

                    entry = connection.entries[0]
                    member_of = entry.memberOf.values if entry.memberOf else []
                    groups = [str(group).split(",")[0].replace("CN=", "") for group in member_of]

                    return {
                        "username": username,
                        "display_name": str(entry.displayName) if entry.displayName else username,
                        "email": str(entry.mail) if entry.mail else username,
                        "department": str(entry.department) if entry.department else "",
                        "employee_id": str(entry.employeeID) if entry.employeeID else None,
                        "groups": groups,
                    }
                finally:
                    connection.unbind()
            except Exception as exc:
                logger.warning(f"LDAP attempt {attempt + 1}/{self.retry_count} failed: {exc}")
                if attempt == self.retry_count - 1:
                    raise LDAPUnavailableError(str(exc)) from exc

        return None


class LDAPAuthProvider:
    """Authenticate against LDAP and provision/update a local shadow user."""

    provider_name = "ldap"

    def __init__(self, directory_client: DirectoryClient | None = None):
        self.directory_client = directory_client or LDAPDirectoryClient()

    def authenticate(self, username: str, password: str, db: Session) -> User | None:
        try:
            directory_user = self.directory_client.authenticate(username, password)
        except LDAPUnavailableError:
            raise

        if not directory_user:
            return None

        roles = map_directory_groups_to_roles(directory_user.get("groups", []))
        return self._upsert_shadow_user(db, directory_user, roles)

    def _upsert_shadow_user(self, db: Session, directory_user: dict[str, Any], roles: list[str]) -> User:
        email = directory_user.get("email") or directory_user.get("username")
        user = db.query(User).filter(User.email == email).first()

        if user is None:
            user = User(email=email, name=directory_user.get("display_name") or email)

        user.name = directory_user.get("display_name") or user.name or email
        user.email = email
        user.department = directory_user.get("department") or user.department
        user.roles = serialize_roles(roles)
        user.auth_provider = self.provider_name
        user.external_id = directory_user.get("employee_id") or user.external_id

        db.add(user)
        db.commit()
        db.refresh(user)
        return user
