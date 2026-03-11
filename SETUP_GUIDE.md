# 🔧 Setup Infrastructure Guide - SPBE RAG System

**Target:** Setup nvidia-docker, download models, dan start containers  
**Time:** ~1-2 jam (tergantung internet)  
**Status:** Follow checklist di bawah

---

## ✅ CHECKLIST SETUP (Ikuti urutan ini)

### STEP 1: Prepare Documents (5 menit) ⚡ MULAI DARI SINI
**Priority:** HIGH - Bisa dilakukan sambil download models

```bash
# 1. Copy 3 PDF Anda ke folder yang sesuai:

# Jika PDF berisi peraturan/regulasi SPBE:
copy "path\to\your\pdf1.pdf" "D:\aqil\pusdatik\data\documents\peraturan\"

# Jika PDF berisi hasil audit BSSN:
copy "path\to\your\pdf2.pdf" "D:\aqil\pusdatik\data\documents\audit\"

# Jika PDF lain-lain:
copy "path\to\your\pdf3.pdf" "D:\aqil\pusdatik\data\documents\others\"

# Verify files copied:
dir data\documents\peraturan
dir data\documents\audit
dir data\documents\others
```

**✅ Checklist:**
- [ ] 3 PDF sudah di-copy ke data/documents/
- [ ] Verify dengan `dir` command

---

### STEP 2: Download Models (30-60 menit) ⏳ PALING LAMA
**Priority:** HIGH - Bisa berjalan di background

**IMPORTANT:** Script sudah di-update dengan model yang benar!
- ✅ LLM: `bartowski/Qwen2.5-7B-Instruct-GGUF` (Q4_K_M)
- ✅ Embedding: `firqaaa/indo-sentence-bert-base`
- ✅ Reranker: `BAAI/bge-reranker-base`

**Lihat `docs/MODEL_SELECTION_GUIDE.md` untuk detail lengkap!**

**Option A: Menggunakan script otomatis (RECOMMENDED)**
```bash
# 1. Install huggingface-hub
cd D:\aqil\pusdatik\backend
venv\Scripts\pip.exe install huggingface-hub

# 2. Run download script (akan download ~6-7 GB)
venv\Scripts\python.exe scripts\download_models.py

# Output akan seperti:
# Downloading bartowski/Qwen2.5-7B-Instruct-GGUF... (4.37 GB)
# Downloading firqaaa/indo-sentence-bert-base... (400 MB)
# Downloading BAAI/bge-reranker-base... (1 GB)
```

**Option B: Manual download (jika script error)**
```bash
# Install dependencies
venv\Scripts\pip.exe install huggingface-hub

# Download manual via Python:
venv\Scripts\python.exe
```

```python
from huggingface_hub import hf_hub_download, snapshot_download
from pathlib import Path

# Create models directory
Path("models/llm").mkdir(parents=True, exist_ok=True)
Path("models/embeddings").mkdir(parents=True, exist_ok=True)
Path("models/reranker").mkdir(parents=True, exist_ok=True)

# Download Qwen 2.5 7B Instruct Q4_K_M (GGUF)
print("Downloading Qwen 2.5 7B Instruct Q4_K_M...")
hf_hub_download(
    repo_id="bartowski/Qwen2.5-7B-Instruct-GGUF",
    filename="Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    local_dir="models/llm",
    local_dir_use_symlinks=False,
    resume_download=True
)

# Download Indonesian embeddings
print("Downloading Indonesian embeddings...")
snapshot_download(
    repo_id="firqaaa/indo-sentence-bert-base",
    local_dir="models/embeddings/indo-sentence-bert-base",
    local_dir_use_symlinks=False,
    resume_download=True
)

# Download reranker
print("Downloading reranker...")
snapshot_download(
    repo_id="BAAI/bge-reranker-base",
    local_dir="models/reranker/bge-reranker-base",
    local_dir_use_symlinks=False,
    resume_download=True
)

print("✅ All models downloaded!")
exit()
```

**✅ Checklist:**
- [ ] huggingface-hub installed
- [ ] Script download_models.py running (atau manual download)
- [ ] Monitor progress (ini akan lama, bisa sambil lanjut step lain)
- [ ] Models tersimpan di `backend/models/`

**Verify setelah selesai:**
```bash
dir backend\models\llm
# Harus ada file: Qwen2.5-7B-Instruct-Q4_K_M.gguf (~4.37 GB)

dir backend\models\embeddings\indo-sentence-bert-base
# Harus ada folder dengan config.json, pytorch_model.bin, dll

dir backend\models\reranker\bge-reranker-base
# Harus ada folder dengan config.json, pytorch_model.bin, dll
```

---

### STEP 3: Install nvidia-docker Runtime (15 menit) 🔧
**Priority:** HIGH - Diperlukan untuk GPU support

**Untuk Windows dengan Docker Desktop + WSL2:**

```bash
# 1. Buka WSL2 terminal
wsl

# 2. Update WSL2 (dalam WSL2 terminal)
sudo apt-get update

# 3. Add NVIDIA Docker repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 4. Install NVIDIA Container Toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 5. Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker

# 6. Restart Docker (exit WSL dulu, lalu di Windows PowerShell)
exit
```

```powershell
# Di Windows PowerShell (Run as Administrator):
Restart-Service docker

# Atau restart Docker Desktop dari tray icon
```

```bash
# 7. Test GPU dalam Docker (kembali ke Git Bash/terminal biasa)
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Jika berhasil, akan muncul output nvidia-smi dari dalam container
```

**✅ Checklist:**
- [ ] WSL2 updated
- [ ] nvidia-container-toolkit installed
- [ ] Docker restarted
- [ ] Test command berhasil (nvidia-smi muncul dari container)

**Jika error:**
- Pastikan Docker Desktop sudah enable WSL2 backend
- Pastikan GPU driver Windows sudah latest
- Coba restart PC jika perlu

---

### STEP 4: Create .env File (2 menit) 📝
**Priority:** MEDIUM

```bash
# Copy example env file
cd D:\aqil\pusdatik\backend
copy .env.example .env

# Edit .env file (buka dengan notepad):
notepad .env
```

**Minimal configuration di .env:**
```bash
# Model paths (sesuaikan dengan lokasi download)
QWEN_MODEL_PATH=/app/models/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q4_k_m.gguf
EMBEDDING_MODEL_NAME=firqaaa/indo-sentence-bert-base
RERANKER_MODEL_NAME=BAAI/bge-reranker-base

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=document_chunks

# Database
DATABASE_URL=sqlite:///app/data/spbe_rag.db

# GPU
CUDA_VISIBLE_DEVICES=0
```

**✅ Checklist:**
- [ ] .env file created
- [ ] Model paths configured

---

### STEP 5: Build Docker Images (10 menit) 🐳
**Priority:** HIGH - Harus setelah Step 3 (nvidia-docker)

```bash
cd D:\aqil\pusdatik

# Build images (akan compile dan install dependencies)
docker-compose -f docker-compose.dev.yml build

# Output akan show progress untuk:
# - Building backend image
# - Building frontend image
# - Pulling qdrant image

# Tunggu sampai selesai (bisa 10-15 menit pertama kali)
```

**✅ Checklist:**
- [ ] Build process started
- [ ] No errors during build
- [ ] Images created successfully

**Verify:**
```bash
docker images | findstr spbe
# Harus muncul:
# pusdatik-backend
# pusdatik-frontend
```

---

### STEP 6: Start Docker Containers (2 menit) 🚀
**Priority:** HIGH

```bash
# Start all containers
docker-compose -f docker-compose.dev.yml up -d

# Check status
docker-compose -f docker-compose.dev.yml ps

# Harus muncul 3 containers:
# - spbe-backend (running)
# - spbe-frontend (running)
# - qdrant (running)
```

**✅ Checklist:**
- [ ] All containers running
- [ ] No restart loops

**Verify services:**
```bash
# Check backend health
curl http://localhost:8000/api/health

# Check Qdrant
curl http://localhost:6333/collections

# Check frontend (buka browser)
# http://localhost:5173
```

---

### STEP 7: Initialize Database (1 menit) 💾
**Priority:** MEDIUM

```bash
# Run database initialization
docker-compose -f docker-compose.dev.yml exec backend python scripts/init_db.py

# Output:
# ✅ Database initialized
# ✅ Tables created
```

**✅ Checklist:**
- [ ] Database initialized
- [ ] File `backend/data/spbe_rag.db` created

---

### STEP 8: Ingest Documents (5-10 menit) 📄
**Priority:** HIGH - Setelah Step 1 (PDFs ready)

```bash
# Run document ingestion
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/ingest_documents.py --input-dir /app/data/documents

# Output akan show progress:
# Processing peraturan/file1.pdf...
# - OCR detection...
# - Parsing...
# - Chunking...
# - Indexing to Qdrant...
# ✅ Processed 1/3

# Tunggu sampai semua 3 PDF selesai
```

**✅ Checklist:**
- [ ] All 3 PDFs processed
- [ ] No errors
- [ ] Chunks indexed to Qdrant

**Verify:**
```bash
# Check how many chunks indexed
curl http://localhost:6333/collections/document_chunks

# Response should show points_count > 0
```

---

### STEP 9: Build BM25 Index (1 menit) 🔍
**Priority:** MEDIUM

**Option A: Build via script (jika ada)**
```bash
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/build_bm25_index.py
```

**Option B: Build via Python (jika script belum ada)**
```bash
docker-compose -f docker-compose.dev.yml exec backend python

# Dalam Python shell:
from app.database import get_db
from app.models import DocumentChunk
from app.core.rag.hybrid_retriever import HybridRetriever

# Get all chunks from DB
db = next(get_db())
chunks = db.query(DocumentChunk).all()

# Convert to format for indexing
documents = [
    {"chunk_id": c.id, "text": c.text}
    for c in chunks
]

# Build index
retriever = HybridRetriever()
retriever.build_indices(documents)

print(f"✅ BM25 index built with {len(documents)} chunks")
exit()
```

**✅ Checklist:**
- [ ] BM25 index built
- [ ] File `data/bm25_index.pkl` created

---

### STEP 10: Test Full System (5 menit) 🧪
**Priority:** HIGH - Final verification

```bash
# Test retrieval system
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/test_retrieval.py --use-db --compare

# Test dengan query spesifik
docker-compose -f docker-compose.dev.yml exec backend \
  python scripts/test_retrieval.py --use-db --query "Apa itu SPBE?"

# Output harus show:
# ✅ BM25 search: X results
# ✅ Vector search: X results  
# ✅ Hybrid search: X results
```

**✅ Checklist:**
- [ ] BM25 retrieval working
- [ ] Vector retrieval working
- [ ] Hybrid retrieval working
- [ ] Reranker working (dengan GPU)

---

## 🎯 QUICK REFERENCE

### Check Status Anytime
```bash
# Containers
docker-compose -f docker-compose.dev.yml ps

# Logs
docker-compose -f docker-compose.dev.yml logs -f backend

# GPU usage in container
docker-compose -f docker-compose.dev.yml exec backend nvidia-smi

# Collection info
curl http://localhost:6333/collections/document_chunks
```

### Restart if Needed
```bash
# Restart single service
docker-compose -f docker-compose.dev.yml restart backend

# Restart all
docker-compose -f docker-compose.dev.yml restart

# Stop all
docker-compose -f docker-compose.dev.yml down

# Start again
docker-compose -f docker-compose.dev.yml up -d
```

---

## 🐛 Troubleshooting

### nvidia-docker tidak terdeteksi
```bash
# Check Docker config
docker info | grep -i runtime

# Jika tidak ada nvidia runtime:
# - Ulangi Step 3
# - Pastikan restart Docker Desktop
# - Coba restart PC
```

### Model download gagal
```bash
# Check internet connection
# Try manual download per-model:
venv\Scripts\python.exe

from huggingface_hub import snapshot_download
snapshot_download("firqaaa/indo-sentence-bert-base", local_dir="models/embed")
```

### Container tidak start
```bash
# Check logs
docker-compose -f docker-compose.dev.yml logs backend

# Common issues:
# - Port conflict (8000, 6333, 5173)
# - Model path salah di .env
# - nvidia-docker belum ready
```

### Qdrant error
```bash
# Recreate Qdrant volume
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d qdrant
```

---

## ✅ COMPLETION CHECKLIST

**Infrastructure Setup:**
- [ ] Step 1: Documents copied (3 PDFs)
- [ ] Step 2: Models downloaded (~6-7 GB)
- [ ] Step 3: nvidia-docker installed & tested
- [ ] Step 4: .env file configured
- [ ] Step 5: Docker images built
- [ ] Step 6: Containers running
- [ ] Step 7: Database initialized
- [ ] Step 8: Documents ingested
- [ ] Step 9: BM25 index built
- [ ] Step 10: Full system tested

**Verification:**
- [ ] `curl http://localhost:8000/api/health` → OK
- [ ] `curl http://localhost:6333/collections` → document_chunks exists
- [ ] `http://localhost:5173` → Frontend loads
- [ ] Test retrieval script → All methods working
- [ ] GPU working in container → nvidia-smi shows usage

---

## 📞 Jika Ada Masalah

**Tanyakan saya dengan info:**
1. Step mana yang error
2. Error message lengkap
3. Output dari command yang gagal

**Saya akan bantu troubleshoot!**

---

**Estimated Total Time:** 1-2 jam (tergantung internet speed)  
**Bisa dikerjakan sambil saya develop RAG query engine** ✅

**Good luck! 🚀**
