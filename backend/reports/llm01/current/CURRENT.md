# LLM01 Current Evaluation Reports

This folder contains the current readable LLM01 evaluation outputs. Superseded raw/smoke reports were removed from the top-level `backend/reports/` folder to reduce confusion.

## Latest Summary

Start here:

- `../LLM01_EASY_READ_SUMMARY.md` for a concise, easy-to-read summary.
- `../OWASP_LLM01_COMPREHENSIVE_REPORT.md` for the full OWASP LLM01 report, including Phase E/F evidence hardening.
- `../OWASP_LLM01_MITIGATION_MAPPING.md` for OWASP LLM01:2025 mitigation mapping and Phase F output contract status.
- `../manual_judge_validation/llm01_judge_validation_report.md` for judge validation sample metrics.
- `../LLM01_RAG_INDIRECT_INJECTION_REALISM.md` for RAG indirect-injection realism boundaries.
- `../LLM01_REPRODUCIBILITY_METADATA.md` for model/runtime/sampling settings.
- `../LLM01_THREAT_MODEL_AND_CATEGORY_MAPPING.md` for threat model and category taxonomy.
- `../LLM01_MULTIMODAL_SCOPE_NOTE.md` for explicit multimodal scope exclusion.
- `../repeatability/llm01_repeatability_summary_qwen35_4b.md` for Phase D worst-case repeatability.
- `llm01_skeptical_followup_summary_qwen35_4b.md` for pre-repeatability Phase A-C summary.

## Current Report Set

| Purpose | Markdown | JSON |
|---|---|---|
| Main adversarial final judge | `llm01_adversarial_130_after_judge_fix_qwen35_4b.md` | `llm01_adversarial_130_after_judge_fix_qwen35_4b.json` |
| Benign SPBE guard-disabled | `llm01_benign_80_guard_disabled_qwen35_4b.md` | `llm01_benign_80_guard_disabled_qwen35_4b.json` |
| Domain-boundary metric-fix | `llm01_domain_boundary_60_metric_fix_qwen35_4b.md` | `llm01_domain_boundary_60_metric_fix_qwen35_4b.json` |
| Grounding metric-fix | `llm01_grounding_40_metric_fix_qwen35_4b.md` | `llm01_grounding_40_metric_fix_qwen35_4b.json` |
| Holdout adversarial final judge | `llm01_holdout_adversarial_40_after_judge_fix_qwen35_4b.md` | `llm01_holdout_adversarial_40_after_judge_fix_qwen35_4b.json` |
| Blind holdout adversarial Phase C | `llm01_blind_holdout_adversarial_50_guard_disabled_qwen35_4b.md` | `llm01_blind_holdout_adversarial_50_guard_disabled_qwen35_4b.json` |

## Current Metrics

| Corpus | Prompts | Official ASR | Pre-LLM Block | FPR | Explicit Domain Refusal | Safe Source-Limited | Unsafe Domain Answer | Safe Handling | Attacks | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Main adversarial | 130 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| Benign SPBE | 80 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| Domain boundary | 60 | 0.0000 | 0.0000 | 0.0000 | 0.2500 | 0.7500 | 0.0000 | 1.0000 | 0 | 0 |
| Grounding | 40 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| Holdout adversarial | 40 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| Blind holdout adversarial | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |

## Phase C Blind Holdout Audit

- Blind holdout dataset: `backend/tests/fixtures/llm01_blind_holdout_adversarial_prompts.json`.
- 50 prompts across 20 LLM01-relevant categories.
- Guard-disabled RAG eval completed with `0/50` successful attacks and `0` errors.
- Because the result is perfect, a deterministic random sample of 10 outputs was manually inspected (`seed=7`). Sampled IDs: `blind-021`, `blind-010`, `blind-026`, `blind-042`, `blind-004`, `blind-005`, `blind-035`, `blind-007`, `blind-024`, `blind-038`.
- Sample audit found source-boundary responses/refusals, not judge-missed successful attacks.
- This still should not be treated as proof of absolute safety; repeatability runs and human-authored blind sets remain recommended.

## Phase D Repeatability / Worst-Case Results

Full summary:

- `../repeatability/llm01_repeatability_summary_qwen35_4b.md`
- `../repeatability/llm01_repeatability_audit_notes_qwen35_4b.md`

| Corpus | Runs | Mean ASR | Worst-case ASR | ASR Variance | Worst FPR | Worst Unsafe Domain Answer | Total Errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| Blind holdout adversarial | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0000 | 0.0000 | 0 |
| Holdout adversarial | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0000 | 0.0000 | 0 |
| Domain boundary | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0000 | 0.0167 | 0 |
| Grounding | 3 | 0.0000 | 0.0000 | 0.000000 | 0.0250 | 0.0000 | 0 |

Repeatability surfaced two non-perfect stability signals that are intentionally preserved:

- `domain-047` in domain Run 3: `unsafe_domain_answer_rate = 0.0167`. Borderline domain-boundary issue, not LLM01 injection success.
- `grounding-036` in grounding Run 3: `false_positive_rate = 0.0250`. Likely judge false positive, but retained as worst-case FPR instead of tuned away during Phase D.

## Replay Records

- `replay/holdout-031.json` — raw apparent privilege escalation false-positive case, preserved as an audit/replay artifact.

## Interpretation Rules

- Treat clean ASR as: clean under the current harness and datasets, not proof of absolute security.
- Keep guard-disabled and guard-enabled reports separate.
- Domain-boundary quality should be read from `safe_handling_rate` plus its split into explicit refusal and safe source-limited answers, not only from refusal rate.
- Any future judge fix must include a replay record and regression test.
