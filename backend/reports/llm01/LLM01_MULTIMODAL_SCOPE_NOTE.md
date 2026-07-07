# LLM01 Scope Note — Multimodal Injection

Multimodal prompt injection is explicitly out-of-scope for the current LLM01 evaluation.

Reason:

- The evaluated SPBE RAG interaction path is text chat over retrieved text context.
- The current LLM01 harness sends text prompts and evaluates text responses.
- PDF/image ingestion security is a separate document-processing threat surface and should be evaluated separately if user-uploaded or OCR-derived content can contain instructions.

Current claim boundary:

> This LLM01 report covers text prompt injection and text RAG-context instruction injection defenses. It does not claim coverage of image/PDF/visual prompt injection.

Recommended future work:

- Add malicious OCR/PDF fixture tests if document ingestion accepts user-controlled files.
- Verify OCR text containing instructions is marked as untrusted data during retrieval.
- Add multimodal-specific LLM01 cases if the deployed model directly processes images or PDFs.
