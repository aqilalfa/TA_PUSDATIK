#!/usr/bin/env python3
"""
SPBE RAG smoke check.

One-command runtime validation for local development.
Checks:
1) Backend /api/health
2) Qdrant collection availability
3) Qdrant point count
4) SQLite chunk count
5) Alignment between Qdrant points and SQLite chunks
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error, request

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import SessionLocal, engine
from app.models.db_models import Chunk
from qdrant_client import QdrantClient


@dataclass
class CheckResult:
    """Result object for a single smoke-check item."""

    name: str
    ok: bool
    details: Dict[str, Any]
    error: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        """Serialize result to JSON-friendly dict."""
        payload: Dict[str, Any] = {
            "name": self.name,
            "ok": self.ok,
            "details": self.details,
        }
        if self.error:
            payload["error"] = self.error
        return payload


def _summarize_services(services: Any) -> str:
    """Create a compact, stable string for service health details."""
    if not isinstance(services, dict):
        return str(services)
    parts = [f"{key}={services[key]}" for key in sorted(services.keys())]
    return ", ".join(parts)


def check_backend_health(backend_url: str, timeout: int) -> CheckResult:
    """Check backend health endpoint and service status."""
    endpoint = f"{backend_url.rstrip('/')}/api/health"
    try:
        with request.urlopen(endpoint, timeout=timeout) as response:
            status_code = response.getcode()
            payload = json.loads(response.read().decode("utf-8"))

        status = str(payload.get("status", "unknown"))
        services = payload.get("services", {})
        services_ok = isinstance(services, dict) and all(
            "healthy" in str(value).lower() or "present" in str(value).lower()
            for value in services.values()
        )

        ok = status_code == 200 and status == "healthy" and services_ok
        return CheckResult(
            name="Backend health endpoint",
            ok=ok,
            details={
                "endpoint": endpoint,
                "http_status": status_code,
                "status": status,
                "services": _summarize_services(services),
            },
            error=None if ok else "Backend health response is not fully healthy.",
        )
    except error.URLError as exc:
        return CheckResult(
            name="Backend health endpoint",
            ok=False,
            details={"endpoint": endpoint},
            error=str(exc),
        )
    except Exception as exc:
        return CheckResult(
            name="Backend health endpoint",
            ok=False,
            details={"endpoint": endpoint},
            error=str(exc),
        )


def check_qdrant_collection(
    qdrant_url: str, collection: str, timeout: int
) -> CheckResult:
    """Check Qdrant reachability and collection point count."""
    try:
        client = QdrantClient(
            url=qdrant_url,
            timeout=timeout,
            check_compatibility=False,
        )
        collections = client.get_collections()
        collection_names = {item.name for item in collections.collections}

        exists = collection in collection_names
        points_count: Any = "n/a"
        if exists:
            info = client.get_collection(collection)
            points_count = int(info.points_count or 0)

        return CheckResult(
            name="Qdrant collection",
            ok=exists,
            details={
                "url": qdrant_url,
                "collection": collection,
                "exists": exists,
                "points_count": points_count,
            },
            error=None if exists else f"Collection '{collection}' not found.",
        )
    except Exception as exc:
        return CheckResult(
            name="Qdrant collection",
            ok=False,
            details={
                "url": qdrant_url,
                "collection": collection,
            },
            error=str(exc),
        )


def check_sqlite_chunk_count() -> CheckResult:
    """Read chunk count from SQLite."""
    db = SessionLocal()
    try:
        chunk_count = db.query(Chunk).count()
        return CheckResult(
            name="SQLite chunk count",
            ok=True,
            details={"chunks": int(chunk_count)},
        )
    except Exception as exc:
        return CheckResult(
            name="SQLite chunk count",
            ok=False,
            details={},
            error=str(exc),
        )
    finally:
        db.close()


def check_count_alignment(
    sqlite_result: CheckResult,
    qdrant_result: CheckResult,
    allow_drift: bool,
) -> CheckResult:
    """Compare SQLite chunk count with Qdrant points."""
    sqlite_chunks = sqlite_result.details.get("chunks")
    qdrant_points = qdrant_result.details.get("points_count")

    if not isinstance(sqlite_chunks, int) or not isinstance(qdrant_points, int):
        return CheckResult(
            name="Qdrant and SQLite count alignment",
            ok=False,
            details={
                "sqlite_chunks": sqlite_chunks,
                "qdrant_points": qdrant_points,
                "allow_drift": allow_drift,
            },
            error="Cannot compare counts because one source is unavailable.",
        )

    delta = qdrant_points - sqlite_chunks
    counts_match = delta == 0
    ok = counts_match or allow_drift

    return CheckResult(
        name="Qdrant and SQLite count alignment",
        ok=ok,
        details={
            "sqlite_chunks": sqlite_chunks,
            "qdrant_points": qdrant_points,
            "delta": delta,
            "allow_drift": allow_drift,
        },
        error=None
        if ok
        else "Count mismatch detected. Run sync_vectors.py --force if needed.",
    )


def print_human_readable(results: list[CheckResult]) -> None:
    """Print structured smoke-check output for terminal use."""
    print("=" * 72)
    print("SPBE RAG - SMOKE CHECK")
    print("=" * 72)

    for item in results:
        label = "PASS" if item.ok else "FAIL"
        print(f"[{label}] {item.name}")
        for key in sorted(item.details.keys()):
            print(f"  - {key}: {item.details[key]}")
        if item.error:
            print(f"  - error: {item.error}")
        print("")

    passed = sum(1 for item in results if item.ok)
    failed = len(results) - passed
    overall_ok = failed == 0

    print("-" * 72)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print(f"RESULT: {'PASS' if overall_ok else 'FAIL'}")


def parse_args() -> argparse.Namespace:
    """Parse CLI args for smoke check."""
    parser = argparse.ArgumentParser(
        description="One-command smoke check for backend health and vector alignment."
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--qdrant-url",
        default=settings.QDRANT_URL,
        help=f"Qdrant URL (default: {settings.QDRANT_URL})",
    )
    parser.add_argument(
        "--collection",
        default=settings.QDRANT_COLLECTION,
        help=f"Qdrant collection name (default: {settings.QDRANT_COLLECTION})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout in seconds for network checks (default: 10)",
    )
    parser.add_argument(
        "--allow-drift",
        action="store_true",
        help="Do not fail when SQLite chunks and Qdrant points are different.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output instead of human-readable format.",
    )
    return parser.parse_args()


def main() -> int:
    """Run smoke-check flow and return process exit code."""
    args = parse_args()

    # Keep smoke-check output readable even when global DEBUG is enabled.
    engine.echo = False

    backend_result = check_backend_health(args.backend_url, args.timeout)
    qdrant_result = check_qdrant_collection(args.qdrant_url, args.collection, args.timeout)
    sqlite_result = check_sqlite_chunk_count()
    alignment_result = check_count_alignment(
        sqlite_result=sqlite_result,
        qdrant_result=qdrant_result,
        allow_drift=args.allow_drift,
    )

    results = [
        backend_result,
        qdrant_result,
        sqlite_result,
        alignment_result,
    ]

    passed = sum(1 for item in results if item.ok)
    failed = len(results) - passed
    overall_ok = failed == 0

    if args.json:
        payload = {
            "overall_ok": overall_ok,
            "summary": {
                "passed": passed,
                "failed": failed,
            },
            "checks": [item.to_json() for item in results],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print_human_readable(results)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())