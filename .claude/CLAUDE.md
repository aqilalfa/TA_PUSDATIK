# 🤖 CLAUDE.md — Pusdatik SPBE RAG Multi-Agent Orchestration

> **Global Agent Configuration** — Berlaku untuk semua session Claude pada workspace ini.
> Main session: **Claude Sonnet** | Sub-agents: **Opus** (heavy tasks) & **Haiku** (lightweight tasks)

---

## 📋 Konteks Proyek

Proyek ini adalah **SPBE RAG System** — sistem Retrieval-Augmented Generation untuk menjawab pertanyaan tentang peraturan SPBE dan hasil audit keamanan BSSN. Dibangun internal untuk **Badan Siber dan Sandi Negara (BSSN)**.

### Tech Stack
- **Backend**: FastAPI (Python) + LlamaIndex + Qdrant + SQLite
- **Frontend**: Vue.js 3 + Vite + Vanilla CSS
- **AI/ML**: Qwen 2.5 7B (GGUF Q4_K_M), indo-sentence-bert-base, BAAI/bge-reranker-base
- **OCR**: PaddleOCR (GPU)
- **Infrastructure**: Docker Compose + NVIDIA Docker
- **Evaluation**: RAGAS + BUS-11

### Arsitektur Utama
```
User Query → Query Reformulation → Hybrid Search (Vector + BM25)
    ↓
Reciprocal Rank Fusion → Reranking → Top-K Selection
    ↓
Context Injection → LLM Generation → Response + Citations
    ↓
Save to Conversation History
```

### Struktur Kode Kritis
```
backend/
├── app/
│   ├── api/routes/          # FastAPI endpoints (chat, documents, sessions, health, models)
│   ├── core/
│   │   ├── rag/
│   │   │   ├── langchain_engine.py   # ★ RAG engine utama (~61KB) — hybrid search, rerank, LLM
│   │   │   └── prompts.py            # System prompts & query classification
│   │   ├── ingestion/
│   │   │   ├── document_manager.py   # ★ Document lifecycle (~67KB)
│   │   │   ├── structured_chunker.py # Chunking strategy
│   │   │   ├── json_structure_parser.py # JSON structure parsing
│   │   │   ├── marker_converter.py   # PDF → Markdown conversion
│   │   │   └── ocr.py               # PaddleOCR wrapper
│   │   ├── agents/                   # Agentic AI (planned)
│   │   ├── session/                  # Session management
│   │   └── database.py              # DB operations
│   ├── models/                       # Pydantic & DB models
│   ├── config.py                     # App configuration
│   └── main.py                       # FastAPI app entry
├── scripts/                          # Utility & migration scripts
└── tests/                            # Test suite

frontend/
├── src/
│   ├── views/          # ChatView, DocumentsView, DocumentDetailView, HomeView
│   ├── components/     # chat/, documents/, common/, session/
│   ├── services/       # API service layer
│   └── stores/         # State management
```

---

## 🎯 Model Delegation Strategy

### 🟡 Sonnet — Main Session (Default Coder)

Sonnet adalah **conductor utama** yang menangani semua interaksi dan coding. Gunakan Sonnet untuk:

| Domain | Contoh Task |
|--------|-------------|
| **Coding & Implementation** | Menulis/edit kode Python, Vue.js, CSS, JavaScript |
| **Bug Fixing** | Debug errors di FastAPI endpoints, Vue components, RAG pipeline |
| **Feature Development** | Implementasi fitur baru di backend/frontend |
| **API Routes** | Menambah/memodifikasi endpoint di `backend/app/api/routes/` |
| **RAG Pipeline Tuning** | Adjust search parameters, prompt engineering di `prompts.py` |
| **Database Operations** | SQLite queries, migration scripts |
| **Docker/Config** | Docker Compose, `.env`, `config.py` changes |
| **Test Writing** | Menulis unit/integration tests |
| **Quick Refactoring** | Rename, extract function, reorganize imports |
| **Git Operations** | Commit, branch, merge, rebase |

**Prinsip Sonnet**: Act first, iterate fast. Sonnet langsung code tanpa over-thinking. Jika task jelas, langsung implement.

---

### 🔴 Opus — Heavy Analysis Sub-Agent

Delegasikan ke Opus ketika task membutuhkan **deep reasoning**, **analisis arsitektural**, atau **keputusan desain yang kompleks**. Opus adalah "senior architect" dari tim.

| Domain | Contoh Task | Kapan Trigger |
|--------|-------------|---------------|
| **Architecture Design** | Redesign RAG pipeline, merancang Agentic AI framework | Ketika ada perubahan arsitektur besar |
| **Complex Debugging** | Bug yang melibatkan interaksi multi-komponen (Qdrant ↔ RAG ↔ LLM ↔ Frontend) | Setelah Sonnet gagal 2x debug |
| **Performance Analysis** | Analisis bottleneck di `langchain_engine.py` (61KB), optimasi retrieval | Ketika response time > 30s atau OOM |
| **Security Review** | Audit keamanan kode (penting karena ini proyek BSSN!) | Sebelum deployment |
| **Algorithm Design** | Desain chunking strategy baru, reranking algorithm, RRF tuning | Ketika kualitas RAG menurun |
| **Data Model Design** | Redesign schema database, Qdrant collection structure | Ketika ada data migration besar |
| **Evaluation Framework** | Desain RAGAS evaluation pipeline, interpretasi metrics | Saat setup/analisis evaluasi |
| **Cross-cutting Concerns** | Refactor yang menyentuh >5 file kritis sekaligus | Ketika refactor besar diperlukan |
| **Legal Document Parsing** | Desain parser baru untuk jenis dokumen hukum yang kompleks | Ketika ada tipe dokumen baru |
| **Trade-off Analysis** | Memilih antara approach A vs B dengan implikasi jangka panjang | Ketika ada keputusan teknis kritis |

**Template Delegasi ke Opus:**
```
@opus Analisis mendalam diperlukan:

## Konteks
[Jelaskan situasi saat ini]

## Problem
[Jelaskan masalah spesifik]

## Constraint
- GPU: GTX 1650 (4GB VRAM)
- RAM: 16GB
- LLM: Qwen 2.5 7B Q4_K_M
- Target: Internal BSSN deployment

## Expected Output
[Apa yang diharapkan dari analisis Opus]
```

**Prinsip Opus**: Think deep before acting. Opus harus memberikan analisis menyeluruh, trade-off, dan rekomendasi terstruktur sebelum kode apapun ditulis.

---

### 🟢 Haiku — Lightweight Sub-Agent

Delegasikan ke Haiku untuk task yang **repetitif**, **dokumentasi**, atau **low-complexity**. Haiku adalah "junior developer" yang cepat dan efisien.

| Domain | Contoh Task | Kapan Trigger |
|--------|-------------|---------------|
| **Dokumentasi** | Update README.md, SETUP_GUIDE.md, API docs, JSDoc/docstrings | Setelah fitur baru selesai |
| **Comment & Docstrings** | Tambahkan docstrings ke functions di `langchain_engine.py` | Saat code review |
| **Changelog** | Generate changelog dari git log | Sebelum release |
| **Translation** | Terjemahan docs EN↔ID | Ketika perlu lokalisasi |
| **Boilerplate Code** | Generate Pydantic models, CRUD endpoints sederhana | Ketika pattern sudah jelas |
| **File Organization** | Rename files, move imports, organize directory | Housekeeping tasks |
| **Test Data Generation** | Generate mock data, test fixtures | Saat menulis tests |
| **Error Messages** | Tulis user-friendly error messages (Bahasa Indonesia) | Saat polish UX |
| **Config Files** | Generate `.env.example`, Docker config templates | Setup tasks |
| **Status Reports** | Generate progress report dari current state | Saat weekly review |
| **Simple Search & Replace** | Bulk rename, pattern replacement across files | Maintenance tasks |
| **Markdown Formatting** | Format tabel, cleanup markdown documents | Document polish |

**Template Delegasi ke Haiku:**
```
@haiku Task ringan:

## Task
[Deskripsi singkat]

## Files
[File yang perlu diproses]

## Output Format
[Format output yang diharapkan]
```

**Prinsip Haiku**: Fast and focused. Haiku harus menyelesaikan task secepat mungkin tanpa over-engineering. Jangan minta Haiku untuk membuat keputusan arsitektural.

---

## 🔄 Delegation Flowchart

```
User Request Masuk
       │
       ▼
┌──────────────────┐
│ Sonnet (Default)  │
│ Evaluasi Request  │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Simple?    Complex?
    │         │
    ▼         │
 ┌──────┐    │
 │Sonnet│    ├─── Architecture/Design? ──────► @opus
 │Handle│    ├─── Multi-component Debug? ────► @opus
 │ Self │    ├─── Security Review? ──────────► @opus
 └──────┘    ├─── Performance Deep-dive? ───► @opus
             ├─── Algorithm Design? ────────► @opus
             │
             ├─── Documentation? ───────────► @haiku
             ├─── Boilerplate/Templates? ───► @haiku
             ├─── Changelog/Reports? ───────► @haiku
             ├─── Test Data/Fixtures? ──────► @haiku
             └─── Config Generation? ───────► @haiku
```

---

## 📏 Delegation Rules

### Rule 1: Sonnet First
Sonnet selalu mencoba handle dulu. Hanya delegasikan jika:
- Task terlalu kompleks untuk satu pass (→ Opus)
- Task terlalu sederhana/repetitif (→ Haiku)

### Rule 2: Escalation Path
```
Haiku gagal → Sonnet ambil alih
Sonnet gagal 2x → Delegasi ke Opus
Opus memberikan plan → Sonnet implement
```

### Rule 3: Context Passing
Saat mendelegasikan, selalu sertakan:
1. **File paths** yang relevan
2. **Error messages** jika debugging
3. **Constraint** (GPU 4GB, RAM 16GB, internal BSSN)
4. **Expected output format**

### Rule 4: Specialization Override
Beberapa task SELALU ke model tertentu:
- **Security review** → SELALU Opus (karena ini proyek BSSN)
- **Docstrings batch** → SELALU Haiku (efisien)
- **RAG pipeline code** → SELALU Sonnet (butuh speed + quality)

---

## 🛠️ Project-Specific Guidelines

### Coding Conventions
- **Python**: Follow PEP 8, gunakan type hints, loguru untuk logging
- **Vue.js**: Composition API (`<script setup>`), Vanilla CSS (bukan Tailwind)
- **Naming**: snake_case (Python), camelCase (JS), kebab-case (files/CSS)
- **Imports**: Absolute imports dari `app.` prefix
- **Error Handling**: Selalu handle exceptions di API routes, log dengan loguru
- **Bahasa**: Code comments dalam Bahasa Inggris, user-facing strings dalam Bahasa Indonesia

### File Sensitivity
File-file ini adalah **core kritis** — perubahan harus extra hati-hati:
- `backend/app/core/rag/langchain_engine.py` — RAG engine utama
- `backend/app/core/ingestion/document_manager.py` — Document lifecycle
- `backend/app/core/rag/prompts.py` — System prompts
- `backend/app/api/routes/chat.py` — Chat endpoint (streaming SSE)
- `backend/app/core/ingestion/structured_chunker.py` — Chunking strategy

### Testing Requirements
- Sebelum modify file kritis, jalankan existing tests: `venv/Scripts/python -m pytest tests/ -v`
- Gunakan TDD approach: test dulu baru implement (gunakan skill `rag-debug-answer` jika ada masalah RAG)
- Test RAG changes dengan `backend/scripts/rag_trace.py`

### Environment Constraints
- **GPU**: NVIDIA GTX 1650 (4GB VRAM) — model harus quantized
- **RAM**: 16GB — perhatikan memory usage saat loading models
- **OS**: Windows 10/11 (development), Docker target
- **Network**: Internal BSSN — no external API calls untuk LLM
- **Python**: 3.10+ dengan venv di `backend/venv/`
- **Node**: Untuk frontend di `frontend/`

---

## 📝 Quick Reference Commands

```bash
# Backend
cd backend
venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend
npm run dev

# Tests
cd backend
venv/Scripts/python -m pytest tests/ -v

# RAG Trace (debug retrieval)
cd backend
venv/Scripts/python scripts/rag_trace.py --query "apa isi pasal 5?" --doc-id 6 --json

# Document Ingestion
cd backend
venv/Scripts/python scripts/ingest_documents.py --input-dir data/documents

# Database Reset
cd backend
venv/Scripts/python scripts/full_reset.py

# Health Check
curl -sf http://localhost:8000/api/health/

# Docker (production)
docker-compose -f docker-compose.dev.yml up -d
```

---

## 🎓 Domain Knowledge

### Jenis Dokumen yang Diproses
1. **Peraturan SPBE** — PP, Perpres, Permen tentang Sistem Pemerintahan Berbasis Elektronik
2. **Surat Edaran (SE)** — SE BSSN dengan lampiran Petunjuk Teknis
3. **Laporan Audit BSSN** — Hasil audit keamanan siber dengan tabel-tabel
4. **Pedoman** — Panduan teknis implementasi SPBE

### Terminologi Kunci
- **SPBE**: Sistem Pemerintahan Berbasis Elektronik
- **BSSN**: Badan Siber dan Sandi Negara
- **RAG**: Retrieval-Augmented Generation
- **RRF**: Reciprocal Rank Fusion
- **Pasal/Ayat**: Article/Verse dalam peraturan hukum
- **Chunking**: Memecah dokumen menjadi potongan-potongan untuk indexing
- **Reranking**: Re-scoring hasil retrieval dengan cross-encoder
- **RAGAS**: RAG Assessment framework (faithfulness, relevancy, precision, recall)
- **BUS-11**: Bot Usability Scale evaluation

---

## ⚡ Delegation Examples

### Contoh 1: Bug di RAG → Sonnet handles
```
User: "Kenapa query 'apa isi pasal 5' mengembalikan dokumen yang salah?"

Sonnet:
1. Gunakan skill rag-debug-answer
2. Jalankan rag_trace.py
3. Identifikasi root cause
4. Fix code langsung
```

### Contoh 2: Redesign Chunking Strategy → Opus
```
User: "Chunking saat ini kehilangan konteks tabel. Redesign dong."

Sonnet → @opus:
"Analisis structured_chunker.py (32KB) dan document_manager.py (67KB).
Dokumen yang diproses: peraturan hukum Indonesia dengan tabel-tabel audit.
Problem: chunks kehilangan konteks tabel saat split.
Constraint: max chunk ~512 tokens untuk embedding model.
Output: Rekomendasi algorithm baru dengan trade-off analysis."

Opus memberikan design → Sonnet implement
```

### Contoh 3: Update semua docstrings → Haiku
```
User: "Tambahin docstrings ke semua function di ingestion module."

Sonnet → @haiku:
"Tambahkan Google-style docstrings ke semua public functions di:
- backend/app/core/ingestion/document_manager.py
- backend/app/core/ingestion/structured_chunker.py
- backend/app/core/ingestion/json_structure_parser.py
- backend/app/core/ingestion/marker_converter.py
- backend/app/core/ingestion/ocr.py
Format: Google-style, Bahasa Inggris, include Args, Returns, Raises."
```

### Contoh 4: Implement Agentic AI → Opus designs, Sonnet codes
```
User: "Implementasi Legal Analysis Agent."

Sonnet → @opus:
"Design Legal Analysis Agent untuk backend/app/core/agents/.
Harus bisa: analisis pasal/ayat, interpretasi hukum, komparasi antar peraturan.
Tech: LlamaIndex ReAct agent, Qwen 2.5 7B.
Constraint: 4GB VRAM, harus bisa streaming response.
Output: Detailed design doc + interface specification."

Opus memberikan spec → Sonnet implement → @haiku dokumentasi
```

### Contoh 5: Security audit sebelum deploy → Opus
```
User: "Review keamanan sebelum deploy ke jaringan internal BSSN."

Sonnet → @opus:
"Full security review untuk deployment ke jaringan internal BSSN:
1. API endpoint security (auth, rate limiting, input validation)
2. File upload security (backend/app/api/routes/documents.py)
3. SQL injection prevention (SQLite queries)
4. Dependency vulnerability scan
5. Docker security (runtime, privileges)
6. Data privacy (dokumen sensitif BSSN)
Output: Security report dengan severity rating + remediation steps."
```

---

## 📌 Catatan Penting

1. **Ini adalah proyek internal BSSN** — semua model AI dijalankan lokal, tidak ada panggilan ke API eksternal
2. **Dokumen bersifat sensitif** — jangan expose isi dokumen ke layanan external
3. **GPU terbatas** — selalu pertimbangkan memory footprint
4. **Bahasa Indonesia** — UI dan responses harus dalam Bahasa Indonesia yang baik dan benar
5. **Kualitas RAG** — setiap perubahan pada RAG pipeline harus divalidasi dengan `rag_trace.py`
