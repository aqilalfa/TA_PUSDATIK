"""
Canary regression check. Sends 4 canary queries to the running RAG backend and
compares against a baseline JSON. Exits non-zero on regression.

Usage:
    python backend/scripts/eval_regression_check.py [--baseline PATH] [--backend URL] [--timeout SECS]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

_DEFAULT_BASELINE = (
    Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "baselines" / "canary_baseline.json"
)
_DEFAULT_BACKEND = os.environ.get("RAG_BACKEND_URL", "http://localhost:8000")


def evaluate_one(entry: dict, response_data: dict) -> dict:
    """Evaluate whether `response_data` meets `entry['expected']`. Returns {pass, reasons, actual}."""
    exp = entry.get("expected", {}) or {}
    reasons: list[str] = []
    answer = str(response_data.get("answer", "") or "")
    answer_low = answer.lower()
    sources = response_data.get("sources", []) or []
    qc = response_data.get("quality_check", {}) or {}

    if "answer_must_contain_any" in exp:
        cands = exp["answer_must_contain_any"] or []
        if not any(str(s).lower() in answer_low for s in cands):
            reasons.append(f"answer missing any of {cands}")

    if "sources_allowed_doc_ids" in exp:
        allowed = {str(x) for x in (exp["sources_allowed_doc_ids"] or [])}
        found = [str(s.get("doc_id") or "").strip() for s in sources]
        leaks = [d for d in found if d and d not in allowed]
        if leaks:
            reasons.append(f"cross-doc leakage: sources include doc_ids {sorted(set(leaks))} outside allowed {sorted(allowed)}")

    if "min_score" in exp:
        score = qc.get("score")
        if score is None or score < exp["min_score"]:
            reasons.append(f"score {score} below min_score {exp['min_score']}")

    if "has_unavailable_claim" in exp:
        actual = bool(qc.get("has_unavailable_claim"))
        if actual != bool(exp["has_unavailable_claim"]):
            reasons.append(f"has_unavailable_claim={actual} expected {bool(exp['has_unavailable_claim'])}")

    return {
        "pass": not reasons,
        "reasons": reasons,
        "actual": {
            "score": qc.get("score"),
            "source_count": len(sources),
            "answer_length": len(answer),
            "source_doc_ids": [str(s.get("doc_id") or "") for s in sources],
        },
    }


def check_regression(entry: dict, response_data: dict) -> dict:
    """Return {regression: bool, reason: str|None}. Regression = score drop > 15% vs baseline."""
    base = (entry.get("baseline_actual") or {}).get("score")
    qc = response_data.get("quality_check", {}) or {}
    now = qc.get("score")
    if base is None or now is None or base <= 0:
        return {"regression": False, "reason": None}
    drop_pct = (base - now) / base
    if drop_pct > 0.15:
        return {
            "regression": True,
            "reason": f"score dropped {drop_pct*100:.1f}% (baseline={base}, now={now})",
        }
    return {"regression": False, "reason": None}


def _post_query(backend: str, request_body: dict, timeout: float) -> dict | None:
    """POST to /api/chat/stream and parse the 'complete' event. Return None on error."""
    if requests is None:
        return None
    try:
        r = requests.post(
            f"{backend.rstrip('/')}/api/chat/stream",
            json={**request_body, "use_rag": True, "max_tokens": request_body.get("max_tokens", 400)},
            timeout=timeout,
            stream=False,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] backend request failed: {e}", file=sys.stderr)
        return None
    body = r.text
    m = re.search(r"event:\s*complete\s*data:\s*(\{.*\})", body, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for row in rows:
        lines.append(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(row))))
    return "\n".join(lines)


def run(baseline_path: Path, backend: str, timeout: float) -> int:
    if not baseline_path.exists():
        print(
            f"[INFO] baseline not found at {baseline_path}. Run:\n"
            f"  python backend/scripts/eval_canary_baseline.py --force\n"
            f"to generate it. Skipping regression check.",
            file=sys.stderr,
        )
        return 0

    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    entries = data.get("queries", [])
    if not entries:
        print("[WARN] baseline has no queries; skipped", file=sys.stderr)
        return 0

    # Probe backend
    try:
        if requests is not None:
            requests.get(f"{backend.rstrip('/')}/api/health/", timeout=10)
    except Exception as e:
        print(f"[WARN] backend down at {backend} ({e}); skipped", file=sys.stderr)
        return 0

    rows = [["query_id", "pass", "regression", "detail"]]
    any_fail = False
    for entry in entries:
        resp = _post_query(backend, entry["request"], timeout)
        if resp is None:
            rows.append([entry["id"], "?", "?", "no response / parse failure"])
            any_fail = True
            continue
        ev = evaluate_one(entry, resp)
        rg = check_regression(entry, resp)
        detail = "; ".join(ev["reasons"]) if ev["reasons"] else ""
        if rg["reason"]:
            detail = (detail + " | " if detail else "") + rg["reason"]
        rows.append([
            entry["id"],
            "PASS" if ev["pass"] else "FAIL",
            "YES" if rg["regression"] else "no",
            detail or "—",
        ])
        if not ev["pass"] or rg["regression"]:
            any_fail = True

    if any_fail:
        print("[RAG Canary] regression detected:\n" + _render_table(rows), file=sys.stderr)
        return 1

    print(f"[RAG Canary] {len(entries)}/{len(entries)} stable")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, default=_DEFAULT_BASELINE)
    p.add_argument("--backend", default=_DEFAULT_BACKEND)
    p.add_argument("--timeout", type=float, default=60.0)
    args = p.parse_args()
    sys.exit(run(args.baseline, args.backend, args.timeout))


if __name__ == "__main__":
    main()
