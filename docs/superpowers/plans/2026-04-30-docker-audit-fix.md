# Docker Audit & Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix semua critical, moderate, dan best-practice issues di Docker setup agar sistem SPBE RAG berjalan benar di dev dan production.

**Architecture:** Perbaikan dilakukan bottom-up: `.dockerignore` dulu (cegah build lambat), lalu `requirements.txt` (dependency ground truth), lalu `Dockerfile.dev`, lalu `docker-compose.dev.yml`, lalu env files dan vite config, terakhir buat seluruh prod stack.

**Tech Stack:** Docker Compose v3.8, FastAPI/uvicorn, Vue 3/Vite/nginx, Qdrant v1.16.2, NVIDIA CUDA 12.4, Python 3.10, Node 18

---

## File Map

| File | Aksi | Alasan |
|---|---|---|
| `backend/.dockerignore` | Create | Cegah venv (2GB) + models (3GB) masuk build context |
| `frontend/.dockerignore` | Create | Cegah node_modules masuk build context |
| `backend/requirements.txt` | Rewrite | Sync dengan venv aktual; tambah marker-pdf, hapus llama-cpp |
| `backend/Dockerfile.dev` | Modify | Ganti -devel → -runtime, hapus llama-cpp install, ganti CUDA 11.8 → 12.4 |
| `backend/Dockerfile.prod` | Create | Multistage build, tanpa build tools di final image |
| `frontend/Dockerfile.prod` | Create | Build Vue → nginx serve static |
| `frontend/nginx.conf` | Create | SPA routing + API proxy + SSE support |
| `frontend/vite.config.js` | Modify | Proxy target dari env var, bukan hardcoded |
| `docker-compose.dev.yml` | Modify | Fix volume paths, qdrant version, health check, env vars |
| `docker-compose.prod.yml` | Create | Production stack: no hot-reload, resource limits, restart: always |
| `.env.example` | Modify | Tambah VITE_BACKEND_PROXY, perbaiki komentar |
| `.env.docker.example` | Create | Template env untuk Docker (host.docker.internal, service names) |

---

## Task 1: Add .dockerignore Files

**Files:**
- Create: `backend/.dockerignore`
- Create: `frontend/.dockerignore`

- [ ] **Step 1: Buat `backend/.dockerignore`**

```
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.mypy_cache/
data/
*.db
*.pkl
models/
tests/
logs/
*.egg-info/
dist/
build/
.git/
```

- [ ] **Step 2: Buat `frontend/.dockerignore`**

```
node_modules/
dist/
.env
.env.*
*.log
```

- [ ] **Step 3: Verifikasi ukuran build context berkurang**

Jalankan dari root project:
```bash
docker build --no-cache -f backend/Dockerfile.dev backend/ 2>&1 | head -5
```
Expected output baris pertama: `Sending build context to Docker daemon  XX.XXkB` — angkanya harus jauh lebih kecil dari sebelumnya (sebelumnya bisa >1GB).

- [ ] **Step 4: Commit**

```bash
git add backend/.dockerignore frontend/.dockerignore
git commit -m "chore(docker): add .dockerignore to prevent venv/models in build context"
```

---

## Task 2: Regenerate requirements.txt

**Files:**
- Modify: `backend/requirements.txt`

Tujuan: ganti requirements.txt yang sudah tidak akurat dengan versi yang disync dari venv aktual. Packages dev (pytest, black, dll) tetap di `requirements-dev.txt`.

- [ ] **Step 1: Generate freeze dari venv**

```bash
cd backend
venv/Scripts/pip freeze > requirements_freeze.txt
```

- [ ] **Step 2: Tulis `requirements.txt` baru**

Ganti seluruh isi `backend/requirements.txt` dengan konten berikut (difilter dari freeze, hapus dev-only tools):

```
# === Torch (CUDA 12.4) ===
--extra-index-url https://download.pytorch.org/whl/cu124
torch==2.6.0+cu124
torchvision==0.21.0+cu124
torchaudio==2.6.0+cu124

# === Core RAG Framework ===
langchain==1.2.15
langchain-classic==1.0.1
langchain-community==0.4.1
langchain-core==1.2.14
langchain-huggingface==1.2.0
langchain-ollama==1.0.1
langchain-qdrant==1.1.0
langchain-text-splitters==1.1.1
qdrant-client==1.16.2

# === LLM & Embeddings ===
transformers==4.57.6
sentence-transformers==5.2.2
huggingface_hub==0.36.2
safetensors==0.7.0
tokenizers==0.22.2
ollama==0.6.1

# === OCR & PDF ===
paddleocr==3.4.0
paddlepaddle==3.3.0
paddlex==3.4.1
marker-pdf==1.10.2
PyMuPDF==1.26.7
pdfplumber==0.11.9
pdfminer.six==20251230
pdftext==0.6.3
pdf2image==1.17.0
pypdfium2==4.30.0
pytesseract==0.3.10
opencv-python-headless==4.11.0.86
opencv-contrib-python==4.10.0.84
Pillow==10.4.0
surya-ocr==0.17.1

# === API Framework ===
fastapi==0.128.0
uvicorn[standard]==0.40.0
python-multipart==0.0.22
websockets==15.0.1
pydantic==2.12.5
pydantic-settings==2.12.0
starlette==0.50.0

# === Database ===
SQLAlchemy==2.0.46
aiosqlite==0.19.0

# === Search & Retrieval ===
rank-bm25==0.2.2
scikit-learn==1.8.0
scipy==1.17.0
numpy==1.26.4

# === Evaluation ===
ragas==0.2.15
datasets==4.8.4

# === Indonesian NLP ===
Sastrawi==1.0.1
nltk==3.8.1

# === Utilities ===
python-dotenv==1.2.1
loguru==0.7.3
httpx==0.28.1
httpx-sse==0.4.3
pyyaml==6.0.2
python-jose[cryptography]==3.3.0
python-dateutil==2.9.0.post0
psutil==7.2.2
tqdm==4.67.3
requests==2.32.5
filelock==3.20.3
packaging==24.2
typing_extensions==4.15.0
anyio==4.12.1
sniffio==1.3.1
```

- [ ] **Step 3: Hapus file sementara**

```bash
rm backend/requirements_freeze.txt
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "fix(docker): regenerate requirements.txt from live venv - sync actual versions"
```

---

## Task 3: Update backend/Dockerfile.dev

**Files:**
- Modify: `backend/Dockerfile.dev`

Perubahan: ganti base image dari CUDA 11.8 -devel ke CUDA 12.4 -runtime (match dengan torch 2.6.0+cu124), hapus llama-cpp-python install.

- [ ] **Step 1: Tulis ulang `backend/Dockerfile.dev`**

Ganti seluruh isi file dengan:

```dockerfile
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    tesseract-ocr \
    tesseract-ocr-ind \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./

RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install -r requirements.txt && \
    pip3 install -r requirements-dev.txt

COPY ./scripts /app/scripts

RUN mkdir -p /app/app /app/logs /app/models /app/data /app/tests

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]
```

- [ ] **Step 2: Verifikasi syntax Dockerfile valid**

```bash
docker build --no-cache --dry-run -f backend/Dockerfile.dev backend/ 2>&1 | head -10
```

Jika `--dry-run` tidak tersedia di versi Docker Anda, jalankan:
```bash
docker build -f backend/Dockerfile.dev backend/ --target base 2>&1 | head -20
```

Expected: tidak ada syntax error (baris pertama menunjukkan `[+] Building`).

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile.dev
git commit -m "fix(docker): switch to CUDA 12.4 runtime image, remove llama-cpp-python"
```

---

## Task 4: Fix docker-compose.dev.yml

**Files:**
- Modify: `docker-compose.dev.yml`

Perubahan: fix volume paths, qdrant version, hapus env vars yang tidak relevan, tambah health check backend, fix depends_on frontend.

- [ ] **Step 1: Tulis ulang `docker-compose.dev.yml`**

Ganti seluruh isi file dengan:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:v1.16.2
    container_name: spbe-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
    restart: unless-stopped
    networks:
      - spbe-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: spbe-backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/models:/app/models:ro
      - ./backend/data:/app/data
      - ./logs/backend:/app/logs
      - ./backend/app:/app/app
      - ./backend/scripts:/app/scripts
      - ./backend/tests:/app/tests
      - /app/app/__pycache__
    environment:
      - QDRANT_URL=http://qdrant:6333
      - QDRANT_COLLECTION=document_chunks
      - EMBEDDING_MODEL=firqaaa/indo-sentence-bert-base
      - EMBEDDING_CACHE_DIR=/app/models/embeddings
      - EMBEDDING_DEVICE=cpu
      - RERANKER_MODEL=BAAI/bge-reranker-base
      - RERANKER_CACHE_DIR=/app/models/reranker
      - RERANKER_DEVICE=cpu
      - RERANKER_TOP_K=10
      - DATABASE_URL=sqlite:////app/data/spbe_rag.db
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - CORS_ORIGINS=${CORS_ORIGINS:-http://localhost,http://localhost:80,http://localhost:5173,http://localhost:3000}
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
      - ENVIRONMENT=development
      - DEBUG=true
      - LOG_LEVEL=DEBUG
      - LOG_DIR=/app/logs
      - RELOAD=true
      - CUDA_VISIBLE_DEVICES=0
    depends_on:
      qdrant:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - spbe-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: spbe-frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/public:/app/public
      - ./frontend/index.html:/app/index.html
      - ./frontend/vite.config.js:/app/vite.config.js
      - /app/node_modules
    environment:
      - VITE_API_URL=${VITE_API_URL:-http://localhost:8000}
      - VITE_BACKEND_PROXY=http://backend:8000
      - NODE_ENV=development
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - spbe-network
    command: npm run dev -- --host 0.0.0.0

networks:
  spbe-network:
    driver: bridge
```

- [ ] **Step 2: Verifikasi syntax compose valid**

```bash
docker compose -f docker-compose.dev.yml config 2>&1 | head -20
```

Expected: output YAML tanpa error `validating` atau `unsupported`.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.dev.yml
git commit -m "fix(docker): fix volume paths, qdrant v1.16.2, add backend health check"
```

---

## Task 5: Create .env.docker.example dan Update .env.example

**Files:**
- Create: `.env.docker.example`
- Modify: `.env.example`

- [ ] **Step 1: Buat `.env.docker.example`**

```env
# =============================================================================
# SPBE RAG System - Docker Environment Configuration
# =============================================================================
# Copy file ini ke .env.docker untuk digunakan dengan docker-compose
# JANGAN gunakan .env.example biasa untuk Docker — path dan hostname berbeda!

# =============================================================================
# QDRANT — gunakan nama service Docker, BUKAN localhost
# =============================================================================
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=document_chunks

# =============================================================================
# OLLAMA — gunakan host.docker.internal agar container bisa akses host
# =============================================================================
OLLAMA_BASE_URL=http://host.docker.internal:11434

# =============================================================================
# DATABASE — path di dalam container
# =============================================================================
DATABASE_URL=sqlite:////app/data/spbe_rag.db

# =============================================================================
# EMBEDDING & RERANKER
# =============================================================================
EMBEDDING_MODEL=firqaaa/indo-sentence-bert-base
EMBEDDING_CACHE_DIR=/app/models/embeddings
EMBEDDING_DEVICE=cpu
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_CACHE_DIR=/app/models/reranker
RERANKER_DEVICE=cpu
RERANKER_TOP_K=10

# =============================================================================
# API
# =============================================================================
API_HOST=0.0.0.0
API_PORT=8000
# Tambahkan IP PC jika akses dari laptop lain, misal: http://192.168.1.10:5173
CORS_ORIGINS=http://localhost,http://localhost:80,http://localhost:5173

# =============================================================================
# FRONTEND
# =============================================================================
# VITE_API_URL: diakses oleh BROWSER (bukan container) — tetap localhost
VITE_API_URL=http://localhost:8000
# VITE_BACKEND_PROXY: digunakan Vite dev server proxy di dalam container
VITE_BACKEND_PROXY=http://backend:8000

# =============================================================================
# LOGGING & ENVIRONMENT
# =============================================================================
LOG_LEVEL=INFO
LOG_DIR=/app/logs
ENVIRONMENT=development
DEBUG=false
RELOAD=false

# =============================================================================
# CUDA
# =============================================================================
CUDA_VISIBLE_DEVICES=0
OCR_USE_GPU=false
```

- [ ] **Step 2: Tambahkan `VITE_BACKEND_PROXY` ke `.env.example`**

Buka `.env.example`, cari bagian `# FRONTEND` dan ganti isinya dengan:

```env
# =============================================================================
# FRONTEND
# =============================================================================
# Untuk akses dari laptop lain, ganti dengan IP PC: http://192.168.1.10:8000
VITE_API_URL=http://localhost:8000
# Untuk Docker: set ke http://backend:8000 (gunakan .env.docker.example)
VITE_BACKEND_PROXY=http://localhost:8000
NODE_ENV=development
```

- [ ] **Step 3: Commit**

```bash
git add .env.docker.example .env.example
git commit -m "chore(docker): add .env.docker.example with correct Docker hostnames"
```

---

## Task 6: Fix vite.config.js Proxy

**Files:**
- Modify: `frontend/vite.config.js`

Masalah: proxy target hardcoded ke `http://backend:8000` — ini gagal saat dev lokal tanpa Docker.

- [ ] **Step 1: Update `frontend/vite.config.js`**

Ganti seluruh isi file dengan:

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  test: {
    environment: 'happy-dom',
    globals: true,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_PROXY ?? 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

- [ ] **Step 2: Verifikasi dev lokal masih bisa akses API**

```bash
cd frontend
npm run dev
```

Buka `http://localhost:5173` di browser. Pastikan tidak ada error "proxy target" di terminal Vite.

- [ ] **Step 3: Commit**

```bash
git add frontend/vite.config.js
git commit -m "fix(frontend): use VITE_BACKEND_PROXY env var for dev server proxy target"
```

---

## Task 7: Create docker-compose.prod.yml

**Files:**
- Create: `docker-compose.prod.yml`

- [ ] **Step 1: Buat `docker-compose.prod.yml`**

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:v1.16.2
    container_name: spbe-qdrant-prod
    volumes:
      - ./qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
    restart: always
    networks:
      - spbe-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: spbe-backend-prod
    env_file:
      - .env.docker
    environment:
      - DEBUG=false
      - RELOAD=false
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - QDRANT_URL=http://qdrant:6333
      - DATABASE_URL=sqlite:////app/data/spbe_rag.db
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
    volumes:
      - ./backend/models:/app/models:ro
      - ./backend/data:/app/data
      - ./logs/backend:/app/logs
    depends_on:
      qdrant:
        condition: service_healthy
    restart: always
    networks:
      - spbe-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    container_name: spbe-frontend-prod
    ports:
      - "80:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: always
    networks:
      - spbe-network

networks:
  spbe-network:
    driver: bridge
```

- [ ] **Step 2: Verifikasi syntax valid**

```bash
docker compose -f docker-compose.prod.yml config 2>&1 | head -20
```

Expected: YAML output tanpa error.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat(docker): add docker-compose.prod.yml for production deployment"
```

---

## Task 8: Create backend/Dockerfile.prod

**Files:**
- Create: `backend/Dockerfile.prod`

Multistage: stage builder install deps, stage runtime hanya copy hasil — tidak ada cmake/git di final image.

- [ ] **Step 1: Buat `backend/Dockerfile.prod`**

```dockerfile
# Stage 1: Builder — install semua Python dependencies
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    git \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt ./
RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir -r requirements.txt

# Stage 2: Runtime — image ringan tanpa build tools
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    curl \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    tesseract-ocr \
    tesseract-ocr-ind \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages dari builder
COPY --from=builder /usr/local/lib/python3.10/dist-packages /usr/local/lib/python3.10/dist-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

# Copy source code (tidak di-mount, di-bake ke image)
COPY ./app /app/app
COPY ./scripts /app/scripts

RUN mkdir -p /app/logs /app/models /app/data

EXPOSE 8000

# Production: 2 workers, tanpa --reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/Dockerfile.prod
git commit -m "feat(docker): add backend/Dockerfile.prod with multistage build"
```

---

## Task 9: Create frontend/Dockerfile.prod dan nginx.conf

**Files:**
- Create: `frontend/Dockerfile.prod`
- Create: `frontend/nginx.conf`

- [ ] **Step 1: Buat `frontend/nginx.conf`**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback — semua route dikembalikan ke index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API ke backend service
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE (Server-Sent Events) — wajib untuk chat streaming
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        chunked_transfer_encoding on;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;
}
```

- [ ] **Step 2: Buat `frontend/Dockerfile.prod`**

```dockerfile
# Stage 1: Build Vue app
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

# Build untuk production (output ke /app/dist)
RUN npm run build

# Stage 2: Serve via nginx
FROM nginx:alpine

# Copy built app
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile.prod frontend/nginx.conf
git commit -m "feat(docker): add frontend Dockerfile.prod with nginx + SSE proxy config"
```

---

## Task 10: Verifikasi Dev Stack End-to-End

Pastikan semua fix bekerja bersama sebelum dinyatakan selesai.

- [ ] **Step 1: Buat `.env.docker` dari template**

```bash
cp .env.docker.example .env.docker
```

Pastikan `.env.docker` ada di `.gitignore` (tambahkan jika belum):

```bash
grep ".env.docker" .gitignore || echo ".env.docker" >> .gitignore
```

- [ ] **Step 2: Pastikan Ollama berjalan di host**

```bash
curl http://localhost:11434/api/tags 2>&1 | head -5
```

Expected: JSON response dengan daftar model. Jika gagal, jalankan Ollama dulu.

- [ ] **Step 3: Jalankan dev stack**

```bash
docker compose -f docker-compose.dev.yml up --build 2>&1 | tee logs/docker-dev-build.log
```

Build pertama akan lama (~10-20 menit) karena download CUDA image dan install packages. Tunggu hingga muncul:
```
spbe-backend  | INFO:     Application startup complete.
```

- [ ] **Step 4: Verifikasi Qdrant**

```bash
curl http://localhost:6333/healthz
```

Expected: `{"title":"qdrant - vector search engine","version":"...","commit":"..."}`

- [ ] **Step 5: Verifikasi Backend health**

```bash
curl http://localhost:8000/api/health/
```

Expected: JSON dengan `status: "healthy"` atau `"ok"`.

- [ ] **Step 6: Verifikasi database terhubung (bukan kosong)**

```bash
curl http://localhost:8000/api/documents/ 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Dokumen: {len(d.get(\"documents\",[]))} dokumen')"
```

Expected: `Dokumen: 7 dokumen` (bukan 0 — ini membuktikan mount data benar).

- [ ] **Step 7: Verifikasi BM25 index loaded**

```bash
docker logs spbe-backend 2>&1 | grep -i "bm25\|BM25"
```

Expected: baris log yang menunjukkan BM25 index berhasil di-load (bukan error).

- [ ] **Step 8: Verifikasi Frontend**

Buka `http://localhost:5173` di browser. Pastikan:
- Halaman Home tampil dengan data (jumlah dokumen, status backend)
- Chat bisa dikirim dan streaming bekerja
- Tidak ada error CORS di browser console

- [ ] **Step 9: Commit final verification**

```bash
git add .gitignore
git commit -m "chore: add .env.docker to .gitignore"
```

---

## Catatan Penting untuk Production Deployment

Sebelum menjalankan `docker-compose.prod.yml`:

1. **Buat `.env.docker`** dari `.env.docker.example` dan isi semua variabel
2. **Pastikan `./logs/backend/` ada** — `mkdir -p logs/backend`
3. **Nginx port 80** — pastikan port 80 tidak dipakai proses lain di server
4. **Ollama di server** — jika deploy ke server lain, pastikan Ollama berjalan di server tersebut
5. **GPU driver** — server harus punya NVIDIA Container Toolkit (`nvidia-ctk`) terinstall

Command production:
```bash
cp .env.docker.example .env.docker
# Edit .env.docker sesuai server
docker compose -f docker-compose.prod.yml up --build -d
```
