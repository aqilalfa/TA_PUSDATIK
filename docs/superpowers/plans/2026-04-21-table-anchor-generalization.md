# Table Completeness Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hardcoded `"tahap persiapan/pelaksanaan/pelaporan"` bias (7 locations) with generic anchor detection so any table is retrieved and answered correctly, not just Tabel 13.

**Architecture:** Two new methods (`_extract_table_anchors`, `_table_anchor_coverage_score`) replace the hardcoded `_table_stage_coverage_score`. Scoring/retry/guardrail/quality-check code reads anchors dynamically from retrieved chunk text rather than assuming a fixed 3-stage structure.

**Tech Stack:** Python, LangChain `Document`, regex, `collections.Counter`. No new dependencies.

---

## File Map

| File | Change |
|---|---|
| `backend/app/core/rag/langchain_engine.py` | Add 2 new methods; edit 5 locations |
| `backend/app/api/routes/chat.py` | Remove 3 functions + stage scoring from 2 functions |
| `backend/tests/test_table_anchor.py` | New test file |
| `backend/tests/test_quality_scoring.py` | New test file |

---

### Task 1: Write failing tests for new anchor methods

**Files:**
- Create: `backend/tests/test_table_anchor.py`

- [ ] **Step 1: Create the test file**

```python
# backend/tests/test_table_anchor.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from langchain_core.documents import Document
from app.core.rag.langchain_engine import LangchainRAGEngine

engine = LangchainRAGEngine.__new__(LangchainRAGEngine)


def test_extract_anchors_finds_recurring_phrases():
    """Phrases appearing in ≥2 chunks of the target table should be anchors."""
    docs = [
        Document(
            page_content="Tabel 5: domain satu nilai bobot 80\naspek teknis memuaskan",
            metadata={"table_label": "Tabel 5"},
        ),
        Document(
            page_content="Tabel 5 lanjutan\ndomain satu aspek teknis nilai 90",
            metadata={"table_label": "Tabel 5"},
        ),
    ]
    anchors = engine._extract_table_anchors(docs, "5", min_hits=2)
    assert isinstance(anchors, list)
    # "domain satu" and "aspek teknis" each appear in 2 chunks
    anchor_blob = " ".join(anchors)
    assert "domain satu" in anchor_blob or "aspek teknis" in anchor_blob


def test_extract_anchors_empty_when_no_table_chunks():
    """No matching table chunks → no anchors extracted."""
    docs = [
        Document(page_content="ini pasal biasa tidak ada tabel", metadata={}),
    ]
    anchors = engine._extract_table_anchors(docs, "5", min_hits=2)
    assert anchors == []


def test_extract_anchors_empty_doc_list():
    anchors = engine._extract_table_anchors([], "13", min_hits=2)
    assert anchors == []


def test_extract_anchors_respects_max_anchors():
    """Never return more than max_anchors entries."""
    # 6 distinct 2-word phrases repeated across 2 docs
    content_a = "alpha beta gamma delta epsilon zeta alpha beta gamma delta epsilon zeta"
    content_b = "alpha beta gamma delta epsilon zeta alpha beta gamma delta epsilon zeta"
    docs = [
        Document(page_content=f"Tabel 7\n{content_a}", metadata={"table_label": "Tabel 7"}),
        Document(page_content=f"Tabel 7\n{content_b}", metadata={"table_label": "Tabel 7"}),
    ]
    anchors = engine._extract_table_anchors(docs, "7", min_hits=2, max_anchors=3)
    assert len(anchors) <= 3


def test_anchor_coverage_counts_present_anchors():
    """Score = number of anchors present in combined docs text."""
    docs = [
        Document(page_content="domain satu nilai 80 domain dua nilai 90", metadata={}),
    ]
    anchors = ["domain satu", "domain dua", "domain tiga"]
    score = engine._table_anchor_coverage_score(docs, anchors)
    assert score == 2  # domain tiga not present


def test_anchor_coverage_zero_with_no_anchors():
    """Empty anchor list → 0 (no penalty)."""
    docs = [Document(page_content="anything", metadata={})]
    assert engine._table_anchor_coverage_score(docs, []) == 0


def test_anchor_coverage_zero_with_empty_docs():
    assert engine._table_anchor_coverage_score([], ["domain satu"]) == 0
```

- [ ] **Step 2: Run to confirm they fail (methods don't exist yet)**

```
cd backend && python -m pytest tests/test_table_anchor.py -v 2>&1 | head -40
```

Expected: `AttributeError: '_extract_table_anchors'` — confirms tests are wired correctly.

---

### Task 2: Implement `_extract_table_anchors` and `_table_anchor_coverage_score`

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py` — add two methods after `_table_stage_coverage_score` (line ~427)

- [ ] **Step 3: Add `Counter` import at top of file (line 11, add to existing imports block)**

The file already imports from `collections` indirectly — add explicitly:

```python
from collections import Counter
```

Add this line after `import re` (line 14).

- [ ] **Step 4: Add the two new methods after `_table_stage_coverage_score` (after line 426)**

Find this exact block in the file:
```python
    @staticmethod
    def _table_stage_coverage_score(docs: List[Document]) -> int:
        """Score table retrieval completeness by counting mandatory stage headings found in docs."""
        if not docs:
            return 0

        blob = "\n".join((doc.page_content or "") for doc in docs).lower()
        required_markers = (
            "tahap persiapan",
            "tahap pelaksanaan",
            "tahap pelaporan",
        )
        return sum(1 for marker in required_markers if marker in blob)
```

Replace the entire `_table_stage_coverage_score` method with the two new methods:

```python
    @staticmethod
    def _extract_table_anchors(
        docs: List[Document],
        table_no: str,
        min_hits: int = 2,
        max_anchors: int = 5,
    ) -> List[str]:
        """Extract recurring structural phrases from retrieved table chunks.

        A phrase found in >= min_hits distinct chunks is likely a real column
        header or row label for this table, not noise. Returns at most
        max_anchors phrases sorted by frequency.
        """
        if not docs or not table_no:
            return []

        target_label = f"tabel {table_no}".lower()
        phrase_pattern = re.compile(
            r"[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F\s]{4,39}[A-Za-z\u00C0-\u024F]"
        )

        table_chunks = [
            d for d in docs
            if target_label in (d.page_content or "").lower()
            or str(d.metadata.get("table_label", "")).lower() == target_label
        ]
        if not table_chunks:
            return []

        phrase_counter: Counter = Counter()
        for doc in table_chunks:
            preview = (doc.page_content or "")[:400]
            found = {m.group().strip().lower() for m in phrase_pattern.finditer(preview)}
            for phrase in found:
                if len(phrase.split()) >= 2:
                    phrase_counter[phrase] += 1

        anchors = [
            phrase
            for phrase, count in phrase_counter.most_common(20)
            if count >= min_hits
        ]
        return anchors[:max_anchors]

    @staticmethod
    def _table_anchor_coverage_score(docs: List[Document], anchors: List[str]) -> int:
        """Count how many anchors appear in combined docs text.

        Returns 0 when anchors is empty (no anchors = no penalty, treat as complete).
        """
        if not anchors or not docs:
            return 0
        blob = "\n".join((doc.page_content or "") for doc in docs).lower()
        return sum(1 for anchor in anchors if anchor in blob)
```

- [ ] **Step 5: Run tests — expect them to pass now**

```
cd backend && python -m pytest tests/test_table_anchor.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py backend/tests/test_table_anchor.py
git commit -m "feat(rag): add _extract_table_anchors and _table_anchor_coverage_score"
```

---

### Task 3: Remove stage_markers from `_table_literal_search`

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py` lines ~313–339

- [ ] **Step 7: Replace the stage-biased scoring block in `_table_literal_search`**

Find this exact block:
```python
            text_blob = text.lower()[:2800]
            stage_markers = (
                "tahap persiapan",
                "tahap pelaksanaan",
                "tahap pelaporan",
            )
            stage_hits = sum(1 for marker in stage_markers if marker in text_blob)
            mention_only_index = (
                "daftar tabel" in text_blob and stage_hits == 0
            )

            score = 2.50
            if "lampiran" in meta_blob or "lampiran" in text.lower()[:500]:
                score += 0.30
            if nomor_match and re.search(rf"\b{re.escape(nomor_match.group(1))}\b", meta_blob):
                score += 0.25
            if tahun_match and re.search(rf"\b{re.escape(tahun_match.group(1))}\b", meta_blob):
                score += 0.25
            if metadata.get("pasal"):
                score -= 0.10
            if stage_hits > 0:
                score += min(1.20, 0.45 * stage_hits)
            if mention_only_index:
                score -= 0.95
            if "isi" in q and mention_only_index:
                score -= 0.35
            if len(text.strip()) < 280 and stage_hits == 0:
                score -= 0.25
```

Replace with:
```python
            text_blob = text.lower()[:2800]
            mention_only_index = "daftar tabel" in text_blob

            score = 2.50
            if "lampiran" in meta_blob or "lampiran" in text.lower()[:500]:
                score += 0.30
            if nomor_match and re.search(rf"\b{re.escape(nomor_match.group(1))}\b", meta_blob):
                score += 0.25
            if tahun_match and re.search(rf"\b{re.escape(tahun_match.group(1))}\b", meta_blob):
                score += 0.25
            if metadata.get("pasal"):
                score -= 0.10
            if mention_only_index:
                score -= 0.95
            if "isi" in q and mention_only_index:
                score -= 0.35
            if len(text.strip()) < 280:
                score -= 0.25
```

- [ ] **Step 8: Verify existing tests still pass**

```
cd backend && python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "refactor(rag): remove hardcoded stage_markers from _table_literal_search"
```

---

### Task 4: Remove stage_markers from `_is_table_index_noise_doc`

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py` lines ~447–483

- [ ] **Step 10: Replace the stage-dependent noise detection block**

Find this exact block inside `_is_table_index_noise_doc`:
```python
        stage_markers = (
            "tahap persiapan",
            "tahap pelaksanaan",
            "tahap pelaporan",
        )
        has_stage_content = any(marker in text_blob for marker in stage_markers)

        has_table_semantic_content = any(
```

Replace with (remove `stage_markers` tuple and `has_stage_content`, keep the rest):
```python
        has_table_semantic_content = any(
```

Then find the return statement:
```python
        return (
            mentions_target_table
            and is_index_like
            and not has_stage_content
            and not has_table_semantic_content
            and very_short
        )
```

Replace with:
```python
        return (
            mentions_target_table
            and is_index_like
            and not has_table_semantic_content
            and very_short
        )
```

- [ ] **Step 11: Run all tests**

```
cd backend && python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 12: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "refactor(rag): remove stage_markers dependency from _is_table_index_noise_doc"
```

---

### Task 5: Remove stage_markers boost from hybrid retrieval

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py` lines ~1082–1095

- [ ] **Step 13: Replace the stage-biased hybrid boost block**

Find this exact block (inside the `if table_match:` section of `_query_metadata_boost`):
```python
            stage_markers = (
                "tahap persiapan",
                "tahap pelaksanaan",
                "tahap pelaporan",
            )
            stage_hits = sum(1 for marker in stage_markers if marker in text_blob)
            if stage_hits > 0:
                boost += min(1.20, 0.45 * stage_hits)

            mention_only_index = "daftar tabel" in text_blob and stage_hits == 0
            if mention_only_index:
                boost -= 0.95
            if "isi" in q and mention_only_index:
                boost -= 0.35
```

Replace with:
```python
            mention_only_index = "daftar tabel" in text_blob
            if mention_only_index:
                boost -= 0.95
            if "isi" in q and mention_only_index:
                boost -= 0.35
```

- [ ] **Step 14: Run all tests**

```
cd backend && python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 15: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "refactor(rag): remove hardcoded stage_markers boost from hybrid retrieval"
```

---

### Task 6: Replace hardcoded retry in `retrieve_context` with anchor-based retry

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py` lines ~1237–1286

- [ ] **Step 16: Replace the entire table completeness safety-net block**

Find this exact block:
```python
        # Table completeness safety-net: if retrieval only captures partial table, retry once
        # with stronger stage anchors while still preserving the original query intent.
        if is_table_query:
            base_coverage = self._table_stage_coverage_score(docs)
            if base_coverage < 3:
                retry_queries = list(expanded_queries)
                self._append_unique_search_query(
                    retry_queries,
                    (
                        f"{query} tahap persiapan tahap pelaksanaan tahap pelaporan"
                    ),
                )

                table_match = re.search(
                    r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b",
                    query,
                    re.IGNORECASE,
                )
                if table_match:
                    table_no = table_match.group(1)
                    self._append_unique_search_query(
                        retry_queries,
                        (
                            f"{query} tabel {table_no} tahap pelaksanaan tahap pelaporan"
                        ),
                    )

                retry_docs = self._run_hybrid_retrieval(
                    query=query,
                    search_queries=retry_queries,
                    final_top_k=final_top_k,
                    vector_top_k=max(self.vector_top_k, final_top_k * 4),
                    bm25_top_k=max(self.bm25_top_k, final_top_k * 4),
                    literal_table_top_k=max(6, final_top_k * 2),
                    qdrant_filter=qdrant_filter,
                    doc_id=doc_id,
                )
                retry_coverage = self._table_stage_coverage_score(retry_docs)

                if retry_coverage > base_coverage:
                    logger.info(
                        "[Retrieval] Table completeness improved "
                        f"({base_coverage} -> {retry_coverage}); using retry results"
                    )
                    docs = retry_docs
                else:
                    logger.info(
                        "[Retrieval] Table completeness retry did not improve "
                        f"({base_coverage} -> {retry_coverage}); keeping initial results"
                    )
```

Replace with:
```python
        # Table completeness safety-net: if anchor-based coverage is low, retry once
        # using the missing anchor phrases as additional query keywords.
        if is_table_query:
            anchor_table_match = re.search(
                r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", query, re.IGNORECASE
            )
            anchor_table_no = anchor_table_match.group(1) if anchor_table_match else ""
            anchors = self._extract_table_anchors(docs, anchor_table_no)
            base_coverage = self._table_anchor_coverage_score(docs, anchors)
            anchor_threshold = max(1, len(anchors) // 2) if anchors else 0

            if anchors and base_coverage < anchor_threshold:
                combined_blob = "\n".join(
                    (d.page_content or "") for d in docs
                ).lower()
                missing_anchors = [a for a in anchors if a not in combined_blob]
                retry_queries = list(expanded_queries)
                if missing_anchors:
                    self._append_unique_search_query(
                        retry_queries,
                        f"{query} {' '.join(missing_anchors[:3])}",
                    )

                retry_docs = self._run_hybrid_retrieval(
                    query=query,
                    search_queries=retry_queries,
                    final_top_k=final_top_k,
                    vector_top_k=max(self.vector_top_k, final_top_k * 4),
                    bm25_top_k=max(self.bm25_top_k, final_top_k * 4),
                    literal_table_top_k=max(6, final_top_k * 2),
                    qdrant_filter=qdrant_filter,
                    doc_id=doc_id,
                )
                retry_coverage = self._table_anchor_coverage_score(retry_docs, anchors)

                if retry_coverage > base_coverage:
                    logger.info(
                        "[Retrieval] Table anchor coverage improved "
                        f"({base_coverage} -> {retry_coverage}); using retry results"
                    )
                    docs = retry_docs
                else:
                    logger.info(
                        "[Retrieval] Table anchor retry did not improve "
                        f"({base_coverage} -> {retry_coverage}); keeping initial results"
                    )
```

- [ ] **Step 17: Run all tests**

```
cd backend && python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 18: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "feat(rag): replace hardcoded stage retry with anchor-based table completeness retry"
```

---

### Task 7: Remove stage injection from `_build_table_guardrail`

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py` lines ~870–910

- [ ] **Step 19: Replace the entire `_build_table_guardrail` method**

Find:
```python
    def _build_table_guardrail(self, query: str, context: str) -> str:
        """Build dynamic instruction so table queries do not collapse to false negatives."""
        q = str(query or "")
        c = str(context or "")
        table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", q, re.IGNORECASE)
        if not table_match:
            return ""

        table_no = table_match.group(1)
        table_pattern = re.compile(
            rf"\b(?:tabel|table)\s*(?:ke[-\s]*)?{re.escape(table_no)}\b",
            re.IGNORECASE,
        )

        if not table_pattern.search(c):
            return ""

        available_stages = []
        if re.search(r"\btahap\s+persiapan\b", c, re.IGNORECASE):
            available_stages.append("Tahap Persiapan")
        if re.search(r"\btahap\s+pelaksanaan\b", c, re.IGNORECASE):
            available_stages.append("Tahap Pelaksanaan")
        if re.search(r"\btahap\s+pelaporan\b", c, re.IGNORECASE):
            available_stages.append("Tahap Pelaporan")

        stage_instruction = ""
        if available_stages:
            stages_text = ", ".join(available_stages)
            stage_instruction = (
                f" Konteks memuat tahap berikut: {stages_text}. "
                "Wajib rangkum SEMUA tahap yang tersedia tersebut, dan dilarang menyatakan tahap itu "
                "'tidak tersedia' atau 'tidak tercantum'."
            )

        return (
            f"Instruksi tambahan pertanyaan tabel: konteks memuat Tabel {table_no}. "
            f"Wajib jawab menggunakan isi Tabel {table_no} yang tersedia di konteks, sertakan sitasi [n], "
            "dan jangan menyatakan 'tidak ditemukan' untuk Tabel tersebut."
            f"{stage_instruction} "
            "Jika isi tabel yang tersedia benar-benar parsial, nyatakan jawaban berdasar bagian yang tersedia saja."
        )
```

Replace with:
```python
    def _build_table_guardrail(self, query: str, context: str) -> str:
        """Build dynamic instruction so table queries do not collapse to false negatives."""
        q = str(query or "")
        c = str(context or "")
        table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", q, re.IGNORECASE)
        if not table_match:
            return ""

        table_no = table_match.group(1)
        table_pattern = re.compile(
            rf"\b(?:tabel|table)\s*(?:ke[-\s]*)?{re.escape(table_no)}\b",
            re.IGNORECASE,
        )
        if not table_pattern.search(c):
            return ""

        return (
            f"Instruksi tambahan pertanyaan tabel: konteks memuat Tabel {table_no}. "
            f"Wajib jawab menggunakan isi Tabel {table_no} yang tersedia di konteks, sertakan sitasi [n], "
            "dan jangan menyatakan 'tidak ditemukan' untuk Tabel tersebut. "
            "Jika isi tabel yang tersedia benar-benar parsial, nyatakan jawaban berdasar bagian yang tersedia saja."
        )
```

- [ ] **Step 20: Run all tests**

```
cd backend && python -m pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 21: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "refactor(rag): remove hardcoded stage injection from _build_table_guardrail"
```

---

### Task 8: Write failing quality-scoring tests (for chat.py cleanup)

**Files:**
- Create: `backend/tests/test_quality_scoring.py`

- [ ] **Step 22: Create the test file**

```python
# backend/tests/test_quality_scoring.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


def test_quality_report_signature_has_no_required_stages_param():
    """After cleanup, _build_answer_quality_report must NOT accept required_stages."""
    import inspect
    from app.api.routes.chat import _build_answer_quality_report
    sig = inspect.signature(_build_answer_quality_report)
    assert "required_stages" not in sig.parameters


def test_quality_report_has_no_stage_fields():
    """Return dict must not contain deprecated stage fields."""
    from app.api.routes.chat import _build_answer_quality_report
    report = _build_answer_quality_report(
        query="apa isi tabel 13?",
        context="Tabel 13: data nilai 80 [1]",
        answer="Tabel 13 berisi nilai 80 [1].",
        source_count=1,
    )
    for deprecated_key in ("required_stages", "missing_stages", "stage_hits", "has_unavailable_stage_claim"):
        assert deprecated_key not in report, f"deprecated key still present: {deprecated_key}"


def test_quality_report_basic_score_runs():
    """Smoke test: function runs and returns a dict with required keys."""
    from app.api.routes.chat import _build_answer_quality_report
    report = _build_answer_quality_report(
        query="apa itu SPBE?",
        context="SPBE adalah sistem pemerintahan berbasis elektronik [1]",
        answer="SPBE adalah sistem pemerintahan berbasis elektronik [1].",
        source_count=1,
    )
    for key in ("score", "needs_retry", "retry_reasons", "focus_coverage"):
        assert key in report


def test_quality_rank_key_has_no_missing_stages_constraint():
    """_quality_rank_key tuple must not include missing_stages."""
    from app.api.routes.chat import _quality_rank_key
    # If missing_stages is gone, passing a report without it should not raise
    report = {
        "conflicting_unavailable_claim": False,
        "list_structure_ok": True,
        "score": 10,
        "focus_coverage": 0.8,
        "citation_count": 2,
        "answer_length": 300,
    }
    key = _quality_rank_key(report)
    assert isinstance(key, tuple)
    assert len(key) == 6  # 6 elements after removing missing_stages


def test_removed_functions_do_not_exist():
    """Confirm deprecated functions are removed from chat module."""
    import app.api.routes.chat as chat_module
    for fn_name in ("_extract_required_table_stages", "_count_stage_hits", "_has_unavailable_stage_claim"):
        assert not hasattr(chat_module, fn_name), f"deprecated function still exists: {fn_name}"


def test_table_stage_markers_constant_removed():
    """Confirm TABLE_STAGE_MARKERS constant is removed."""
    import app.api.routes.chat as chat_module
    assert not hasattr(chat_module, "TABLE_STAGE_MARKERS")
```

- [ ] **Step 23: Run to confirm they fail**

```
cd backend && python -m pytest tests/test_quality_scoring.py -v 2>&1 | head -40
```

Expected: FAIL — functions and constant still present.

---

### Task 9: Clean up chat.py — remove stage functions and scoring

**Files:**
- Modify: `backend/app/api/routes/chat.py`

- [ ] **Step 24: Remove `TABLE_STAGE_MARKERS` constant and 3 deprecated functions**

Find and delete this entire block (lines ~189–234):
```python
TABLE_STAGE_MARKERS = (
    "Tahap Persiapan",
    "Tahap Pelaksanaan",
    "Tahap Pelaporan",
)


def _extract_required_table_stages(context: str) -> List[str]:
    text = str(context or "").lower()
    required: List[str] = []
    for stage in TABLE_STAGE_MARKERS:
        if stage.lower() in text:
            required.append(stage)
    return required


def _count_stage_hits(answer: str, stages: List[str]) -> int:
    if not stages:
        return 0
    text = str(answer or "").lower()
    return sum(1 for stage in stages if stage.lower() in text)


def _has_unavailable_stage_claim(answer: str, stages: List[str]) -> bool:
    """Detect claims that table stages are unavailable/missing in the provided context."""
    if not stages:
        return False

    text = str(answer or "").lower()

    # Global disclaimer can be enough to consider answer quality low for table completeness.
    if _contains_unavailable_signal(text):
        for stage in stages:
            stage_l = stage.lower()
            pos = text.find(stage_l)
            if pos >= 0:
                start = max(0, pos - 180)
                end = min(len(text), pos + len(stage_l) + 180)
                window = text[start:end]
                if _contains_unavailable_signal(window):
                    return True

        # If negatives exist anywhere while required stages are known in context, treat as weak answer.
        return True

    return False
```

Delete the entire block. Replace with nothing (empty line).

- [ ] **Step 25: Remove stage parameters and scoring from `_build_answer_quality_report`**

Find the function signature:
```python
def _build_answer_quality_report(
    query: str,
    context: str,
    answer: str,
    source_count: int,
    required_stages: List[str],
) -> Dict[str, Any]:
```

Replace with:
```python
def _build_answer_quality_report(
    query: str,
    context: str,
    answer: str,
    source_count: int,
) -> Dict[str, Any]:
```

Inside the function body, find and remove these lines:
```python
    stage_hits = _count_stage_hits(answer_text, required_stages)
    missing_stages = [
        stage for stage in required_stages if stage.lower() not in answer_lower
    ]
    stage_ok = not missing_stages
    has_unavailable_stage_claim = _has_unavailable_stage_claim(answer_text, required_stages)
```

Find and remove the stage scoring block:
```python
    if required_stages:
        score += stage_hits * 3
        if not stage_ok:
            score -= 8
    if has_unavailable_stage_claim:
        score -= 6
```

Find and remove these retry_reasons lines:
```python
    if required_stages and not stage_ok:
        retry_reasons.append("tahap wajib belum lengkap")
    if has_unavailable_stage_claim:
        retry_reasons.append("klaim unavailable muncul pada tahap yang tersedia")
```

Find and remove these return dict keys:
```python
        "has_unavailable_stage_claim": has_unavailable_stage_claim,
        ...
        "required_stages": required_stages,
        "stage_hits": stage_hits,
        "missing_stages": missing_stages,
```

- [ ] **Step 26: Fix `_quality_rank_key` — remove `missing_stages` constraint**

Find:
```python
def _quality_rank_key(report: Dict[str, Any]):
    """Rank quality reports with hard constraints first, then score and coverage."""
    return (
        0 if not report.get("conflicting_unavailable_claim") else -1,
        0 if not report.get("missing_stages") else -1,
        0 if report.get("list_structure_ok", True) else -1,
        int(report.get("score", 0)),
        float(report.get("focus_coverage", 0.0)),
        int(report.get("citation_count", 0)),
        int(report.get("answer_length", 0)),
    )
```

Replace with:
```python
def _quality_rank_key(report: Dict[str, Any]):
    """Rank quality reports with hard constraints first, then score and coverage."""
    return (
        0 if not report.get("conflicting_unavailable_claim") else -1,
        0 if report.get("list_structure_ok", True) else -1,
        int(report.get("score", 0)),
        float(report.get("focus_coverage", 0.0)),
        int(report.get("citation_count", 0)),
        int(report.get("answer_length", 0)),
    )
```

- [ ] **Step 27: Fix `_build_retry_query` — remove `required_stages` parameter**

Find:
```python
def _build_retry_query(
    original_query: str,
    quality_report: Dict[str, Any],
    required_stages: List[str],
) -> str:
```

Replace with:
```python
def _build_retry_query(
    original_query: str,
    quality_report: Dict[str, Any],
) -> str:
```

Inside the function body, find and remove the `required_stages` block:
```python
    if required_stages:
        instructions.append(
            "- Untuk konteks tabel ini, wajib mencakup semua tahap yang tersedia: "
            + ", ".join(required_stages)
            + "."
        )
```

- [ ] **Step 28: Fix callers in `chat_stream` — remove `required_stages` everywhere**

In the `event_generator()` function, find and remove:
```python
            required_stages = (
                _extract_required_table_stages(context)
                if classify_query(request.message) == "table"
                else []
            )
```

Update all `_build_answer_quality_report` calls (there are 2) — remove `required_stages=required_stages`:

First call:
```python
            first_quality = _build_answer_quality_report(
                query=request.message,
                context=context,
                answer=first_response,
                source_count=len(sources_for_response),
                required_stages=required_stages,
            )
```
→
```python
            first_quality = _build_answer_quality_report(
                query=request.message,
                context=context,
                answer=first_response,
                source_count=len(sources_for_response),
            )
```

Second call (inside the retry loop):
```python
                retry_quality = _build_answer_quality_report(
                    query=request.message,
                    context=context,
                    answer=retry_response,
                    source_count=len(sources_for_response),
                    required_stages=required_stages,
                )
```
→
```python
                retry_quality = _build_answer_quality_report(
                    query=request.message,
                    context=context,
                    answer=retry_response,
                    source_count=len(sources_for_response),
                )
```

Update `_build_retry_query` call — remove `required_stages`:
```python
                retry_query = _build_retry_query(
                    original_query=request.message,
                    quality_report=current_best_quality,
                    required_stages=required_stages,
                )
```
→
```python
                retry_query = _build_retry_query(
                    original_query=request.message,
                    quality_report=current_best_quality,
                )
```

Also fix the `quality_payload` dict — remove `"missing_stages"` key:
```python
            quality_payload = {
                "score": selected_quality.get("score"),
                "needs_retry": selected_quality.get("needs_retry"),
                "retry_reasons": selected_quality.get("retry_reasons"),
                "focus_coverage": selected_quality.get("focus_coverage"),
                "has_unavailable_claim": selected_quality.get("has_unavailable_claim"),
                "missing_stages": selected_quality.get("missing_stages"),
                "unavailable_triggers_active": selected_quality.get(
                    "unavailable_triggers_active", []
                ),
            }
```
→
```python
            quality_payload = {
                "score": selected_quality.get("score"),
                "needs_retry": selected_quality.get("needs_retry"),
                "retry_reasons": selected_quality.get("retry_reasons"),
                "focus_coverage": selected_quality.get("focus_coverage"),
                "has_unavailable_claim": selected_quality.get("has_unavailable_claim"),
                "unavailable_triggers_active": selected_quality.get(
                    "unavailable_triggers_active", []
                ),
            }
```

- [ ] **Step 29: Run all tests**

```
cd backend && python -m pytest tests/ -v
```

Expected: all tests PASS including `test_quality_scoring.py`.

- [ ] **Step 30: Final commit**

```bash
git add backend/app/api/routes/chat.py
git commit -m "refactor(chat): remove TABLE_STAGE_MARKERS and hardcoded stage quality scoring"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Remove `_table_literal_search` stage_markers | Task 3 |
| Remove `_is_table_index_noise_doc` stage_markers | Task 4 |
| Remove hybrid retrieval stage boost | Task 5 |
| Replace `_table_stage_coverage_score` | Task 2 (new methods) + Task 6 |
| Replace hardcoded retry strings | Task 6 |
| Remove `_build_table_guardrail` stage injection | Task 7 |
| Remove `TABLE_STAGE_MARKERS` + 3 functions from chat.py | Task 9, Step 24 |
| Remove stage scoring from quality report | Task 9, Step 25 |
| Remove `missing_stages` from `_quality_rank_key` | Task 9, Step 26 |
| Remove `required_stages` from `_build_retry_query` | Task 9, Step 27 |
| Remove callers (`required_stages=...`) in chat_stream | Task 9, Step 28 |

**Placeholder scan:** None found.

**Type consistency:**
- `_extract_table_anchors` returns `List[str]` — used as `List[str]` in Task 6 ✓
- `_table_anchor_coverage_score(docs, anchors)` signature — used with same arg order in Task 6 ✓
- `_build_answer_quality_report` loses `required_stages` param — all callers updated in Task 9 ✓
- `_build_retry_query` loses `required_stages` param — caller updated in Task 9 ✓
- `_quality_rank_key` tuple shrinks from 7 to 6 elements — test asserts `len == 6` ✓
