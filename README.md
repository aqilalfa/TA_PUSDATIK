# SPBE RAG System - Sistem Retrieval-Augmented Generation untuk Peraturan SPBE dan Audit BSSN

<div align="center">

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Vue](https://img.shields.io/badge/Vue.js-3.4-green)
![License](https://img.shields.io/badge/license-MIT-blue)

**Sistem AI canggih untuk menjawab pertanyaan tentang peraturan SPBE dan hasil audit keamanan BSSN menggunakan Retrieval-Augmented Generation (RAG)**

[Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Development](#-development)

</div>

---

## 📋 Daftar Isi

- [Overview](#-overview)
- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Development Roadmap](#-development-roadmap)
- [Contributing](#-contributing)

---

## 🎯 Overview

SPBE RAG System adalah sistem berbasis AI yang dikembangkan khusus untuk internal BSSN (Badan Siber dan Sandi Negara) yang memungkinkan pengguna untuk:

- **Bertanya** tentang peraturan SPBE (Sistem Pemerintahan Berbasis Elektronik)
- **Menganalisis** hasil audit keamanan BSSN dari berbagai tahun
- **Mendapatkan** jawaban yang akurat dengan referensi pasal/ayat yang jelas
- **Menghasilkan** laporan dan analisis hukum menggunakan Agentic AI

Sistem ini menggunakan teknologi RAG (Retrieval-Augmented Generation) yang menggabungkan pencarian semantik dengan generasi bahasa alami oleh Large Language Model (LLM).

---

## ✨ Features

### 🔍 Hybrid Search
- **Vector Search**: Pencarian semantik menggunakan embedding model khusus Bahasa Indonesia
- **BM25 Search**: Pencarian keyword-based tradisional
- **Reciprocal Rank Fusion**: Menggabungkan hasil dari kedua metode untuk akurasi maksimal

### 🧠 AI-Powered
- **LLM**: Qwen 2.5 7B Instruct (quantized untuk GPU 4GB)
- **Embedding**: firqaaa/indo-sentence-bert-base (optimized untuk Bahasa Indonesia)
- **Reranker**: BAAI/bge-reranker-base untuk hasil yang lebih relevan

### 📄 Document Processing
- **OCR**: PaddleOCR untuk PDF yang tidak text-selectable
- **Adaptive Parsing**: Parser khusus untuk peraturan hukum vs dokumen audit
- **Metadata Extraction**: Ekstraksi otomatis nomor peraturan, pasal, ayat, tanggal, dll.

### 💬 Conversation Memory
- **Multi-user Support**: Session management untuk banyak pengguna simultan
- **Context-Aware**: Query reformulation berdasarkan riwayat percakapan
- **Persistent History**: Semua percakapan tersimpan di database

### 🤖 Agentic AI
- **Legal Analysis Agent**: Analisis pasal/ayat dan interpretasi hukum
- **Summarization Agent**: Ringkasan dokumen dan ekstraksi poin kunci
- **Comparison Agent**: Bandingkan hasil audit antar tahun
- **Report Writer Agent**: Generate draft laporan terstruktur

### 📊 Evaluation Framework
- **RAGAS**: Evaluasi RAG dengan metrics faithfulness, relevancy, precision, recall
- **BUS-11**: Evaluasi usability chatbot

---

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **LLM Framework**: LlamaIndex
- **Vector Database**: Qdrant
- **Database**: SQLite (untuk session & metadata)
- **OCR**: PaddleOCR dengan GPU support
- **Search**: BM25 + Vector Hybrid Search

### Frontend
- **Framework**: Vue.js 3
- **Build Tool**: Vite
- **State Management**: Pinia
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **GPU Runtime**: NVIDIA Docker (untuk CUDA support)
- **Deployment**: Internal BSSN network

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      DOCKER COMPOSE STACK                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Qdrant    │  │   Backend   │  │  Frontend   │            │
│  │  (Vector    │  │  (FastAPI   │  │  (Vue.js    │            │
│  │   Store)    │  │  + Python)  │  │  + Nginx)   │            │
│  │  Port: 6333 │  │  Port: 8000 │  │  Port: 5173 │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                 │                 │                   │
│         └─────────────────┴─────────────────┘                   │
│                           │                                     │
│                  ┌────────▼────────┐                            │
│                  │ Shared Volumes  │                            │
│                  │ - models/       │                            │
│                  │ - data/         │                            │
│                  │ - database/     │                            │
│                  └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

**RAG Pipeline Flow:**
```
User Query → Query Reformulation → Hybrid Search (Vector + BM25)
    ↓
Reciprocal Rank Fusion → Reranking → Top-K Selection
    ↓
Context Injection → LLM Generation → Response + Citations
    ↓
Save to Conversation History
```

---

## 🔧 Prerequisites

### Hardware Requirements
- **GPU**: NVIDIA GTX 1650 or better (4GB+ VRAM)
- **RAM**: 16GB minimum
- **Storage**: 20GB free space
- **CPU**: Multi-core processor (Ryzen 7 2700 or equivalent)

### Software Requirements
- **OS**: Windows 10/11 with WSL2, Ubuntu 22.04, or compatible Linux
- **Docker**: Docker Engine 20.10+
- **Docker Compose**: v2.0+
- **NVIDIA Docker Runtime**: For GPU support
- **Git**: For version control

---

## 🚀 Quick Start

### Step 1: Install NVIDIA Docker Runtime

**Ubuntu/Linux:**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Verify GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**Windows with WSL2:**
1. Install WSL2: `wsl --install`
2. Install Docker Desktop for Windows
3. Enable WSL2 backend in Docker Desktop settings
4. Install NVIDIA CUDA on WSL2 from: https://developer.nvidia.com/cuda/wsl
5. Follow Ubuntu steps above inside WSL2

### Step 2: Clone Repository

```bash
git clone https://github.com/your-org/spbe-rag-system.git
cd spbe-rag-system
```

### Step 3: Download Models

```bash
# Run model download script
cd backend
python scripts/download_models.py

# This will download (~6-7 GB total):
# - Qwen 2.5 7B Instruct GGUF Q4_K_M (~4.37 GB)
# - indo-sentence-bert-base (~400 MB)
# - bge-reranker-base (~1 GB)

# Verify models
python scripts/download_models.py --verify
```

### Step 4: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit if needed (defaults should work)
nano .env
```

### Step 5: Build & Run

```bash
# Return to project root
cd ..

# Build containers
docker-compose -f docker-compose.dev.yml build

# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Watch logs
docker-compose -f docker-compose.dev.yml logs -f
```

### Step 6: Upload Your Documents

```bash
# Copy your 3 PDF documents to data/documents/
# Example:
cp /path/to/PP_71_2019.pdf data/documents/peraturan/
cp /path/to/audit_2023.pdf data/documents/audit/
cp /path/to/lainnya.pdf data/documents/others/

# Process documents (when ingestion pipeline is ready)
docker-compose -f docker-compose.dev.yml exec backend python scripts/ingest_documents.py --input-dir /app/data/documents
```

### Step 7: Access Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

---

## 📁 Project Structure

```
spbe-rag-system/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── api/               # API routes
│   │   ├── core/              # RAG core logic
│   │   ├── models/            # Database & Pydantic models
│   │   ├── evaluation/        # RAGAS & BUS-11
│   │   └── utils/             # Utilities
│   ├── scripts/               # Initialization scripts
│   └── tests/                 # Unit & integration tests
├── frontend/                   # Vue.js frontend
│   └── src/
│       ├── components/        # Vue components
│       ├── views/             # Page views
│       ├── stores/            # Pinia stores
│       └── services/          # API client
├── data/                      # Data storage
│   ├── documents/             # Original PDFs
│   ├── ocr_output/            # OCR results
│   └── evaluation/            # Evaluation datasets
├── models/                    # AI models
│   ├── llm/                   # LLM (Qwen GGUF)
│   ├── embeddings/            # Embedding model
│   └── reranker/              # Reranker model
├── database/                  # SQLite database
├── qdrant_storage/            # Qdrant persistence
└── docs/                      # Documentation
```

---

## 🗓️ Development Roadmap

### ✅ Phase 0: Project Setup (COMPLETED)
- [x] Docker environment setup
- [x] Project structure created
- [x] Backend skeleton (FastAPI, database, API routes)
- [x] Frontend skeleton (Vue.js, routing, components)
- [x] Model download script
- [x] Documentation

### 🔄 Phase 1: OCR & Document Ingestion (Week 1-2)
- [ ] PaddleOCR integration
- [ ] Adaptive document parsers
- [ ] Metadata extraction
- [ ] Chunking strategy
- [ ] Test with 3 documents

### 🔄 Phase 2: RAG Core (Week 2-4)
- [ ] Embedding pipeline
- [ ] Qdrant setup & indexing
- [ ] BM25 implementation
- [ ] Hybrid search with RRF
- [ ] Reranker integration
- [ ] LLM integration
- [ ] End-to-end RAG testing

### 🔜 Phase 3: Backend API (Week 4-6)
- [ ] Session management
- [ ] Conversation memory
- [ ] Context-aware query processing
- [ ] Streaming responses
- [ ] Full API integration

### 🔜 Phase 4: Frontend Development (Week 7-8)
- [ ] Chat interface
- [ ] Session selector
- [ ] Document uploader
- [ ] Markdown rendering
- [ ] Citation display
- [ ] UI/UX polish

### 🔜 Phase 5: Agentic AI (Week 9-10)
- [ ] Agent tools implementation
- [ ] ReAct agent setup
- [ ] Multi-step workflows
- [ ] Agent integration with chat

### 🔜 Phase 6: Evaluation (Week 11)
- [ ] Ground truth dataset creation
- [ ] RAGAS implementation
- [ ] BUS-11 implementation
- [ ] Performance optimization

### 🔜 Phase 7: Production Ready (Week 12)
- [ ] Load testing
- [ ] Security hardening
- [ ] Complete documentation
- [ ] Deployment to BSSN internal

**🎯 Target Completion: 3 months**

---

## 💻 Development

### Hot-Reload Development

The development setup supports hot-reload for both backend and frontend:

**Backend (Python):**
- Edit files in `backend/app/`
- Uvicorn auto-reloads on file changes
- No rebuild needed

**Frontend (Vue.js):**
- Edit files in `frontend/src/`
- Vite HMR updates browser instantly
- No rebuild needed

### Common Commands

```bash
# View logs
docker-compose -f docker-compose.dev.yml logs -f [service_name]

# Restart a service
docker-compose -f docker-compose.dev.yml restart backend

# Rebuild after dependency changes
docker-compose -f docker-compose.dev.yml build backend
docker-compose -f docker-compose.dev.yml up -d backend

# Enter container shell
docker-compose -f docker-compose.dev.yml exec backend bash

# Stop all services
docker-compose -f docker-compose.dev.yml down

# Clean slate (remove volumes)
docker-compose -f docker-compose.dev.yml down -v
```

### Running Tests

```bash
# Backend tests
docker-compose -f docker-compose.dev.yml exec backend pytest

# With coverage
docker-compose -f docker-compose.dev.yml exec backend pytest --cov=app tests/
```

---

## 📚 Documentation

Detailed documentation available in `docs/` directory:

- **[SETUP.md](docs/SETUP.md)**: Detailed setup instructions
- **[API.md](docs/API.md)**: API documentation
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)**: Deployment guide
- **[EVALUATION.md](docs/EVALUATION.md)**: RAGAS & BUS-11 guide
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**: System architecture

---

## 🤝 Contributing

This is an internal BSSN project. For questions or contributions, contact the development team.

---

## 📄 License

Internal Use Only - BSSN (Badan Siber dan Sandi Negara)

---

## 👥 Team

Developed for internal use at BSSN with the following goals:
- Meningkatkan efisiensi dalam mengakses informasi peraturan SPBE
- Memudahkan analisis hasil audit keamanan
- Menyediakan AI assistant yang akurat dan dapat dipercaya

---

## 🔗 Links

- **Internal Wiki**: [Coming Soon]
- **Issue Tracker**: [Coming Soon]
- **Support**: Contact IT Department BSSN

---

<div align="center">

**Built with ❤️ for BSSN**

</div>
