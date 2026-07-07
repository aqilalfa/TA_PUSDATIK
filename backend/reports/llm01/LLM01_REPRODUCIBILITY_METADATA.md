# LLM01 Reproducibility Metadata

## Runtime

- Eval target: local Docker backend (`spbe-backend`).
- LLM endpoint: Ollama `/api/chat` via `settings.OLLAMA_BASE_URL`.
- Eval model: `qwen3.5:4b`.
- Eval mode: guard-disabled, RAG enabled.
- Retrieval: `top_k=5`.
- Eval role: `evaluator_spbe`.
- Per-prompt timeout: `180` seconds.
- Inter-prompt delay: `0` seconds.

## LLM Sampling Options

From `backend/app/core/rag/engine/llm_client.py`:

```python
options = {
    "temperature": 0.1,
    "num_predict": 1024,
    "num_ctx": 8192,
}
extra_params["think"] = False  # for qwen3/qwen3.5/r1 family
```

Implication:

- The eval is low-temperature but not strictly deterministic greedy decoding.
- Phase D repeatability is therefore important and was used to report worst-case ASR rather than a single best run.

## Ollama Model Metadata

From Ollama `/api/tags`:

```json
{
  "name": "qwen3.5:4b",
  "model": "qwen3.5:4b",
  "modified_at": "2026-03-10T21:54:22.0406201+07:00",
  "size": 3389983735,
  "digest": "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd",
  "details": {
    "format": "gguf",
    "family": "qwen35",
    "parameter_size": "4.7B",
    "quantization_level": "Q4_K_M",
    "context_length": 262144,
    "embedding_length": 2560
  }
}
```

## Reproducibility Caveats

- No explicit random seed is passed to Ollama in the current LLM client.
- Temperature is `0.1`, so output may vary slightly between runs.
- Repeatability Phase D addresses this by using three runs and reporting worst-case metrics.
- If stricter determinism is required, add an Ollama-supported seed option and/or set temperature to `0` for a separate deterministic benchmark profile.
