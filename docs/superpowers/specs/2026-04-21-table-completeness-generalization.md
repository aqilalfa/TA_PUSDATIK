# Table Completeness Generalization — Design Spec
**Date:** 2026-04-21
**Project:** SPBE RAG System (BSSN)
**Scope:** Hapus bias hardcoded "tahap persiapan/pelaksanaan/pelaporan" → ganti dengan anchor detection dinamis

---

## 1. Masalah

Ada 7 tempat di kode yang hardcode frasa `"tahap persiapan"`, `"tahap pelaksanaan"`, `"tahap pelaporan"` sebagai sinyal "completeness" tabel. Kode ini dibuat untuk satu tabel spesifik (kemungkinan Tabel 13 "Perbandingan Pemantauan & Evaluasi SPBE"), tapi diterapkan ke SEMUA query tabel.

**Akibat untuk tabel lain (misal tabel domain SPBE):**
- Retrieval di-bias ke chunk berisi frasa tahap, meskipun tidak relevan
- Retry query menyuntik string `"tahap persiapan tahap pelaksanaan tahap pelaporan"` ke semua tabel
- LLM diberi instruksi "rangkum semua tahap" padahal tabel tidak punya struktur tahap
- Quality scoring menghukum jawaban yang tidak menyebut 3 tahap

---

## 2. Pendekatan: Generic Anchor Detection

Ganti hardcode dengan deteksi **anchor dinamis** dari chunk tabel yang sudah diretrieve.

### Flow Baru

```
Initial retrieval → docs
    ↓
_extract_table_anchors(docs, table_no)
    → scan text dari chunk yang table_label="Tabel N"
    → ambil frasa yang muncul di ≥2 chunk (structural header/baris nyata)
    → max 5 anchor
    ↓
_table_anchor_coverage_score(docs, anchors) → int (0 = no anchors defined = OK)
    → coverage < 50% dari anchors? → trigger retry
    ↓
Retry query: tambah anchor yang belum muncul sebagai keyword tambahan
    ↓
_build_table_guardrail → pakai anchor nyata, bukan hardcode tahap
    ↓
chat.py quality: hapus semua stage-specific scoring
```

---

## 3. File yang Dimodifikasi

### 3.1 `backend/app/core/rag/langchain_engine.py`

**Hapus semua hardcode stage_markers di:**
- `_table_literal_search` (line ~313–333): hapus `stage_markers` tuple + `stage_hits` scoring
- `_is_table_index_noise_doc` (line ~447–452): hapus `has_stage_content` check dari stage_markers
- Hybrid retrieval boost (line ~1082–1089): hapus stage_markers + stage_hits boost
- `retrieve_context` retry (line ~1246): ganti string hardcode dengan anchor dinamis

**Tambah fungsi baru:**

```python
@staticmethod
def _extract_table_anchors(docs: List[Document], table_no: str, min_hits: int = 2, max_anchors: int = 5) -> List[str]:
    """
    Extract recurring structural phrases from retrieved table chunks.
    A phrase found in ≥ min_hits chunks is likely a real header/row anchor.
    """
    from collections import Counter
    import re

    target_label = f"tabel {table_no}".lower()
    table_chunks = [
        d for d in docs
        if target_label in (d.page_content or "").lower()
        or str(d.metadata.get("table_label", "")).lower() == target_label
    ]
    if not table_chunks:
        return []

    phrase_counter: Counter = Counter()
    phrase_pattern = re.compile(r"[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F\s]{4,39}[A-Za-z\u00C0-\u024F]")

    for doc in table_chunks:
        preview = (doc.page_content or "")[:400]
        found = {m.group().strip().lower() for m in phrase_pattern.finditer(preview)}
        for phrase in found:
            phrase_counter[phrase] += 1

    anchors = [
        phrase for phrase, count in phrase_counter.most_common(20)
        if count >= min_hits and len(phrase.split()) >= 2
    ]
    return anchors[:max_anchors]


def _table_anchor_coverage_score(self, docs: List[Document], anchors: List[str]) -> int:
    """
    Count how many anchors appear in combined docs text.
    Returns 0 if no anchors (treat as complete — no data to penalize).
    """
    if not anchors:
        return 0
    blob = "\n".join((doc.page_content or "") for doc in docs).lower()
    return sum(1 for anchor in anchors if anchor in blob)
```

**Ubah `_table_stage_coverage_score` → ganti dengan `_table_anchor_coverage_score`** di `retrieve_context`:

```python
# sebelum
base_coverage = self._table_stage_coverage_score(docs)
if base_coverage < 3:
    ...append "tahap persiapan tahap pelaksanaan tahap pelaporan"...

# sesudah
table_match_for_anchor = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", query, re.IGNORECASE)
table_no_for_anchor = table_match_for_anchor.group(1) if table_match_for_anchor else ""
anchors = self._extract_table_anchors(docs, table_no_for_anchor)
anchor_coverage = self._table_anchor_coverage_score(docs, anchors)
anchor_threshold = max(1, len(anchors) // 2)  # 50% anchors harus muncul

if anchors and anchor_coverage < anchor_threshold:
    missing_anchors = [a for a in anchors if a not in blob_check]
    retry_anchor_str = " ".join(missing_anchors[:3])
    self._append_unique_search_query(retry_queries, f"{query} {retry_anchor_str}")
    ...run retry...
```

**Ubah `_build_table_guardrail`:** hapus stage detection, ganti dengan anchor list jika ada.

### 3.2 `backend/app/api/routes/chat.py`

**Hapus:**
- `TABLE_STAGE_MARKERS` constant
- `_extract_required_table_stages(context)` function
- `_has_unavailable_stage_claim(answer, stages)` function
- Stage-based scoring di `_build_answer_quality_report`: `required_stages`, `stage_hits`, `missing_stages`, `has_unavailable_stage_claim`, `stage_ok`
- Stage-related `retry_reasons` dan score modifiers
- `required_stages` parameter dari semua callers

**Pertahankan semua sinyal quality lain:** focus coverage, citations, list structure, unavailable claims.

---

## 4. Yang Tidak Berubah

- Table-number regex matching di `_table_literal_search`
- `is_table` / `table_label` metadata boost
- `_is_table_index_noise_doc` — hanya hapus stage_markers dari kondisi noise
- RRF fusion, reranker
- `validate_answer`, `sanitize_citations`
- Semua logika non-table

---

## 5. Testing Manual

| Query | Perilaku yang Diharapkan |
|---|---|
| "apa isi tabel 13?" | Retrieval tidak di-inject frasa tahap; jawaban sesuai struktur Tabel 13 |
| "apa isi tabel domain spbe?" | Tidak ada instruksi "rangkum tahap"; anchor diambil dari tabel domain |
| "tabel yang tidak punya 3 tahap" | Tidak ada retry dengan "tahap persiapan"; tidak ada penalti quality score |
| Query non-tabel | Tidak ada perubahan perilaku |

---

## 6. Risiko

| Risiko | Mitigasi |
|---|---|
| Tabel 13 regresi (dulu dijawab benar) | Anchor detection akan menemukan frasa struktural Tabel 13 jika chunk cukup spesifik; test manual wajib |
| Anchor extraction menangkap frasa noise | Cap max_anchors=5, min_hits=2, panjang frasa min 2 kata |
| Tidak ada anchor ditemukan | Fallback: `anchor_coverage=0`, tidak ada retry → lebih baik dari bias salah |
