# RAG Productivity Skills — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Otomasi alur eval regresi + debug jawaban RAG via dua hook (`PostToolUse`, `Stop`), satu magnetic skill (`rag-debug-answer`), tiga script baru (`rag_trace.py`, `eval_regression_check.py`, `eval_canary_baseline.py`), dan satu baseline JSON.

**Architecture:** Hooks menulis/membaca flag file untuk memicu regresi canary sekali per sesi setelah edit RAG. Skill membaca output tracer terstruktur lalu melapor root cause. Semua komponen menggunakan HTTP lokal ke `http://localhost:8000` (kecuali tracer yang boot engine langsung untuk akses internal).

**Tech Stack:** Python 3.12, FastAPI, LangChain, Qdrant, pytest, Claude Code hooks (stdin JSON protocol), Claude Code skills (SKILL.md frontmatter).

Spec: `docs/superpowers/specs/2026-04-22-rag-productivity-skills-design.md`.

---

## File Map

| File | Tipe | Tugas |
|---|---|---|
| `.claude/hooks/rag_mark_dirty.py` | Baru | Task 10 |
| `.claude/hooks/rag_run_regression.py` | Baru | Task 11 |
| `.claude/settings.json` | Modif | Task 12 |
| `.claude/skills/rag-debug-answer/SKILL.md` | Baru | Task 5 |
| `.gitignore` | Modif | Task 1 |
| `backend/app/core/rag/langchain_engine.py:1380` | Modif | Task 2 |
| `backend/scripts/rag_trace.py` | Baru | Task 3–4 |
| `backend/scripts/eval_regression_check.py` | Baru | Task 6–7 |
| `backend/scripts/eval_canary_baseline.py` | Baru | Task 8 |
| `backend/tests/test_api_sources_doc_id.py` | Baru | Task 2 |
| `backend/tests/test_rag_trace.py` | Baru | Task 3 |
| `backend/tests/test_eval_regression.py` | Baru | Task 6 |
| `backend/tests/test_rag_mark_dirty.py` | Baru | Task 10 |
| `docs/evaluation/baselines/canary_baseline.json` | Baru | Task 9 |
| `QUICKSTART.md` | Modif | Task 13 |

---

## Task 1: Scaffolding (directories + gitignore)

**Files:**
- Create: `.claude/_state/.gitkeep`
- Create: `.claude/hooks/` (empty for now)
- Create: `.claude/skills/rag-debug-answer/` (empty for now)
- Create: `docs/evaluation/baselines/` (empty for now)
- Modify: `.gitignore`

- [ ] **Step 1: Create directories (Git-bash syntax)**

```bash
mkdir -p .claude/_state .claude/hooks .claude/skills/rag-debug-answer docs/evaluation/baselines
touch .claude/_state/.gitkeep
```

- [ ] **Step 2: Add `.claude/_state/` to `.gitignore`**

Buka `.gitignore`. Tambahkan di bagian bawah (sebelum baris terakhir, atau di akhir file):

```
# Claude Code ephemeral state (dirty flags, session stamps)
.claude/_state/*
!.claude/_state/.gitkeep
```

- [ ] **Step 3: Verify gitignore**

```bash
git check-ignore -v .claude/_state/rag_dirty
```

Expected: baris output menunjukkan match pada aturan `.claude/_state/*`.

- [ ] **Step 4: Commit**

```bash
git add .gitignore .claude/_state/.gitkeep
git commit -m "chore: scaffold .claude/_state and .claude/hooks dirs for productivity skills"
```

---

## Task 2: Expose `doc_id` di sources API response

Tujuan: comparator regresi bisa memeriksa leakage lintas-dokumen.

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py`
- Create: `backend/tests/test_api_sources_doc_id.py`

- [ ] **Step 1: Tulis failing test**

Buat `backend/tests/test_api_sources_doc_id.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_source_dict_includes_doc_id():
    """Source dict built by retrieve_context must include numeric doc_id field."""
    from langchain_core.documents import Document
    from app.core.rag.langchain_engine import LangchainRAGEngine

    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    # Minimum attrs used by _format_context + source builder
    fake_doc = Document(
        page_content="dummy",
        metadata={
            "document_id": 7,
            "doc_id": "7",
            "filename": "PP Nomor 71 Tahun 2019.pdf",
            "document_title": "PP Nomor 71 Tahun 2019.pdf",
            "judul_dokumen": "PP Nomor 71 Tahun 2019",
        },
    )
    # Minimal shim: call the source builder directly via _build_sources_payload if exposed,
    # atau verifikasi langsung lewat inspect bahwa field "doc_id" muncul di dict.
    # Kita test end-to-end via retrieve_context-slice: isolasi block "4. Build sources list".
    # Verifikasi via inspeksi source bahwa sources.append payload memuat key "doc_id".
    # String "doc_id" muncul di banyak tempat, jadi batasi pencarian ke block sources.append.
    import inspect
    src = inspect.getsource(LangchainRAGEngine.retrieve_context)
    assert 'sources.append' in src, "sources.append block missing"
    anchor = src.index('sources.append')
    block = src[anchor:anchor + 2000]
    assert '"doc_id":' in block, "sources.append payload must include doc_id field"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_api_sources_doc_id.py -v
```

Expected: FAIL (string `"doc_id"` tidak ada di `retrieve_context` sebelum fix).

- [ ] **Step 3: Tambah `doc_id` di source dict**

Buka `backend/app/core/rag/langchain_engine.py`. Cari block `sources.append({` di dalam `retrieve_context()` (sekitar line 1380). Tambahkan field `doc_id` setelah field `id`:

```python
            sources.append({
                "id": i,
                "doc_id": str(meta.get("doc_id") or meta.get("document_id") or ""),
                "document": citation_title,
                "document_short": doc_title,
                "citation_title": citation_title,
                "citation_label": f"[{i}] {citation_title}",
                "section": section,
                "pasal": str(meta.get("pasal") or ""),
                "ayat": str(meta.get("ayat") or ""),
                "context_header": str(meta.get("context_header") or ""),
```

- [ ] **Step 4: Run test — expect PASS**

```bash
venv/Scripts/python -m pytest tests/test_api_sources_doc_id.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py backend/tests/test_api_sources_doc_id.py
git commit -m "feat(api): expose doc_id per source in chat/stream response"
```

---

## Task 3: `rag_trace.py` — sections 1-2 (classify + filter resolution)

**Files:**
- Create: `backend/scripts/rag_trace.py`
- Create: `backend/tests/test_rag_trace.py`

- [ ] **Step 1: Tulis failing test untuk struktur output**

Buat `backend/tests/test_rag_trace.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_trace_has_expected_sections(monkeypatch):
    """trace() returns dict with all 7 required sections."""
    import rag_trace

    # Mock engine to avoid boot
    class FakeEngine:
        _initialized = True
        client = None
        def initialize(self): pass
        def _resolve_doc_target(self, d): return (3, "peraturan-bssn-no-8-tahun-2024.pdf") if d == "3" else None
        def _build_doc_filter(self, d): return "FAKE_FILTER" if d else None
        def _vector_search(self, q, top_k, qdrant_filter=None): return []
        def _bm25_search(self, q, top_k, doc_id=None): return []
        def _table_literal_search(self, q, top_k, doc_id=None): return []
        def _run_hybrid_retrieval(self, **kw): return []
        def retrieve_context(self, **kw): return {"context":"", "sources":[], "raw_docs":[], "query_type":"table"}

    monkeypatch.setattr(rag_trace, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(rag_trace, "expand_query", lambda q: [q])

    out = rag_trace.trace("apa isi tabel 13?", doc_id="3")
    assert set(out.keys()) == {
        "classify_query",
        "filter_resolution",
        "vector_search",
        "bm25_search",
        "table_literal_search",
        "rerank",
        "final_context_and_answer",
    }
    assert out["classify_query"] == "table"
    assert out["filter_resolution"]["resolved"] == (3, "peraturan-bssn-no-8-tahun-2024.pdf")


def test_trace_filter_resolution_unknown_doc(monkeypatch):
    import rag_trace

    class FakeEngine:
        _initialized = True
        client = None
        def initialize(self): pass
        def _resolve_doc_target(self, d): return None
        def _build_doc_filter(self, d): return None
        def _vector_search(self, q, top_k, qdrant_filter=None): return []
        def _bm25_search(self, q, top_k, doc_id=None): return []
        def _table_literal_search(self, q, top_k, doc_id=None): return []
        def _run_hybrid_retrieval(self, **kw): return []
        def retrieve_context(self, **kw): return {"context":"","sources":[],"raw_docs":[],"query_type":"general"}

    monkeypatch.setattr(rag_trace, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(rag_trace, "expand_query", lambda q: [q])

    out = rag_trace.trace("apa itu X?", doc_id="unknown")
    assert out["filter_resolution"]["resolved"] is None
    assert out["filter_resolution"]["qdrant_hit_count"] is None  # no filter → no hit count
```

- [ ] **Step 2: Run test — expect FAIL (import error)**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_rag_trace.py -v
```

Expected: `ModuleNotFoundError: No module named 'rag_trace'`.

- [ ] **Step 3: Tulis skeleton `rag_trace.py` dengan semua 7 seksi**

Buat `backend/scripts/rag_trace.py`:

```python
"""
Trace RAG retrieval pipeline for a single query.

Usage:
    python backend/scripts/rag_trace.py --query "apa isi tabel 13?" [--doc-id 3] [--json]

Emits 7 structured sections (classify_query, filter_resolution, vector_search,
bm25_search, table_literal_search, rerank, final_context_and_answer).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make backend/app importable
_THIS = Path(__file__).resolve()
_BACKEND = _THIS.parents[1]
sys.path.insert(0, str(_BACKEND))

from app.core.rag.langchain_engine import classify_query, langchain_engine  # noqa: E402
from app.core.rag.prompts import expand_query  # noqa: E402


def _get_engine():
    """Return initialized engine singleton. Indirection simplifies test mocking."""
    if not getattr(langchain_engine, "_initialized", False):
        langchain_engine.initialize()
    return langchain_engine


def _doc_brief(doc):
    meta = getattr(doc, "metadata", {}) or {}
    return {
        "filename": meta.get("filename"),
        "section": meta.get("section") or meta.get("context_header"),
        "doc_id": meta.get("doc_id") or meta.get("document_id"),
        "score": meta.get("rerank_score") or meta.get("rrf_score") or meta.get("bm25_score"),
        "table_label": meta.get("table_label"),
    }


def trace(query: str, doc_id: str | None = None) -> dict:
    engine = _get_engine()
    out: dict = {}

    # 1. classify_query
    qt = classify_query(query)
    out["classify_query"] = qt

    # 2. filter_resolution
    resolved = engine._resolve_doc_target(doc_id) if doc_id else None
    qdrant_filter = engine._build_doc_filter(doc_id) if doc_id else None
    hit_count = None
    if qdrant_filter is not None and getattr(engine, "client", None) is not None:
        try:
            hit_count = int(engine.client.count(
                collection_name="document_chunks",
                count_filter=qdrant_filter,
            ).count)
        except Exception as e:  # noqa: BLE001
            hit_count = f"error: {e}"
    out["filter_resolution"] = {
        "doc_id_input": doc_id,
        "resolved": resolved,
        "filter_object": repr(qdrant_filter) if qdrant_filter else None,
        "qdrant_hit_count": hit_count,
    }

    expanded = expand_query(query)[:3]

    # 3. vector_search
    out["vector_search"] = []
    for q in expanded:
        vdocs = engine._vector_search(q, 5, qdrant_filter=qdrant_filter)
        out["vector_search"].append({"query_variant": q, "results": [_doc_brief(d) for d in vdocs]})

    # 4. bm25_search
    out["bm25_search"] = []
    for q in expanded:
        bdocs = engine._bm25_search(q, 5, doc_id=doc_id)
        out["bm25_search"].append({"query_variant": q, "results": [_doc_brief(d) for d in bdocs]})

    # 5. table_literal_search (only for table queries)
    if qt == "table":
        tdocs = engine._table_literal_search(query, 5, doc_id=doc_id)
        out["table_literal_search"] = [_doc_brief(d) for d in tdocs]
    else:
        out["table_literal_search"] = None

    # 6. rerank — take final fused+reranked order from _run_hybrid_retrieval
    fused = engine._run_hybrid_retrieval(
        query=query,
        search_queries=expanded,
        final_top_k=8,
        qdrant_filter=qdrant_filter,
        doc_id=doc_id,
    )
    out["rerank"] = {"final_top_docs": [_doc_brief(d) for d in fused[:8]]}

    # 7. final_context_and_answer
    ctx = engine.retrieve_context(query=query, doc_id=doc_id, use_rag=True)
    out["final_context_and_answer"] = {
        "query_type": ctx.get("query_type"),
        "context_length": len(ctx.get("context", "") or ""),
        "sources_count": len(ctx.get("sources", []) or []),
        "raw_doc_filenames": [
            (d.metadata or {}).get("filename") for d in (ctx.get("raw_docs") or [])
        ],
    }
    return out


def _human(out: dict) -> str:
    lines = []
    for k, v in out.items():
        lines.append(f"\n=== {k} ===")
        lines.append(json.dumps(v, indent=2, ensure_ascii=False, default=str))
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Trace RAG pipeline for one query")
    p.add_argument("--query", required=True)
    p.add_argument("--doc-id", default=None)
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human output")
    args = p.parse_args()

    result = trace(args.query, args.doc_id)
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    else:
        print(_human(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test — expect PASS**

```bash
venv/Scripts/python -m pytest tests/test_rag_trace.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/rag_trace.py backend/tests/test_rag_trace.py
git commit -m "feat(scripts): add rag_trace.py — structured 7-section retrieval tracer"
```

---

## Task 4: `rag_trace.py` smoke run against live backend

Tujuan: pastikan tracer tidak error saat boot engine sungguhan dan memberi output yang berguna.

**Files:** Tidak ada perubahan kode.

- [ ] **Step 1: Pastikan backend / Qdrant running**

```bash
curl -sf http://localhost:6333/collections/document_chunks/exists
```

Expected: JSON response `{"result":{"exists":true},"status":"ok","time":...}`.

- [ ] **Step 2: Jalankan tracer live**

```bash
cd backend
venv/Scripts/python scripts/rag_trace.py --query "apa isi tabel 13?" --doc-id 3
```

Expected: output 7 seksi terisi. `filter_resolution.qdrant_hit_count` > 0. `table_literal_search` ada isinya atau kosong tapi bukan None. `final_context_and_answer.raw_doc_filenames` hanya berisi `peraturan-bssn-no-8-tahun-2024.pdf`.

- [ ] **Step 3: Verifikasi JSON mode**

```bash
venv/Scripts/python scripts/rag_trace.py --query "apa isi pasal 5?" --doc-id 6 --json | python -c "import sys,json; j=json.load(sys.stdin); print('ok' if set(j)=={'classify_query','filter_resolution','vector_search','bm25_search','table_literal_search','rerank','final_context_and_answer'} else 'FAIL')"
```

Expected: `ok`.

- [ ] **Step 4: Commit (no code changes — smoke verified)**

Tidak ada commit; lanjut Task berikutnya.

---

## Task 5: Debug skill — `.claude/skills/rag-debug-answer/SKILL.md`

**Files:**
- Create: `.claude/skills/rag-debug-answer/SKILL.md`

- [ ] **Step 1: Tulis SKILL.md**

Buat `.claude/skills/rag-debug-answer/SKILL.md`:

```markdown
---
name: rag-debug-answer
description: Use when user reports a RAG answer problem in this SPBE project — wrong sources cited, answer contains content from unexpected document, doc_id scoping leaked, fabricated pasal/ayat, unavailable detector triggered incorrectly, or asks why the retriever returned specific docs. Traces classify_query → doc filter → per-path retrieval (vector / BM25 / table-literal) → rerank → context → answer via backend/scripts/rag_trace.py and reports root cause with file:line recommendations.
---

# RAG Answer Debugging Runbook

Magnetic skill. Auto-invokes when user describes symptoms like:
- "kenapa sumbernya dari dokumen X?"
- "jawabannya ngarang Pasal 99"
- "filter document_id tidak jalan"
- "tabel 13 diambil dari dokumen salah"
- "unavailable detector keliru"

## Steps

### 1. Parse the complaint
- Extract: exact query string, optional `document_id`.
- If ambiguous, ask ONE short question: "Query persisnya apa? Dan ada `document_id` yang Anda kirim?" Don't investigate yet.

### 2. Run the tracer
```
python backend/scripts/rag_trace.py --query "<QUERY>" [--doc-id <ID>] --json
```
Capture the JSON. If the command errors (backend/engine not bootable), fallback: ask user to start the backend or provide the request body; you can also hit `/api/chat/stream` via curl and inspect `sources` directly.

### 3. Analyze with this checklist (in order)

| Hypothesis | Signal in trace | Where to fix |
|---|---|---|
| **H1. doc_id tidak ter-resolve** | `filter_resolution.resolved` is `null` despite user passing `doc_id` | `_resolve_doc_target` in `backend/app/core/rag/langchain_engine.py` — check DB query (doc_id string vs id int) |
| **H2. Qdrant payload key mismatch** | `filter_resolution.qdrant_hit_count == 0` but doc exists in DB | `_build_doc_filter` in same file — inspect Qdrant payload structure with a direct scroll |
| **H3. Satu jalur bocor** | Filenames in one of `vector_search` / `bm25_search` / `table_literal_search` differ from target | That path's scoping: `_vector_search` (qdrant_filter), `_bm25_search` (doc_id), `_table_literal_search` (doc_id) |
| **H4. Fallback terlalu agresif** | `qdrant_hit_count > 0` but final `raw_doc_filenames` includes other docs | `retrieve_context` fallback-no-filter branch in `langchain_engine.py` — fallback should only kick in on 0 docs, not on few |
| **H5. Rerank menenggelamkan target** | `rerank.final_top_docs` top-5 none from target filename but earlier paths had them | Cross-encoder model — usually tuning, not a bug; confirm with user |
| **H6. Unavailable detector over-trigger** | Answer contains deskriptif "tidak tercantum" + `quality_check.has_unavailable_claim=true` while context clearly has numeric evidence | `_contains_unavailable_signal` in `backend/app/api/routes/chat.py` — see Fase 2 plan `sementara-ini-saya-memiliki-playful-kay.md` |

Report format:
- **Symptom** — one line quoting user complaint
- **Trace evidence** — the section(s) that triggered hypothesis
- **Root cause** — pick ONE most likely H#
- **Fix target** — exact file:line
- **Next step** — "Hand off to superpowers:test-driven-development to write a failing test before editing <file>"

### 4. Do NOT apply the fix yourself
This skill only diagnoses. After reporting, wait for user confirmation. When they confirm, invoke `superpowers:test-driven-development` — write the failing test first.

### 5. Escalation
If 2 iterations of H1–H6 don't explain the symptom:
1. Ask user for the commit SHA of the last known-good state.
2. Suggest `git bisect start HEAD <known-good-sha>` with the tracer command as the test.
```

- [ ] **Step 2: Verifikasi skill terdeteksi**

```bash
ls .claude/skills/rag-debug-answer/SKILL.md
```

Expected: file ada. (Claude Code akan memuat skill otomatis di sesi berikutnya — tidak perlu tes runtime di sini.)

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/rag-debug-answer/SKILL.md
git commit -m "feat(skills): add magnetic rag-debug-answer skill with tracer-based runbook"
```

---

## Task 6: Comparator tests untuk `eval_regression_check.py`

**Files:**
- Create: `backend/tests/test_eval_regression.py`
- Create: `backend/scripts/eval_regression_check.py` (stub first)

- [ ] **Step 1: Tulis failing tests untuk logika perbandingan**

Buat `backend/tests/test_eval_regression.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _entry(id_, expected, baseline_actual=None):
    return {
        "id": id_,
        "request": {"message": "dummy"},
        "expected": expected,
        "baseline_actual": baseline_actual or {"score": 25, "source_count": 5, "answer_length": 500},
    }


def _resp(answer="", sources=None, score=25, has_unavailable=False):
    return {
        "answer": answer,
        "sources": sources or [],
        "quality_check": {"score": score, "has_unavailable_claim": has_unavailable},
    }


def test_pass_when_all_expectations_met():
    import eval_regression_check as m
    entry = _entry("x", {"answer_must_contain_any": ["foo"], "min_score": 20, "has_unavailable_claim": False})
    res = m.evaluate_one(entry, _resp(answer="lorem foo ipsum"))
    assert res["pass"] is True
    assert res["reasons"] == []


def test_fail_on_missing_keyword():
    import eval_regression_check as m
    entry = _entry("x", {"answer_must_contain_any": ["foo", "bar"]})
    res = m.evaluate_one(entry, _resp(answer="lorem ipsum"))
    assert res["pass"] is False
    assert any("missing" in r for r in res["reasons"])


def test_fail_on_leakage_by_doc_id():
    import eval_regression_check as m
    entry = _entry("x", {"sources_allowed_doc_ids": [3]})
    bad = _resp(sources=[{"doc_id": "3"}, {"doc_id": "1"}])
    res = m.evaluate_one(entry, bad)
    assert res["pass"] is False
    assert any("leakage" in r.lower() or "allowed" in r.lower() for r in res["reasons"])


def test_pass_on_exact_allowed_doc_ids():
    import eval_regression_check as m
    entry = _entry("x", {"sources_allowed_doc_ids": [6]})
    ok = _resp(sources=[{"doc_id": "6"}, {"doc_id": "6"}])
    res = m.evaluate_one(entry, ok)
    assert res["pass"] is True


def test_fail_on_score_below_min():
    import eval_regression_check as m
    entry = _entry("x", {"min_score": 20})
    res = m.evaluate_one(entry, _resp(score=15))
    assert res["pass"] is False


def test_fail_on_unavailable_mismatch():
    import eval_regression_check as m
    entry = _entry("x", {"has_unavailable_claim": True})
    res = m.evaluate_one(entry, _resp(has_unavailable=False))
    assert res["pass"] is False


def test_regression_on_score_drop_more_than_15pct():
    import eval_regression_check as m
    entry = _entry("x", {"min_score": 0}, baseline_actual={"score": 20, "source_count": 5, "answer_length": 500})
    # 15% of 20 = 3.0 → anything <17 is regression
    res = m.check_regression(entry, _resp(score=16))
    assert res["regression"] is True
    entry2 = _entry("y", {"min_score": 0}, baseline_actual={"score": 20, "source_count": 5, "answer_length": 500})
    res2 = m.check_regression(entry2, _resp(score=18))
    assert res2["regression"] is False
```

- [ ] **Step 2: Create stub file so pytest can collect**

Buat `backend/scripts/eval_regression_check.py`:

```python
"""Canary regression comparator for RAG backend. Stub — filled in Task 7."""


def evaluate_one(entry, response_data):
    raise NotImplementedError


def check_regression(entry, response_data):
    raise NotImplementedError
```

- [ ] **Step 3: Run tests — expect FAIL (NotImplementedError)**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_eval_regression.py -v
```

Expected: 7 tests FAIL with NotImplementedError.

- [ ] **Step 4: Commit failing tests + stub**

```bash
git add backend/scripts/eval_regression_check.py backend/tests/test_eval_regression.py
git commit -m "test(eval): add failing tests for canary regression comparator"
```

---

## Task 7: Implement `eval_regression_check.py`

**Files:**
- Modify: `backend/scripts/eval_regression_check.py`

- [ ] **Step 1: Replace stub with full implementation**

Timpa `backend/scripts/eval_regression_check.py`:

```python
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
            requests.get(f"{backend.rstrip('/')}/api/health/", timeout=3)
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
```

- [ ] **Step 2: Run tests — expect PASS**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_eval_regression.py -v
```

Expected: 7/7 PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/eval_regression_check.py
git commit -m "feat(scripts): implement canary regression comparator + runner"
```

---

## Task 8: Baseline generator `eval_canary_baseline.py`

**Files:**
- Create: `backend/scripts/eval_canary_baseline.py`

- [ ] **Step 1: Tulis script**

Buat `backend/scripts/eval_canary_baseline.py`:

```python
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
    args = p.parse_args()

    if _OUT.exists() and not args.force:
        print(f"[WARN] baseline already exists at {_OUT}. Pass --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    queries = []
    for c in _CANARIES:
        print(f"[baseline] running {c['id']} ...", file=sys.stderr)
        resp = _post_query(args.backend, c["request"], timeout=120.0)
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
```

- [ ] **Step 2: Smoke-run (dry)**

Tanpa `--force`, jika file belum ada, script akan mencoba generate. Jalankan:

```bash
cd backend
venv/Scripts/python scripts/eval_canary_baseline.py --force
```

Expected (requires backend running on port 8000): output "[baseline] running canary_tabel13_doc1 ..." × 4, lalu "wrote docs/evaluation/baselines/canary_baseline.json with 4 canary entries".

Catatan: di port mana backend berjalan? Kalau port 8000 tidak tersedia, pass `--backend http://localhost:8001`.

- [ ] **Step 3: Commit script (baseline JSON akan di-commit di Task 9)**

```bash
git add backend/scripts/eval_canary_baseline.py
git commit -m "feat(scripts): add canary baseline generator"
```

---

## Task 9: Generate & commit initial baseline

**Files:**
- Create: `docs/evaluation/baselines/canary_baseline.json`

- [ ] **Step 1: Pastikan backend berjalan dengan fix doc_id terbaru**

```bash
curl -sf http://localhost:8000/api/health/ && echo OK
```

Kalau tidak OK, start backend:

```bash
cd backend
PYTHONIOENCODING=utf-8 venv/Scripts/python -m uvicorn app.main:app --port 8000 --log-level warning
```

- [ ] **Step 2: Generate baseline**

```bash
venv/Scripts/python scripts/eval_canary_baseline.py --force
```

Expected: 4 entries tertulis ke `docs/evaluation/baselines/canary_baseline.json`.

- [ ] **Step 3: Verifikasi isi baseline**

```bash
venv/Scripts/python -c "import json; d=json.load(open('../docs/evaluation/baselines/canary_baseline.json', encoding='utf-8')); print('entries:', len(d['queries'])); [print(q['id'], '→ score=', q['baseline_actual']['score']) for q in d['queries']]"
```

Expected: 4 entries, semua punya `score` angka non-None.

- [ ] **Step 4: Smoke-run regresi (harus bersih)**

```bash
venv/Scripts/python scripts/eval_regression_check.py
```

Expected: `[RAG Canary] 4/4 stable`. Exit code 0.

- [ ] **Step 5: Commit**

```bash
cd ..
git add docs/evaluation/baselines/canary_baseline.json
git commit -m "chore(eval): seed canary_baseline.json (post doc_id-filter fix)"
```

---

## Task 10: Hook `rag_mark_dirty.py` + test

**Files:**
- Create: `.claude/hooks/rag_mark_dirty.py`
- Create: `backend/tests/test_rag_mark_dirty.py`

- [ ] **Step 1: Tulis failing test**

Buat `backend/tests/test_rag_mark_dirty.py`:

```python
import sys, os, json, tempfile, pathlib, importlib.util


def _load():
    root = pathlib.Path(__file__).resolve().parents[2]
    p = root / ".claude" / "hooks" / "rag_mark_dirty.py"
    spec = importlib.util.spec_from_file_location("rag_mark_dirty", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_matches_rag_core_edit(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    assert mod.should_mark("backend/app/core/rag/langchain_engine.py")
    mod.handle({"tool_input": {"file_path": "backend/app/core/rag/langchain_engine.py"}})
    assert flag.exists()


def test_matches_chat_route(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    mod.handle({"tool_input": {"file_path": "backend/app/api/routes/chat.py"}})
    assert flag.exists()


def test_ignores_non_rag_file(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    mod.handle({"tool_input": {"file_path": "frontend/src/views/ChatView.vue"}})
    assert not flag.exists()


def test_handles_missing_file_path(tmp_path, monkeypatch):
    mod = _load()
    flag = tmp_path / "rag_dirty"
    monkeypatch.setattr(mod, "FLAG_PATH", flag)
    mod.handle({"tool_input": {}})
    assert not flag.exists()
```

- [ ] **Step 2: Run test — expect FAIL (file tidak ada)**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_rag_mark_dirty.py -v
```

Expected: FAIL — module tidak ditemukan.

- [ ] **Step 3: Tulis `.claude/hooks/rag_mark_dirty.py`**

Buat `.claude/hooks/rag_mark_dirty.py`:

```python
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
```

- [ ] **Step 4: Run test — expect PASS**

```bash
venv/Scripts/python -m pytest tests/test_rag_mark_dirty.py -v
```

Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
cd ..
git add .claude/hooks/rag_mark_dirty.py backend/tests/test_rag_mark_dirty.py
git commit -m "feat(hooks): add rag_mark_dirty PostToolUse hook"
```

---

## Task 11: Hook `rag_run_regression.py` (Stop)

**Files:**
- Create: `.claude/hooks/rag_run_regression.py`

- [ ] **Step 1: Tulis hook**

Buat `.claude/hooks/rag_run_regression.py`:

```python
#!/usr/bin/env python
"""
Stop hook: runs canary regression check if .claude/_state/rag_dirty flag exists.

Always exits 0 (hook must never block), but prints regression output to stderr so
Claude reads it in the tool result. Clears the flag at the end regardless.
"""
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
        _ = sys.stdin.read()  # consume stdin event, ignore content
    except Exception:
        pass

    if not FLAG_PATH.exists():
        return 0
    if not SCRIPT.exists():
        # Script missing — clear flag and exit
        try: FLAG_PATH.unlink()
        except Exception: pass
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
        try: FLAG_PATH.unlink()
        except Exception: pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test hook manual**

Pastikan backend running + baseline tersedia. Jalankan:

```bash
touch .claude/_state/rag_dirty
echo '{}' | python .claude/hooks/rag_run_regression.py
```

Expected: output `[RAG Canary] 4/4 stable` dan flag `.claude/_state/rag_dirty` hilang.

- [ ] **Step 3: Commit**

```bash
git add .claude/hooks/rag_run_regression.py
git commit -m "feat(hooks): add rag_run_regression Stop hook with flag-gated canary runner"
```

---

## Task 12: Wire hooks di `.claude/settings.json`

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: Cek file settings existing**

```bash
cat .claude/settings.json 2>/dev/null || echo "NO FILE"
```

Jika file belum ada: buat dengan isi berikut. Jika ada: merge block `hooks` ke object root (jaga setting lain).

- [ ] **Step 2: Tulis (atau merge) `settings.json`**

Minimal content kalau file belum ada:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/rag_mark_dirty.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/rag_run_regression.py"
          }
        ]
      }
    ]
  }
}
```

Kalau sudah ada setting lain, tambahkan hanya properti `hooks` (merge), jangan timpa file.

- [ ] **Step 3: Verifikasi JSON valid**

```bash
python -c "import json; json.load(open('.claude/settings.json', encoding='utf-8')); print('valid')"
```

Expected: `valid`.

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "chore(claude): wire PostToolUse + Stop hooks for RAG canary automation"
```

---

## Task 13: Update `QUICKSTART.md`

**Files:**
- Modify: `QUICKSTART.md`

- [ ] **Step 1: Tambah seksi "RAG canary regression"**

Buka `QUICKSTART.md`. Tambah seksi baru sebelum bagian akhir:

```markdown
## RAG canary regression & debug

**Regresi canary (otomatis di akhir tiap sesi Claude yang menyentuh RAG):**

Claude Code menjalankan 4 canary queries terhadap backend saat Anda selesai
mengedit file RAG. Output regresi muncul di log harness (stderr). Tidak perlu
tindakan manual.

**Regenerate baseline** (setelah refactor yang mengubah skor secara sengaja):

```bash
cd backend
venv/Scripts/python scripts/eval_canary_baseline.py --force
```

**Run check manual:**

```bash
venv/Scripts/python scripts/eval_regression_check.py
```

**Trace satu query untuk debug:**

```bash
venv/Scripts/python scripts/rag_trace.py --query "apa isi tabel 13?" --doc-id 3
```

Untuk dipakai Claude Code: ketik keluhan seperti "kenapa sumbernya salah" atau
"filter document_id bocor" — skill `rag-debug-answer` akan auto-invoke dan
melakukan tracing + analisis checklist.
```

- [ ] **Step 2: Commit**

```bash
git add QUICKSTART.md
git commit -m "docs: document RAG canary regression and debug skill"
```

---

## Task 14: End-to-end smoke test

**Files:** Tidak ada perubahan kode.

- [ ] **Step 1: Clear state**

```bash
rm -f .claude/_state/rag_dirty
```

- [ ] **Step 2: Simulate PostToolUse hook pada file RAG**

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"backend/app/core/rag/langchain_engine.py"}}' | python .claude/hooks/rag_mark_dirty.py
ls .claude/_state/rag_dirty
```

Expected: flag file ada.

- [ ] **Step 3: Simulate PostToolUse pada non-RAG file (harus diabaikan)**

```bash
rm -f .claude/_state/rag_dirty
echo '{"tool_name":"Edit","tool_input":{"file_path":"frontend/src/views/ChatView.vue"}}' | python .claude/hooks/rag_mark_dirty.py
ls .claude/_state/rag_dirty 2>&1 | head -1
```

Expected: `ls: cannot access ...rag_dirty` (flag tidak dibuat).

- [ ] **Step 4: Simulate Stop hook dengan flag**

```bash
touch .claude/_state/rag_dirty
echo '{}' | python .claude/hooks/rag_run_regression.py
```

Expected: output `[RAG Canary] 4/4 stable`, flag dihapus.

- [ ] **Step 5: Simulate Stop hook tanpa flag (harus diam)**

```bash
rm -f .claude/_state/rag_dirty
echo '{}' | python .claude/hooks/rag_run_regression.py
```

Expected: tidak ada output, exit 0.

- [ ] **Step 6: Re-run all unit tests**

```bash
cd backend
venv/Scripts/python -m pytest tests/ -v
```

Expected: semua test PASS (termasuk test lama + test_rag_routing, test_rag_trace, test_eval_regression, test_rag_mark_dirty, test_api_sources_doc_id).

- [ ] **Step 7: Final commit (no changes, checkpoint only — skip if nothing to commit)**

Kalau semua langkah hijau, plan selesai. Skills siap dipakai di sesi Claude Code berikutnya.
