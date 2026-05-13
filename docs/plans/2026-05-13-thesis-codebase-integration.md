# Thesis Codebase Integration Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Menambahkan potongan kode riil dari backend ke dalam dokumen Tugas Akhir (BAB 4) dengan penjelasan teknis mendalam.

**Architecture:** Menggunakan pola "Teori -> Implementasi Kode -> Analisis Teknis" di setiap sub-bab yang relevan.

**Tech Stack:** Python (FastAPI, LangChain, Qdrant, LDAP3), Markdown.

---

### Task 1: Integrasi Arsitektur RAG (Bab 4.2)

**Files:**
- Modify: `d:\aqil\pusdatik\TUGAS_AKHIR\4.2_Arsitektur_RAG_Mendalam.md`
- Source: `d:\aqil\pusdatik\backend\app\core\rag\langchain_engine.py`
- Source: `d:\aqil\pusdatik\backend\app\core\rag\engine\retrievers.py`

**Step 1: Update section 4.2.1 dengan orkestrasi LangchainRAGEngine**
Masukkan kodingan `retrieve_context` dari `langchain_engine.py`.

**Step 2: Update section 4.2.3 dengan Hybrid Retrieval**
Masukkan kodingan `vector_search` dan `bm25_search` dari `retrievers.py`.

**Step 3: Tambahkan analisis teknis untuk RRF Fusion**
Jelaskan bagaimana skor dari berbagai jalur retrieval digabungkan.

**Step 4: Commit**
```bash
git add TUGAS_AKHIR/4.2_Arsitektur_RAG_Mendalam.md
git commit -m "docs: add real RAG architecture code and analysis to Bab 4.2"
```

---

### Task 2: Integrasi Ingestion & Chunking (Bab 4.4)

**Files:**
- Modify: `d:\aqil\pusdatik\TUGAS_AKHIR\4.4_Ingestion_Chunking_Indexing.md`
- Source: `d:\aqil\pusdatik\backend\app\core\ingestion\structured_chunker.py`

**Step 1: Update section 4.4.2 dengan Strategi Chunking Peraturan**
Masukkan kodingan `chunk_peraturan` yang menunjukkan pembagian per Pasal/Ayat.

**Step 2: Update section 4.4.2 dengan Linearisasi Tabel**
Masukkan kodingan `_linearize_md_table` untuk menjelaskan preservasi data tabel.

**Step 3: Tambahkan analisis teknis mengenai metadata hierarchy**
Jelaskan pentingnya `hierarchy` metadata untuk sitasi hukum.

**Step 4: Commit**
```bash
git add TUGAS_AKHIR/4.4_Ingestion_Chunking_Indexing.md
git commit -m "docs: add chunking and table processing code to Bab 4.4"
```

---

### Task 3: Integrasi Quality Gates (Bab 4.5)

**Files:**
- Modify: `d:\aqil\pusdatik\TUGAS_AKHIR\4.5_Quality_Gates_Guardrails.md`
- Source: `d:\aqil\pusdatik\backend\app\core\rag\prompts.py`

**Step 1: Update section 4.5.2 dengan Answer Validation**
Masukkan kodingan `validate_answer` yang melakukan audit sitasi.

**Step 2: Update section 4.5.3 dengan Hierarchy Confusion Check**
Masukkan kodingan `_check_spbe_hierarchy_confusion` sebagai contoh guardrail domain-spesifik.

**Step 3: Tambahkan analisis teknis mengenai grounding**
Jelaskan bagaimana sistem memastikan jawaban AI tetap berpijak pada dokumen referensi.

**Step 4: Commit**
```bash
git add TUGAS_AKHIR/4.5_Quality_Gates_Guardrails.md
git commit -m "docs: add quality gate and guardrail code to Bab 4.5"
```

---

### Task 4: Integrasi Security (Bab 4.6)

**Files:**
- Modify: `d:\aqil\pusdatik\TUGAS_AKHIR\4.6_Authentication_Security.md`
- Source: `d:\aqil\pusdatik\backend\app\auth\ldap_provider.py`
- Source: `d:\aqil\pusdatik\backend\app\api\auth_routes.py`

**Step 1: Update section Autentikasi dengan LDAP Integration**
Masukkan kodingan `LDAPAuthProvider.authenticate` dan `_upsert_shadow_user`.

**Step 2: Update section Session Management dengan JWT Login**
Masukkan kodingan `login_for_access_token` yang menangani HttpOnly cookies.

**Step 3: Tambahkan analisis teknis mengenai keamanan session**
Jelaskan perlindungan terhadap serangan CSRF dan XSS melalui cookie secure.

**Step 4: Commit**
```bash
git add TUGAS_AKHIR/4.6_Authentication_Security.md
git commit -m "docs: add LDAP and JWT security code to Bab 4.6"
```
