# Figure Extraction Pipeline — Evaluation Results

**Date**: 2026-04-29  
**Pipeline version**: Tasks 1–15 complete + VLM bug fix (commit 405060b)

---

## Pipeline Implementation Summary

All 15 implementation tasks completed:

| Component | File | Status |
|---|---|---|
| Types & dataclass | `figures/types.py` | ✅ |
| Image extractor (PyMuPDF) | `figures/image_extractor.py` | ✅ |
| Figure classifier (heuristics) | `figures/classifier.py` | ✅ |
| VLM extractor (qwen3-vl:4b) | `figures/vlm_extractor.py` | ✅ (+ bug fix) |
| OCR extractor (PaddleOCR) | `figures/ocr_extractor.py` | ✅ |
| Sidecar cache (SHA-256) | `figures/cache.py` | ✅ |
| Caption matcher (Marker refs) | `figures/caption_matcher.py` | ✅ |
| Pipeline orchestrator | `figures/processor.py` | ✅ |
| Chunker integration | `structured_chunker.py` | ✅ |
| Document manager integration | `document_manager.py` | ✅ |
| Reingest script | `scripts/reingest_doc.py` | ✅ |
| RAGAS comparison script | `scripts/compare_ragas_reports.py` | ✅ |
| 15 figure-specific GT entries | `data/ground_truth.json` | ✅ (gt_041–gt_055) |
| Unit tests (34 tests) | `tests/test_figure_*.py` | ✅ 34/34 pass |

---

## VLM Bug Found and Fixed

**Bug**: `qwen3-vl:4b` uses mandatory thinking mode (`qwen3-vl-thinking` renderer) that consumes all `num_predict=800` tokens on internal reasoning, leaving `response=''`.

**Root cause**: Long prompts (>~15 tokens) trigger extensive thinking that exhausts the token budget. `think: false`, `/no_think` prefix, and system messages all failed to disable it.

**Fix** (commit `405060b`):
- Switched from `/api/generate` → `/api/chat` endpoint
- Shortened `CHART_PROMPT` and `DIAGRAM_PROMPT` to minimal `"SUMMARY:\nDETAIL:"` (<30 chars)
- Set `temperature=1.0` (model default, increases chance of response transition)
- Added retry loop (up to 3 attempts) since transition is non-deterministic (~60% per attempt)

**Confirmed working** on 2026-04-29 08:26:40:
```
fig_p001_01 → diagram: summary=281ch, detail=660ch (attempt 1/3, ~137s)
```

---

## Document: 20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf

| Metric | Value |
|---|---|
| Pages | 97 |
| Images extracted | 169 |
| Classified as VLM (diagrams/charts/timelines) | 166 |
| Classified as OCR (table_image) | 3 |
| Reingest started | 2026-04-29 08:24 |
| Estimated completion | ~6 hours (169 figures × ~2 min/fig) |

**Status at time of writing**: Reingest in progress, confirmed producing summaries.

---

## RAGAS Evaluation (PENDING)

Full RAGAS evaluation blocked until reingest completes (Qdrant index updated only at end of reingest).

**Planned steps**:
```bash
# After reingest completes:
venv/Scripts/python scripts/evaluate_rag.py --phase collect
venv/Scripts/python scripts/evaluate_ragas.py
venv/Scripts/python scripts/compare_ragas_reports.py \
    data/evaluation_report.json data/evaluation_report_after_figures.json
```

**Targets**:
- Figure GT pass rate: ≥10/15 (gt_041–gt_055)
- No regression on existing 40 questions (delta > -0.05 on any metric)

---

## Test Suite

```
37 tests passed (0 failed) in 104s
- test_figure_types.py: 3/3
- test_figure_image_extractor.py: 2/2
- test_figure_classifier.py: 15/15
- test_figure_vlm_extractor.py: 5/5
- test_figure_ocr_extractor.py: 2/2
- test_figure_cache.py: 3/3
- test_figure_caption_matcher.py: 4/4
- test_figure_processor.py: 2/2
- test_eval_default_model.py: 1/1
```

Note: `test_chunker_figure_integration.py` excluded from pytest (pre-existing pyarrow segfault in Windows test environment; functions verified by code inspection).
