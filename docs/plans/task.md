# Task Tracker: Peningkatan Answer Relevancy

**Goal:** AR 0.6672 → ≥ 0.75 | **Safety:** CR/CP/Faithfulness tidak boleh turun  
**Baseline:** CP=0.8453 | CR=0.9500 | Faith=0.8116 | AR=0.6672

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Update `build_answer_style_instructions()` — hard-stop per tipe | `[x]` | ✅ |
| 2 | Update `shared_rules` — anti-disclaimer rules | `[x]` | ✅ |
| 3 | Buat `_FEW_SHOT_BY_TYPE` dict + inject ke `build_answer_style_instructions()` | `[x]` | ✅ |
| 4 | Update `SYSTEM_PROMPT_SPBE` — tambah anti-verbose constraint (rule 13 & 14) | `[x]` | ✅ |
| 5 | Buat `answer_trimmer.py` — disclaimer detector + type-aware trim | `[x]` | ✅ Faithfulness-safe |
| 6 | Update `expand_query()` — tambah anchor GT-021 | `[x]` | ✅ |
| 7 | Integrasi trimmer ke `evaluate_rag.py` | `[x]` | ✅ answer_raw tersimpan untuk debug |
| 8 | Unit test `test_answer_trimmer.py` — 24 tests | `[x]` | ✅ 24/24 PASSED |
| 9 | Collect ulang 12 ID AR terendah | `[ ]` | Perlu Ollama running |
| 10 | RAGAS on subset + bandingkan semua 4 metrik | `[ ]` | Gate: tidak ada degradasi |

