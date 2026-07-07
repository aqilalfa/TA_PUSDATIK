#!/usr/bin/env python3
"""Migrate legacy role names to the unified `staff` role.

Replaces evaluator_spbe, staf_pusdatik, and manager_evaluasi in local user
roles, document security metadata, BM25 chunk metadata, and Qdrant payloads.
"""

from __future__ import annotations

import json
import pickle
import sqlite3
import sys
import urllib.request
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "data" / "spbe_rag.db"
BM25_PATH = BACKEND_DIR / "data" / "bm25_index.pkl"
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "document_chunks"
LEGACY_ROLES = {"evaluator_spbe", "staf_pusdatik", "manager_evaluasi"}
ROLE_ORDER = {"admin_pusdatik": 0, "staff": 1}


def normalize_roles(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [value]
    elif isinstance(value, list):
        parsed = value
    else:
        parsed = list(value) if hasattr(value, "__iter__") else []

    normalized: set[str] = set()
    for role in parsed:
        role_name = str(role).strip()
        if not role_name:
            continue
        normalized.add("staff" if role_name in LEGACY_ROLES else role_name)

    return sorted(normalized, key=lambda item: (ROLE_ORDER.get(item, 99), item))


def migrate_sqlite(db_path: Path = DB_PATH) -> dict[str, int]:
    result = {"users_scanned": 0, "users_updated": 0, "documents_scanned": 0, "documents_updated": 0}
    connection = sqlite3.connect(str(db_path))
    try:
        for user_id, roles_raw in connection.execute("SELECT id, roles FROM users").fetchall():
            result["users_scanned"] += 1
            roles = normalize_roles(roles_raw)
            updated_raw = json.dumps(roles)
            if updated_raw != (roles_raw or "[]"):
                connection.execute("UPDATE users SET roles = ? WHERE id = ?", (updated_raw, user_id))
                result["users_updated"] += 1

        for doc_id, metadata_raw in connection.execute("SELECT id, doc_metadata FROM documents").fetchall():
            result["documents_scanned"] += 1
            try:
                metadata = json.loads(metadata_raw or "{}")
            except json.JSONDecodeError:
                continue
            if not isinstance(metadata, dict):
                continue
            security = metadata.get("security")
            if not isinstance(security, dict):
                continue
            old_roles = security.get("allowed_roles")
            new_roles = normalize_roles(old_roles)
            if new_roles != old_roles:
                security["allowed_roles"] = new_roles
                metadata["security"] = security
                connection.execute(
                    "UPDATE documents SET doc_metadata = ? WHERE id = ?",
                    (json.dumps(metadata, ensure_ascii=False), doc_id),
                )
                result["documents_updated"] += 1
        connection.commit()
    finally:
        connection.close()
    return result


def migrate_bm25(bm25_path: Path = BM25_PATH) -> dict[str, int]:
    result = {"chunks_scanned": 0, "chunks_updated": 0}
    if not bm25_path.exists():
        return result
    with bm25_path.open("rb") as handle:
        payload = pickle.load(handle)

    documents = payload.get("documents", []) if isinstance(payload, dict) else []
    for document in documents:
        if not isinstance(document, dict):
            continue
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            continue
        result["chunks_scanned"] += 1
        old_roles = metadata.get("allowed_roles")
        new_roles = normalize_roles(old_roles)
        if new_roles != old_roles:
            metadata["allowed_roles"] = new_roles
            result["chunks_updated"] += 1

    if result["chunks_updated"]:
        with bm25_path.open("wb") as handle:
            pickle.dump(payload, handle)
    return result


def _qdrant_scroll(offset: Any | None = None, limit: int = 100) -> dict[str, Any]:
    body: dict[str, Any] = {"limit": limit, "with_payload": True, "with_vector": False}
    if offset is not None:
        body["offset"] = offset
    request = urllib.request.Request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _qdrant_set_payload(point_id: Any, allowed_roles: list[str]) -> None:
    body = {"points": [point_id], "payload": {"allowed_roles": allowed_roles}}
    request = urllib.request.Request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/payload",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def migrate_qdrant() -> dict[str, int | str]:
    result: dict[str, int | str] = {"points_scanned": 0, "points_updated": 0}
    offset = None
    try:
        while True:
            payload = _qdrant_scroll(offset=offset)
            scroll_result = payload.get("result", {}) if isinstance(payload, dict) else {}
            points = scroll_result.get("points", [])
            for point in points:
                if not isinstance(point, dict):
                    continue
                result["points_scanned"] = int(result["points_scanned"]) + 1
                point_payload = point.get("payload", {})
                if not isinstance(point_payload, dict):
                    continue
                old_roles = point_payload.get("allowed_roles")
                new_roles = normalize_roles(old_roles)
                if new_roles != old_roles:
                    _qdrant_set_payload(point.get("id"), new_roles)
                    result["points_updated"] = int(result["points_updated"]) + 1
            offset = scroll_result.get("next_page_offset")
            if not offset:
                break
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main() -> None:
    result = {
        "sqlite": migrate_sqlite(),
        "bm25": migrate_bm25(),
        "qdrant": migrate_qdrant(),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
