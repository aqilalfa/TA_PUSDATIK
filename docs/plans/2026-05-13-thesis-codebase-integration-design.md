# Design Doc: Integrasi Kodingan Riil ke Dokumen Tugas Akhir

**Tanggal**: 13 Mei 2026  
**Status**: 🛠️ In-Progress  
**Tujuan**: Melakukan pembaruan pada dokumen BAB 4 (Tugas Akhir) dengan menyertakan potongan kodingan riil dari sistem RAG Pusdatik untuk memberikan penjelasan teknis yang lebih mendalam dan valid.

---

## 1. Arsitektur Integrasi Kode

Setiap bab akan mengikuti pola **"Teori -> Implementasi Kode -> Analisis Teknis"**. Kode yang dipilih adalah fungsi-fungsi inti (*core functions*) yang merepresentasikan inovasi dalam penelitian ini.

### Bab 4.2: Arsitektur RAG & Retrieval
- **Core Snippets**: 
    - `LangchainRAGEngine.retrieve_context`: Alur orkestrasi 6 tahap.
    - `HybridRetriever.vector_search` & `bm25_search`: Logika pencarian hibrida.
- **Analisis**: Menjelaskan bagaimana Reciprocal Rank Fusion (RRF) menggabungkan sinyal semantik dan literal.

### Bab 4.4: Pipeline Ingestion & Chunking
- **Core Snippets**:
    - `chunk_peraturan`: Strategi pemotongan berbasis Pasal/Ayat.
    - `_linearize_md_table`: Teknik menjaga integritas data tabel.
- **Analisis**: Justifikasi pemilihan ukuran chunk (900 vs 1800 char) berdasarkan batas token LLM.

### Bab 4.5: Quality Gates & Guardrails
- **Core Snippets**:
    - `validate_answer`: Audit konsistensi sitasi.
    - `_check_spbe_hierarchy_confusion`: Pencegahan halusinasi level hierarki SPBE.
- **Analisis**: Bagaimana sistem meminimalisir *hallucination rate* pada domain hukum yang sensitif.

### Bab 4.6: Keamanan & Autentikasi
- **Core Snippets**:
    - `LDAPAuthProvider.authenticate`: Integrasi direktori aktif dan *shadow user*.
    - `auth_routes.login_for_access_token`: Manajemen sesi JWT.
- **Analisis**: Penjelasan mengenai keamanan berlapis (LDAP + JWT + Audit Logging).

---

## 2. Standar Penulisan

1. **Bahasa**: Indonesia Formal (Pemerintahan/Akademik).
2. **Format Kode**: Markdown Fenced Code Blocks dengan *syntax highlighting* Python.
3. **Keterangan**: Setiap blok kode wajib memiliki komentar dalam kode (Inggris/Indo) dan narasi penjelasan di bawah blok kode (Indo).

---

## 3. Rencana Verifikasi

- Memastikan potongan kode yang dimasukkan adalah versi terbaru dari folder `backend/`.
- Memastikan tidak ada data sensitif (seperti password atau API key asli) yang terbawa ke dalam dokumen.
- Memvalidasi alur penjelasan teknis agar selaras dengan kesimpulan di Bab 4.7.
