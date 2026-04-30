# Docker Setup Audit & Fix — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all critical, moderate, and best-practice issues found in the Docker setup so the SPBE RAG system can be reliably run in both development and production modes.

**Architecture:** Fix data volume paths, regenerate requirements.txt from the live venv, restructure Dockerfiles, split dev/prod compose files, add health checks and .dockerignore.

**Tech Stack:** Docker Compose, FastAPI/uvicorn, Vue 3/Vite/nginx, Qdrant v1.16.2, NVIDIA CUDA 11.8

---

## Findings Summary

### 🔴 Critical (Docker fails or corrupts data)

| # | Issue | Root Cause |
|---|---|---|
| 1 | `./database:/app/database` mounts empty folder | DB is at `backend/data/spbe_rag.db`, not root `database/` |
| 2 | `./data:/app/data` mounts wrong data dir | BM25 index, marker output, documents are in `backend/data/` |
| 3 | `requirements.txt` has wrong versions | Written manually, never synced with live venv |
| 4 | `marker-pdf==1.10.2` missing from requirements.txt | App uses it actively for PDF→Markdown conversion |
| 5 | `paddlepaddle-gpu==2.6.0` in requirements but not installed | Actual: `paddlepaddle==3.3.0` (non-gpu package name) |

### 🟡 Moderate (runs but incorrectly)

| # | Issue | Root Cause |
|---|---|---|
| 6 | No `.env` file exists | Only `.env.example`, which has wrong `OLLAMA_BASE_URL=http://localhost:11434` for Docker |
| 7 | `vite.config.js` proxy hardcoded to `http://backend:8000` | Breaks local dev without Docker |
| 8 | `qdrant-client==1.16.2` vs server `v1.12.0` | Image version not updated when client was upgraded |
| 9 | `MODEL_PATH` env var references GGUF but app uses Ollama | Legacy config never cleaned up |
| 10 | Frontend `depends_on: backend` without health check | Frontend starts before backend finishes loading model |

### 🔵 Best Practice (production)

| # | Issue | Fix |
|---|---|---|
| 11 | Dockerfile uses `-devel` CUDA image (~5GB) | Switch to `-runtime` (~2GB) for dev, multistage for prod |
| 12 | `llama-cpp-python` still in requirements | Remove — app uses Ollama |
| 13 | No `docker-compose.prod.yml` | Create with nginx, no hot-reload, resource limits |
| 14 | No `Dockerfile.prod` for backend/frontend | Create multistage builds |
| 15 | No `.dockerignore` | `venv/` and `models/` copied into build context (2GB+ wasted) |
| 16 | No backend health check | Add `/api/health/` check with 60s start_period |

---

## File Structure After Fix

```
/
├── docker-compose.dev.yml       # updated
├── docker-compose.prod.yml      # NEW
├── .env.example                 # updated (local dev)
├── .env.docker.example          # NEW (Docker env template)
├── backend/
│   ├── Dockerfile.dev           # updated (runtime image, no llama-cpp)
│   ├── Dockerfile.prod          # NEW (multistage)
│   ├── .dockerignore            # NEW
│   ├── requirements.txt         # regenerated from live venv
│   └── data/                   # ← correct data dir (mounted in Docker)
│       ├── spbe_rag.db
│       ├── bm25_index.pkl
│       ├── marker_output/
│       └── documents/
└── frontend/
    ├── Dockerfile.dev           # unchanged
    ├── Dockerfile.prod          # NEW (nginx)
    ├── .dockerignore            # NEW
    ├── nginx.conf               # NEW
    └── vite.config.js           # updated (env-based proxy)
```

---

## Section 1 — Volume & Path Architecture

### `docker-compose.dev.yml` volume changes

**Before (broken):**
```yaml
volumes:
  - ./data:/app/data
  - ./database:/app/database
```

**After (correct):**
```yaml
volumes:
  - ./backend/data:/app/data
  # ./database removed entirely
```

### `DATABASE_URL` change
```yaml
# Before:
DATABASE_URL: sqlite:////app/database/spbe_rag.db

# After:
DATABASE_URL: sqlite:////app/data/spbe_rag.db
```

No files need to be moved — only the compose mount path changes.

---

## Section 2 — Requirements & Dockerfile

### `requirements.txt` — key changes

The file is regenerated from the live venv using `pip freeze`, then trimmed to remove test/dev packages (those stay in `requirements-dev.txt`). Key differences from current file:

| Package | Old | New |
|---|---|---|
| `paddleocr` | `2.7.0` | `3.4.0` |
| `paddlepaddle-gpu` | `2.6.0` | removed |
| `paddlepaddle` | missing | `3.3.0` |
| `qdrant-client` | `1.7.1` | `1.16.2` |
| `torch` | `2.1.0` | `2.6.0+cu124` |
| `marker-pdf` | missing | `1.10.2` |
| `llama-cpp-python` | `0.2.55` | removed |
| `transformers` | `4.36.0` | pinned to actual |

### `backend/Dockerfile.dev` changes

```dockerfile
# Before:
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04
RUN CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip3 install llama-cpp-python==0.2.55 && \
    pip3 install -r requirements.txt

# After:
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install -r requirements.txt
# llama-cpp-python removed entirely
```

### `backend/Dockerfile.prod` — new multistage

```dockerfile
# Stage 1: builder
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04 AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --target=/build/packages

# Stage 2: runtime
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
COPY --from=builder /build/packages /usr/local/lib/python3.10/dist-packages
COPY ./app /app/app
COPY ./scripts /app/scripts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### `frontend/Dockerfile.prod` — new nginx-based

```dockerfile
# Stage 1: build
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### `backend/.dockerignore` — new

```
venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
data/
*.db
*.pkl
models/
tests/
```

### `frontend/.dockerignore` — new

```
node_modules/
dist/
.env*
```

---

## Section 3 — Environment & Configuration

### `.env.docker.example` — new file

Key differences from `.env.example`:

```env
# Ollama: use host.docker.internal, NOT localhost
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Qdrant: use service name
QDRANT_URL=http://qdrant:6333

# Database: correct container path
DATABASE_URL=sqlite:////app/data/spbe_rag.db

# Frontend: browser accesses backend via exposed port
VITE_API_URL=http://localhost:8000

# Vite proxy: uses service name inside container
VITE_BACKEND_PROXY=http://backend:8000

# Production: flip these
DEBUG=false
RELOAD=false
ENVIRONMENT=production
```

### `vite.config.js` proxy fix

```js
// Before (hardcoded, breaks local dev):
proxy: {
  '/api': { target: 'http://backend:8000', changeOrigin: true }
}

// After (env-based, works both local and Docker):
proxy: {
  '/api': {
    target: process.env.VITE_BACKEND_PROXY ?? 'http://localhost:8000',
    changeOrigin: true
  }
}
```

### `.env.example` update

Add missing vars and fix comment for Docker users:
```env
# LOCAL dev (no Docker): use localhost
OLLAMA_BASE_URL=http://localhost:11434
# For Docker: use http://host.docker.internal:11434 in .env.docker

VITE_BACKEND_PROXY=http://localhost:8000
```

---

## Section 4 — Dev vs Prod Compose Split

### `docker-compose.dev.yml` — full updated service definitions

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:v1.16.2        # UPDATED from v1.12.0
    # ... rest unchanged

  backend:
    volumes:
      - ./backend/data:/app/data        # FIXED
      - ./backend/models:/app/models:ro
      - ./backend/app:/app/app
      - ./backend/scripts:/app/scripts
      - ./logs/backend:/app/logs
      # removed: ./database, ./data
    environment:
      DATABASE_URL: sqlite:////app/data/spbe_rag.db   # FIXED
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
      # removed: MODEL_PATH, MODEL_N_GPU_LAYERS (Ollama handles LLM)
    depends_on:
      qdrant:
        condition: service_healthy
    healthcheck:                         # NEW
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  frontend:
    environment:
      VITE_BACKEND_PROXY: http://backend:8000   # NEW
    depends_on:
      backend:
        condition: service_healthy       # FIXED: was just depends_on
```

### `docker-compose.prod.yml` — new file

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:v1.16.2
    volumes:
      - ./qdrant_storage:/qdrant/storage
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
    env_file: .env.docker
    environment:
      DEBUG: "false"
      RELOAD: "false"
      ENVIRONMENT: production
      LOG_LEVEL: INFO
    volumes:
      - ./backend/data:/app/data
      - ./backend/models:/app/models:ro
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

### `frontend/nginx.conf` — new file

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API to backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
    }
}
```

---

## Section 5 — Health Checks & Network

### Backend health check
Uses existing `/api/health/` endpoint. `start_period: 60s` gives backend time to load embedding and reranker models before health checks begin.

### Startup dependency chain
```
qdrant (healthy) → backend (healthy) → frontend (start)
```

This prevents the "API not found" error that occurs when frontend starts before backend finishes initializing.

### `.dockerignore` impact
Without `.dockerignore`, `docker build` copies the entire `backend/` context including:
- `venv/` (~2GB Python packages)
- `models/` (~3GB model files)
- `data/` (database, BM25 index)

With `.dockerignore`, build context drops from ~6GB to ~50MB, making builds dramatically faster.

---

## What Is NOT Changed

- `backend/app/` source code — no code changes
- `frontend/src/` — no logic changes (only `vite.config.js`)
- `backend/app/config.py` — already reads from env vars correctly
- Qdrant collection structure — data is preserved via volume mount
- Ollama setup — runs on host, accessed via `host.docker.internal`
- All API routes, RAG pipeline, session management

---

## Verification Checklist

**Dev:**
- [ ] `docker-compose -f docker-compose.dev.yml up --build` completes without error
- [ ] Backend health: `curl http://localhost:8000/api/health/` → `200 OK`
- [ ] Qdrant: `curl http://localhost:6333/healthz` → `200 OK`
- [ ] Frontend loads at `http://localhost:5173`
- [ ] Chat works, database shows existing documents (not empty)
- [ ] BM25 search works (index loaded from `backend/data/bm25_index.pkl`)

**Prod:**
- [ ] `docker-compose -f docker-compose.prod.yml up --build` completes
- [ ] Frontend loads at `http://localhost:80`
- [ ] SSE streaming works through nginx proxy
- [ ] No source code exposed in container

**Local dev (no Docker):**
- [ ] `npm run dev` in frontend works (proxy to `localhost:8000`)
- [ ] Backend uvicorn runs normally
