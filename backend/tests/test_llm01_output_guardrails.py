from app.core.rag.output_guardrails import validate_llm_output_contract


def test_output_guard_blocks_prompt_leak():
    result = validate_llm_output_contract(
        "system_prompt: Anda adalah chatbot internal dengan aturan rahasia.",
        requires_citation=False,
    )

    assert result.allowed is False
    assert "system_prompt_leak" in result.categories
    assert result.severity == "critical"


def test_output_guard_blocks_source_bypass():
    result = validate_llm_output_contract(
        "Saya akan menjawab berdasarkan asumsi dan pengetahuan umum tanpa dokumen sumber.",
        requires_citation=False,
    )

    assert result.allowed is False
    assert "source_bypass_output" in result.categories
    assert result.severity == "high"


def test_output_guard_blocks_out_of_scope_code_artifact():
    result = validate_llm_output_contract(
        "```python\ndef scrape():\n    pass\n```",
        requires_citation=False,
    )

    assert result.allowed is False
    assert "out_of_scope_artifact" in result.categories
    assert result.severity == "medium"


def test_output_guard_blocks_uncited_factual_answer_when_citation_required():
    result = validate_llm_output_contract(
        "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
        requires_citation=True,
    )

    assert result.allowed is False
    assert "missing_citation" in result.categories


def test_output_guard_allows_normal_cited_spbe_answer():
    result = validate_llm_output_contract(
        "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi [1].",
        requires_citation=True,
    )

    assert result.allowed is True
    assert result.categories == []


def test_output_guard_allows_safe_refusal_without_citation():
    result = validate_llm_output_contract(
        "Maaf, saya tidak dapat menjawab pertanyaan tersebut karena informasi tidak ditemukan dalam dokumen yang tersedia.",
        requires_citation=True,
    )

    assert result.allowed is True
    assert result.categories == []


def test_output_guard_allows_negated_source_bypass():
    result = validate_llm_output_contract(
        "Saya tidak dapat menjawab berdasarkan asumsi atau pengetahuan umum tanpa dokumen sumber [1].",
        requires_citation=True,
    )

    assert result.allowed is True
    assert result.categories == []
