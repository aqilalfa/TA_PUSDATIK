#!/usr/bin/env python
"""Stop hook: runs canary regression check if .claude/_state/rag_dirty flag exists."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLAG_PATH = ROOT / ".claude" / "_state" / "rag_dirty"
SCRIPT = ROOT / "backend" / "scripts" / "eval_regression_check.py"
VENV_PY = ROOT / "backend" / "venv" / "Scripts" / "python.exe"


def main() -> int:
    try:
        _ = sys.stdin.read()
    except Exception:
        pass

    if not FLAG_PATH.exists():
        return 0

    if not SCRIPT.exists():
        try:
            FLAG_PATH.unlink()
        except Exception:
            pass
        return 0

    py = str(VENV_PY if VENV_PY.exists() else sys.executable)
    try:
        proc = subprocess.run(
            [py, str(SCRIPT)],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(ROOT / "backend"),
        )
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
    except subprocess.TimeoutExpired:
        sys.stderr.write("[RAG Canary] hook timeout after 90s; skipped\n")
    except Exception as e:
        sys.stderr.write(f"[RAG Canary] hook error: {e}\n")
    finally:
        try:
            FLAG_PATH.unlink()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
