## TUGAS AKHIR — BAB 4 Adaptasi Kode

Folder ini berisi penulisan ulang BAB 4 yang disesuaikan dengan implementasi aktual pada repository PUSDATIK. Struktur barunya dibuat agar pusat pembahasan berada pada alur RAG, model LLM, retrieval, ingestion, dan evaluasi. LDAP dan JWT tetap dibahas, tetapi sebagai komponen pendukung, bukan topik utama.

- 4.1_Pendahuluan.md — konteks penelitian, tujuan sistem, dan ruang lingkup
- 4.2_Arsitektur_RAG_Dan_Retrieval.md — alur query, hybrid search, ranking, dan penyusunan konteks
- 4.3_Model_LLM_Dan_Prompting.md — model lokal, prompt legal, guardrail, dan streaming jawaban
- 4.4_Ingestion_Chunking_Dan_Indexing.md — ekstraksi dokumen, chunking, dan indexing ke Qdrant/BM25
- 4.5_Pengujian_Dan_Quality_Gate.md — pengujian, quality check, dan evaluasi keluaran
- 4.6_Autentikasi_Dan_Sesi_Pendukung.md — LDAP, JWT, shadow user, dan sesi pengguna
- 4.7_Kesimpulan_Dan_Saran.md — simpulan serta saran pengembangan lanjutan

Dokumen ini sebaiknya dibaca bersama file inti di `backend/app/core/rag/`, `backend/app/core/ingestion/`, `backend/app/api/routes/chat.py`, dan `backend/app/auth/`.
