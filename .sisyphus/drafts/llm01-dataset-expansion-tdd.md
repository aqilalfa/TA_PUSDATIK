# Draft: LLM01 Dataset Expansion TDD

## Requirements (confirmed)
- User wants a plan to expand LLM01 datasets beyond the current 36 adversarial prompts.
- User specifically asked to include testing and a TDD approach.
- Current baseline: expanded adversarial dataset has 36 prompts, full guard-disabled RAG ASR after judge fix is 0% with pre-LLM block rate 0% and errors 0.
- Target recommendation discussed: adversarial dataset should grow to approximately 120 prompts; benign/domain/grounding datasets should also grow so ASR is not optimized at the cost of false positives or domain-boundary failures.

## Technical Decisions
- Planning target: one consolidated work plan at `.sisyphus/plans/llm01-dataset-expansion-tdd.md`.
- Keep pre-LLM blocker unchanged unless a later explicit requirement says otherwise; this phase measures guard-disabled LLM/RAG behavior.
- Use TDD: first write schema/count/category/metric tests that fail against current fixtures, then expand datasets and evaluator/reporting support.
- Use full guard-disabled ASR as final verification, plus benign/domain/grounding eval for FPR and refusal/grounding metrics.

## Research Findings
- Existing relevant files:
  - `backend/tests/fixtures/llm01_adversarial_prompts.json`
  - `backend/tests/fixtures/llm01_benign_prompts.json`
  - `backend/tests/fixtures/llm01_domain_boundary_prompts.json`
  - `backend/tests/fixtures/llm01_grounding_prompts.json`
  - `backend/scripts/llm01_redteam_eval.py`
  - `backend/tests/test_llm01_redteam_eval.py`
  - `backend/tests/test_llm01_prompt_injection.py`
  - `promptfoo/provider-spbe.js`
  - `promptfoo/summarize-results.js`
- Existing successful final report:
  - `backend/reports/llm01_expanded_adversarial_full_after_judge_fix_qwen35_4b.md`

## Open Questions
- None blocking. Defaults can be applied for exact category counts.

## Scope Boundaries
- INCLUDE: dataset expansion, TDD tests, evaluator/reporting improvements only as needed, full rerun and report generation.
- INCLUDE: adversarial prompt count target around 120, benign around 80, domain-boundary around 60, grounding around 40.
- EXCLUDE: production pre-LLM blocker hardening unless final ASR shows true attacks and user explicitly asks to harden.
- EXCLUDE: changing model, RAG engine architecture, retrieval ranking, or application UI.
