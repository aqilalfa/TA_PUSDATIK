# Context Integrity Design

## Scope

Add a post-rerank context-integrity layer without replacing Qdrant, BM25,
literal retrieval, RRF, the embedding model, the reranker, the generator,
LLM01 controls, LLM09 controls, or role-based access control.

## Existing call graph

`chat_stream` in `app/api/routes/chat.py` calls
`LangchainRAGEngine.retrieve_context`, which currently executes:

1. query classification and expansion;
2. permission-filtered Qdrant, BM25, and literal retrieval;
3. RRF fusion;
4. legacy neighbor stitching;
5. reranking;
6. context and source construction;
7. prompt/LLM streaming and existing answer/citation validation.

## Selected architecture

Use two explicit orchestration paths.

- **Feature off:** retain the existing stitch-before-rerank sequence exactly.
- **Shadow:** return the feature-off result, while independently processing the
  reranked seed candidates and recording sanitized comparison metrics.
- **Feature on:** rerank authorized seed chunks first, then pass them to
  `ContextIntegrityService`, which segments units, loads authorized neighbors,
  scores local consistency and anomaly risk, expands safe spans, and selects
  final spans within the token budget.

This preserves a valid E0 baseline and places active context-integrity
processing after reranking as required.

## Components

The package `app/core/rag/context_integrity/` contains:

- immutable domain models and result objects;
- context-aware configuration derived from application settings;
- structure-preserving unit segmentation;
- permission- and boundary-aware neighbor loading;
- persistent, versioned unit embedding and score cache;
- cosine consistency and robust median/MAD anomaly estimation;
- secure span expansion and score breakdown;
- score-per-token final selection;
- sanitized audit emission through `RagTrace`;
- the orchestration service.

## Security invariants

1. Every seed and neighbor is rechecked with the existing metadata access
   predicate before it can affect scores, spans, logs, context, or sources.
2. Empty/unknown roles remain fail-closed.
3. Neighbor queries stay inside one document and, by default, one section or
   article and one compatible structure type/classification.
4. `allowed_roles`, `classification`, document identity, source hash, and
   citation identity are never widened or rewritten.
5. Audit records contain identifiers, hashes, numeric scores, reasons, and
   latency only; retrieved text is never logged.
6. Evaluation poison labels remain outside runtime storage and code paths.

## Storage and invalidation

Use two SQLAlchemy-backed SQLite tables in the existing database. Cache keys
include document/source hash, chunk identity, unit index, text hash, embedding
model identity, and scoring version. Changed text/model/version causes a cache
miss. Document deletion and re-indexing invalidate entries by document ID.

## Failure behavior

- Technical processing failure: return the already-authorized reranked seed
  result and record a sanitized technical fallback.
- No safe/authorized context: return an empty final context so the existing
  LLM09 insufficient-context response is used.
- Feature off: no cache, scoring, neighbor, or ordering side effect.

## Compatibility

Final spans are returned as LangChain `Document` objects. Their metadata keeps
the seed source/citation identity and adds only namespaced score breakdown and
member-unit identifiers. Existing context formatting and source construction
therefore remain the sole final adapters.

## Limitations

Local semantic consistency is an experimental risk-reduction heuristic, not a
truth oracle or an authorization boundary. Legitimate abrupt transitions can
be penalized, coordinated poisoning can evade local statistics, and thresholds
must be calibrated on development data then frozen before holdout evaluation.
