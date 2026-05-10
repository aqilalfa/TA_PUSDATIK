#!/usr/bin/env python
"""
PostToolUse hook: marks rag_dirty flag when edits touch RAG-critical files.

Reads JSON event from stdin ({"tool_name": "...", "tool_input": {"file_path": "..."}}).
Exits 0 unconditionally — hook must never block the user.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLAG_PATH = ROOT / ".claude" / "_state" / "rag_dirty"

# Substring targets are matched against the normalized forward-slash path.
# This stays robust whether the hook receives an absolute path or a repo-relative one.
TARGETS = (
    "backend/app/core/rag/",
    "backend/app/api/routes/chat.py",
)


def should_mark(file_path: str) -> bool:
    if not file_path:
        return False
    p = file_path.replace("\\", "/").lower()
    if "backend/app/api/routes/chat.py" in p:
        return True
    return "backend/app/core/rag/" in p and p.endswith(".py")


def handle(event: dict) -> None:
    tool_input = (event or {}).get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if should_mark(file_path):
        try:
            FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
            FLAG_PATH.touch()
        except Exception:
            pass  # never block


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    handle(event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
