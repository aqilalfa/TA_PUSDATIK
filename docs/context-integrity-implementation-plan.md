# Context Integrity Implementation Plan

**Goal:** Add reproducible, permission-safe post-rerank context integrity while
preserving byte-for-byte orchestration behavior when the feature is disabled.

**Architecture:** A dual-path integration keeps the existing final pipeline as
E0 and uses an isolated service for shadow/active processing. New behavior is
test-driven and returns the existing LangChain `Document` contract.

**Tech stack:** Python, FastAPI, LangChain documents, Qdrant client, NumPy,
SciPy, SQLAlchemy/SQLite, pytest, existing RAGAS tooling.

## Task 1: Configuration and domain contracts

- Add all PRD environment settings with production default off and validation.
- Add immutable unit/span/result types and mode-specific resolved settings.
- Write configuration and contract tests first.

## Task 2: Segmentation and authorized neighbors

- Test ayat, sentence/paragraph, table-row, heading, and short-boilerplate rules.
- Test document, role, classification, section/article, and structure boundaries.
- Implement segmentation and a Qdrant loader that reuses existing access checks.

## Task 3: Embedding cache and robust scoring

- Add SQLAlchemy cache models and migration/bootstrap support.
- Test cache hit, text/model invalidation, and document invalidation.
- Test normalized cosine, left/right aggregation, median/MAD, small groups,
  zero MAD, and score audit fields.

## Task 4: Span building and final selection

- Test hard-risk exclusion, structural ordering, deduplication, maximum span
  units/tokens, score breakdown, risk aggregation, and score-per-token budget.
- Implement safe expansion and deterministic selection.

## Task 5: Service and pipeline integration

- Test process success, empty-safe result, technical fallback, sanitized audit,
  shadow non-interference, active post-rerank ordering, and feature-off parity.
- Initialize the service with existing embedding/Qdrant dependencies.
- Build sources only from final selected documents.

## Task 6: Evaluation and operations

- Add isolated synthetic poisoning fixtures and deterministic E0-E4 runner.
- Export absolute counts, percentages, scenario breakdown, run configuration,
  code/config/dataset hashes, latency, and JSON/CSV reports.
- Add cache invalidation to document deletion and re-indexing.
- Document configuration, commands, rollout, rollback, and limitations.

## Task 7: Verification

- Run focused RED/GREEN tests after each component.
- Run all backend tests and diagnostics.
- Run offline E0-E4 fixture evaluation and available profiling.
- Review access-control, source/citation, streaming, and logging regressions.
