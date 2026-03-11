# QUICKSTART - SPBE RAG System

Panduan cepat untuk memulai development SPBE RAG System.

## ✅ Status Saat Ini

**Phase 0: Project Setup - COMPLETED** ✅

Skeleton lengkap telah dibuat dengan 80+ files termasuk:
- ✅ Docker configuration (docker-compose, Dockerfiles)
- ✅ Backend skeleton (FastAPI, database, API routes)  
- ✅ Frontend skeleton (Vue.js, components, views)
- ✅ Model download script
- ✅ Initialization scripts
- ✅ Complete documentation

## 🚀 Langkah Selanjutnya

### Langkah 1: Install NVIDIA Docker (WAJIB)

Karena belum ada nvidia-docker runtime di PC Anda, install terlebih dahulu:

**Windows dengan WSL2:**
```powershell
# 1. Install WSL2
wsl --install

# 2. Di dalam WSL2 Ubuntu, jalankan:
```

**Di WSL2 Ubuntu atau Linux native:**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Verify GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

Anda harus melihat informasi GTX 1650 di output.

### Langkah 2: Download Models

```bash
cd backend

# Install dependencies minimal untuk download script
pip install huggingface-hub loguru

# Download models (~6-7 GB, bisa займает 30-60 menit tergantung internet)
python scripts/download_models.py

# Verify download berhasil
python scripts/download_models.py --verify
```

Expected output:
```
✓ LLM         : Present (models/llm/qwen-2.5-7b-instruct-q4_k_m.gguf)
✓ EMBEDDING   : Present (models/embeddings/indo-sentence-bert-base/)
✓ RERANKER    : Present (models/reranker/bge-reranker-base/)
```

### Langkah 3: Copy Environment Config

```bash
# Kembali ke root directory
cd ..

# Copy .env template
cp .env.example .env

# Edit jika perlu (defaults sudah OK untuk development)
# nano .env
```

### Langkah 4: Copy Dokumen PDF Anda

```bash
# Copy 3 dokumen PDF ke data/documents/
# Contoh:
cp /path/to/dokumen1.pdf data/documents/peraturan/
cp /path/to/dokumen2.pdf data/documents/audit/
cp /path/to/dokumen3.pdf data/documents/others/

# Verify
ls -lh data/documents/*/
```

### Langkah 5: Build & Run

```bash
# Build semua containers (pertama kali займет ~10-15 menit)
docker-compose -f docker-compose.dev.yml build

# Start services
docker-compose -f docker-compose.dev.yml up -d

# Watch logs untuk memastikan semua jalan
docker-compose -f docker-compose.dev.yml logs -f
```

Tunggu hingga melihat:
```
spbe-backend    | ✓ Database initialized
spbe-backend    | ✓ Application startup complete
spbe-qdrant     | Health check passed
spbe-frontend   | VITE ready in XXXms
```

### Langkah 6: Akses Aplikasi

Buka browser dan akses:

- **Frontend**: http://localhost:5173
- **Backend API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health
- **Qdrant Dashboard**: http://localhost:6333/dashboard

### Langkah 7: Test API

```bash
# Test health endpoint
curl http://localhost:8000/api/health

# Expected output:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "environment": "development",
#   "services": {
#     "database": "healthy",
#     "qdrant": "healthy",
#     "llm_model": "present"
#   }
# }
```

## 🎯 Apa yang Sudah Bisa Dilakukan Sekarang?

✅ **Backend API:**
- `/api/health` - Check system health
- `/api/users` - User management (create, get)
- `/api/sessions` - Session management (create, list)
- `/api/chat` - Chat endpoint (placeholder, akan diintegrasikan dengan RAG)
- `/api/documents` - Document upload (placeholder, akan diintegrasikan dengan OCR)

✅ **Frontend:**
- Home page dengan system status
- Navigation (Home, Chat, Documents)
- Basic UI components

⚠️ **Belum Berfungsi (Coming Soon):**
- OCR processing (Week 1-2)
- RAG pipeline (Week 2-4)
- Actual chat with LLM (Week 4)
- Document ingestion & processing (Week 2)
- Agentic AI (Week 9-10)
- Evaluation (Week 11)

## 📅 Development Timeline

**SEKARANG: Week 0 DONE ✅**

**NEXT: Week 1-2 - OCR & Document Ingestion**
- Implement PaddleOCR pipeline
- Create adaptive parsers (peraturan vs audit)
- Test dengan 3 dokumen Anda
- Implement chunking & metadata extraction

Lihat README.md untuk roadmap lengkap 12 minggu.

## 💻 Development Tips

### Hot-Reload Aktif

File yang Anda edit akan otomatis reload:

**Backend:**
```bash
# Edit file di backend/app/
# Uvicorn auto-reload secara otomatis
# Lihat perubahan di logs
docker-compose -f docker-compose.dev.yml logs -f backend
```

**Frontend:**
```bash
# Edit file di frontend/src/
# Browser auto-refresh via Vite HMR
# Langsung terlihat di http://localhost:5173
```

### Common Issues & Solutions

**Issue: Port sudah dipakai**
```bash
# Check port yang dipakai
netstat -ano | findstr :8000
netstat -ano | findstr :5173
netstat -ano | findstr :6333

# Stop service yang conflict atau ubah port di docker-compose.dev.yml
```

**Issue: GPU tidak terdeteksi**
```bash
# Verify nvidia-docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Jika error, reinstall nvidia-container-toolkit
```

**Issue: Model download gagal**
```bash
# Retry dengan force
python scripts/download_models.py --force

# Atau download manual dari HuggingFace
```

**Issue: Container crash**
```bash
# Check logs
docker-compose -f docker-compose.dev.yml logs backend

# Rebuild
docker-compose -f docker-compose.dev.yml build backend --no-cache
docker-compose -f docker-compose.dev.yml up -d backend
```

## 📚 Next Steps After Setup

1. **Familiarize dengan codebase:**
   - Explore `backend/app/` struktur
   - Baca API docs di http://localhost:8000/docs
   - Review frontend components di `frontend/src/`

2. **Start Development:**
   - Lihat TODO list di README.md
   - Mulai dari Week 1: OCR Pipeline
   - Follow development roadmap

3. **Join Development:**
   - Create feature branch
   - Make changes dengan hot-reload
   - Test changes
   - Commit & push

## 🆘 Butuh Bantuan?

- **Documentation**: Lihat `docs/` directory
- **API Reference**: http://localhost:8000/docs
- **Issues**: Check console logs
- **Support**: Contact development team

---

**Happy Coding! 🚀**

Skeleton lengkap sudah ready, tinggal lanjut ke implementasi OCR dan RAG pipeline!
