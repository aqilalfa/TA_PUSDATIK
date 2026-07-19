import inspect
from pathlib import Path

import pytest

from app import main


def test_startup_source_does_not_seed_hardcoded_users_or_passwords():
    source = inspect.getsource(main.lifespan)

    assert "password123" not in source
    assert "admin@bssn.go.id" not in source
    assert "evaluator@bssn.go.id" not in source
    assert "Default User" not in source


def test_production_startup_failure_is_reraised():
    error = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        main._handle_startup_failure("Database initialization", error, "production")


def test_non_production_startup_failure_is_tolerated():
    main._handle_startup_failure(
        "Database initialization",
        RuntimeError("database unavailable"),
        "development",
    )


def test_legacy_document_router_is_removed_and_secure_router_is_registered():
    backend_root = Path(__file__).resolve().parents[1]
    assert not (backend_root / "app" / "api" / "routes" / "documents.py").exists()

    paths = {route.path for route in main.app.routes}
    assert "/api/documents/upload" in paths
    assert "/api/documents/{doc_id}" in paths


def test_seed_script_has_no_static_password_and_requires_explicit_environment_secret():
    backend_root = Path(__file__).resolve().parents[1]
    source = (backend_root / "seed_users.py").read_text(encoding="utf-8")

    assert "$2b$" not in source
    assert "password123" not in source
    assert "SEED_USER_PASSWORD" in source
    assert "Refusing to seed development users in production" in source
