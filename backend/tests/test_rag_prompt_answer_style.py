import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent))


from app.core.rag.prompts import build_answer_style_instructions, build_rag_prompt, build_simple_prompt


def test_value_or_time_question_gets_one_sentence_direct_answer_instruction():
    instructions = build_answer_style_instructions(
        "Untuk berapa lama Arsitektur SPBE Nasional disusun?"
    )

    assert "Tipe pertanyaan: BERAPA/KAPAN/NILAI/WAKTU." in instructions
    assert "dalam 1 kalimat" in instructions
    assert "DILARANG menambahkan penjelasan tujuan, proses, atau konteks historis" in instructions


def test_actor_question_gets_entity_only_instruction():
    instructions = build_answer_style_instructions(
        "Siapa entitas yang bertugas sebagai Pelaksana Audit Keamanan SPBE?"
    )

    assert "Tipe pertanyaan: SIAPA/ENTITAS." in instructions
    assert "Tulis nama pihak/lembaga/instansi" in instructions
    assert "DILARANG menambahkan kalimat kedua berisi tugas" in instructions


def test_list_question_preserves_complete_list_requirement():
    instructions = build_answer_style_instructions(
        "Apa sanksi administratif jika Penyelenggara Sistem Elektronik melakukan pelanggaran?"
    )

    assert "Tipe pertanyaan: DAFTAR." in instructions
    assert "bullet list singkat dan LENGKAP" in instructions


def test_rag_prompt_includes_answer_first_and_context_spillover_rules():
    prompt = build_rag_prompt(
        "Apa tujuan diadakannya Tata Kelola SPBE?",
        "[1] Tata Kelola SPBE bertujuan untuk memastikan penerapan unsur-unsur SPBE secara terpadu.",
    )

    assert "PROFIL JAWABAN BERDASARKAN TIPE PERTANYAAN" in prompt
    assert "Tipe pertanyaan: TUJUAN." in prompt
    assert "Kalimat pertama jawaban HARUS berisi fakta inti yang ditanya" in prompt
    assert "abaikan konteks sampingan" in prompt


def test_simple_prompt_includes_same_answer_style_guidance():
    prompt = build_simple_prompt(
        "Apa yang dimaksud dengan Aplikasi SPBE Prioritas?",
        "[1] Aplikasi SPBE Prioritas adalah Aplikasi SPBE berdampak luas.",
    )

    assert "PROFIL JAWABAN BERDASARKAN TIPE PERTANYAAN" in prompt
    assert "Tipe pertanyaan: DEFINISI/PENGERTIAN." in prompt
    assert "Tulis definisi inti dalam 1 kalimat" in prompt
