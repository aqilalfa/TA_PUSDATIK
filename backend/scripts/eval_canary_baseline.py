"""
Generate canary_baseline.json by running 4 canary queries against the running backend
and recording the actual score / source_count / answer_length.

Usage:
    python backend/scripts/eval_canary_baseline.py [--backend URL] [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from eval_regression_check import _post_query, _DEFAULT_BACKEND  # type: ignore

_OUT = (
    Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "baselines" / "canary_baseline.json"
)

_CANARIES = [
    {
        "id": "canary_tabel13_doc1",
        "request": {"message": "apa isi tabel 13?", "document_id": "1"},
        "expected": {
            "answer_must_contain_any": ["Sekretariat Kabinet", "Kejaksaan Agung"],
            "sources_allowed_doc_ids": [1],
            "min_score": 20,
            "has_unavailable_claim": False,
        },
    },
    {
        "id": "canary_pasal5_doc6",
        "request": {"message": "apa isi pasal 5?", "document_id": "6"},
        "expected": {
            "answer_must_contain_any": ["Ayat (7)", "Rencana Induk"],
            "sources_allowed_doc_ids": [6],
            "min_score": 20,
            "has_unavailable_claim": False,
        },
    },
    {
        "id": "canary_leakage_guard",
        "request": {"message": "apa isi tabel 13?", "document_id": "3"},
        "expected": {
            "answer_must_contain_any": ["tidak ditemukan", "tidak ada tabel"],
            "sources_allowed_doc_ids": [3],
            "min_score": 0,
            "has_unavailable_claim": True,
        },
    },
    {
        "id": "canary_general_spbe",
        "request": {"message": "apa itu SPBE?"},
        "expected": {
            "answer_must_contain_any": ["Sistem Pemerintahan Berbasis Elektronik"],
            "min_score": 15,
            "has_unavailable_claim": False,
        },
    },
]


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default=_DEFAULT_BACKEND)
    p.add_argument("--force", action="store_true", help="Overwrite existing baseline without prompting")
    p.add_argument("--timeout", type=float, default=300.0, help="Per-query timeout seconds")
    args = p.parse_args()

    if _OUT.exists() and not args.force:
        print(f"[WARN] baseline already exists at {_OUT}. Pass --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    queries = []
    for c in _CANARIES:
        print(f"[baseline] running {c['id']} ...", file=sys.stderr)
        resp = _post_query(args.backend, c["request"], timeout=args.timeout)
        if resp is None:
            print(f"[ERROR] no response for {c['id']}; aborting", file=sys.stderr)
            sys.exit(2)
        qc = resp.get("quality_check", {}) or {}
        queries.append({
            **c,
            "baseline_actual": {
                "score": qc.get("score"),
                "source_count": len(resp.get("sources", []) or []),
                "answer_length": len(resp.get("answer", "") or ""),
            },
        })

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "commit": _git_head(),
        "queries": queries,
    }
    _OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[baseline] wrote {_OUT} with {len(queries)} canary entries")


if __name__ == "__main__":
    main()
