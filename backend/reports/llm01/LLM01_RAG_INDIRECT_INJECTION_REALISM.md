# LLM01 RAG Indirect Injection Realism Note

## Question

Does the LLM01 indirect/retrieval injection evaluation use true poisoned-document ingestion through the full Qdrant pipeline, or prompt-level simulation?

## Current Answer

Current adversarial datasets include indirect/retrieval-injection categories, but they primarily test prompt-level and retrieved-context behavior rather than a full poisoned-document ingestion pipeline.

The system **does** implement RAG-specific segregation controls:

- `backend/app/core/rag/guardrails.py::build_llm01_security_instruction()` marks user questions, chat history, and retrieval context as data, not higher-priority instructions.
- `backend/app/core/rag/guardrails.py::sanitize_untrusted_context()` wraps retrieved content in explicit untrusted markers:
  - `BEGIN UNTRUSTED RETRIEVED CONTENT`
  - `END UNTRUSTED RETRIEVED CONTENT`
- `backend/app/core/rag/engine/llm_client.py` calls `sanitize_untrusted_context(context)` before sending context to the LLM.

## Added Verification

Test file:

- `backend/tests/test_llm01_rag_indirect_injection.py`

Tests added:

1. `test_sanitize_untrusted_context_marks_retrieved_content_as_untrusted`
2. `test_llm01_security_instruction_segregates_retrieval_context_from_instructions`

These tests verify that retrieved content is explicitly labeled as untrusted and that system instructions forbid following instructions embedded in retrieval context.

## Limitation

This is not yet a full poisoned-document ingestion test. A stronger future test should:

1. create a malicious fixture document,
2. ingest it through the real document/chunking/embedding/Qdrant pipeline in an isolated test collection,
3. issue a normal user query that retrieves the poisoned chunk,
4. assert the model refuses or ignores the embedded malicious instruction.

## Claim Boundary

Current evidence supports the claim:

> The system segregates retrieved content as untrusted at prompt-construction time and tests indirect/retrieval-injection behavior at the harness level.

Current evidence does **not** yet support the stronger claim:

> The system has passed a full end-to-end poisoned-document ingestion attack through Qdrant.
