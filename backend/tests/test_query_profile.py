from app.core.rag.query_profile import classify_query_profile


def test_query_profile_classifies_national_purpose_question():
    profile = classify_query_profile("Apa tujuan Tata Kelola SPBE?")

    assert profile.retrieval_type == "general"
    assert profile.answer_type == "purpose"
    assert profile.scope == "national"


def test_query_profile_classifies_bssn_purpose_question():
    profile = classify_query_profile("Apa tujuan Tata Kelola SPBE BSSN?")

    assert profile.retrieval_type == "general"
    assert profile.answer_type == "purpose"
    assert profile.scope == "bssn"


def test_query_profile_preserves_specialized_retrieval_type():
    profile = classify_query_profile("Apa isi Tabel 13 SPBE?")

    assert profile.retrieval_type == "table"
    assert profile.answer_type == "general"
    assert profile.scope == "national"
