# Docker Usage Guide

Panduan ini adalah referensi resmi Docker untuk kondisi proyek saat ini.

## Mode aktif saat ini

Stack yang sedang dipakai untuk development adalah gabungan:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d
```

Container aktif dari mode ini:

| Service | Container | Port host | Fungsi |
|---|---|---:|---|
| frontend | `spbe-frontend` | `5173` | Vite dev server dengan hot reload |
| backend | `spbe-backend` | `8000` | FastAPI dev server dengan hot reload |
| redis | `spbe-redis` | `6379` | Rate limit, token revocation, security counters |
| qdrant | `spbe-qdrant` | `6333`, `6334` | Vector database |

Gunakan mode ini untuk kerja harian, editing frontend/backend, debugging, dan pengembangan fitur.

## Perintah harian

Jalankan dari root repository.

### Start stack development GPU

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d
```

### Lihat status container

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml ps
```

### Lihat logs semua service

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml logs -f
```

### Lihat logs service tertentu

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml logs -f backend
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml logs -f frontend
```

### Restart service tertentu

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml restart backend
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml restart frontend
```

### Stop stack development

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml down
```

Jangan pakai `down -v` kecuali memang ingin menghapus volume/data container.

### Rebuild setelah dependency berubah

Backend dependency berubah (`backend/requirements*.txt`):

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml build backend
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d backend
```

Frontend dependency berubah (`frontend/package*.json`):

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml build frontend
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d frontend
```

Rebuild semua service:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml build
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d
```

## Hot reload

Mode development memakai bind mount.

Frontend:

- `frontend/src` -> `/app/src`
- `frontend/public` -> `/app/public`
- `frontend/index.html` -> `/app/index.html`
- `frontend/vite.config.js` -> `/app/vite.config.js`

Artinya perubahan di `frontend/src/**` langsung dibaca Vite container dan biasanya reload otomatis di http://localhost:5173.

Backend:

- `backend/app` -> `/app/app`
- `backend/scripts` -> `/app/scripts`
- `backend/tests` -> `/app/tests`

Artinya perubahan di `backend/app/**` langsung dibaca Uvicorn reload.

## URL lokal

| Komponen | URL |
|---|---|
| Frontend dev | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Backend API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/health |
| Qdrant dashboard | http://localhost:6333/dashboard |

## File Docker dan fungsinya

| File | Status | Fungsi |
|---|---|---|
| `docker-compose.dev.yml` | utama | Stack development: frontend Vite, backend FastAPI reload, Redis, Qdrant |
| `docker-compose.gpu.yml` | override aktif | Menambahkan akses NVIDIA GPU untuk backend |
| `docker-compose.prod.yml` | deployment-only | Stack production: frontend nginx port 80, backend tanpa hot reload |
| `docker-compose.cloudflare.yml` | optional | Menambahkan service Cloudflare tunnel |
| `docker-compose.ldap.yml` | test-only | OpenLDAP lokal dan phpLDAPadmin untuk pengujian LDAP |
| `backend/Dockerfile.dev` | dev | Backend development image berbasis NVIDIA CUDA runtime |
| `backend/Dockerfile.prod` | prod | Backend production image berbasis Python slim |
| `frontend/Dockerfile.dev` | dev | Frontend development image dengan Vite |
| `frontend/Dockerfile.prod` | prod | Frontend production build served by nginx |

## Kapan memakai prod compose

Jangan gunakan `docker-compose.prod.yml` untuk kerja harian.

Pakai production compose hanya saat ingin menguji deployment/nginx/port 80:

```powershell
docker compose -f docker-compose.prod.yml up -d
```

Jika butuh GPU di prod:

```powershell
docker compose -f docker-compose.prod.yml -f docker-compose.gpu.yml up -d
```

Catatan penting: saat ini dev dan prod masih berbagi beberapa folder host, seperti `qdrant_storage`, `backend/data`, `backend/models`, dan `logs/backend`. Karena itu, jangan bolak-balik menjalankan dev dan prod tanpa tujuan jelas. Untuk isolation penuh, prod sebaiknya memakai folder data terpisah.

## Cloudflare tunnel

Cloudflare compose adalah add-on. Gunakan bersama base compose.

Dengan production:

```powershell
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml up -d
```

Dengan development, jika memang ingin expose Vite dev server:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml -f docker-compose.cloudflare.yml up -d
```

Pastikan `CLOUDFLARED_TUNNEL_TOKEN` tersedia di environment atau file env yang digunakan.

## LDAP test stack

LDAP stack terpisah untuk pengujian integrasi LDAP:

```powershell
docker compose -f docker-compose.ldap.yml up -d
```

Akses phpLDAPadmin:

```text
http://localhost:6680
```

Jangan gunakan LDAP test stack sebagai production identity provider.

## Container lama yang mungkin muncul

Jika Docker Desktop menampilkan `spbe-frontend-prod` dalam status exited, itu container production lama. Jika tidak sedang menguji production, container tersebut boleh dihapus manual:

```powershell
docker rm spbe-frontend-prod
```

Perintah itu hanya menghapus container stopped, bukan source code dan bukan data volume.

## Troubleshooting cepat

### Port sudah dipakai

```powershell
docker ps -a
netstat -ano | findstr :5173
netstat -ano | findstr :8000
netstat -ano | findstr :6333
```

### Backend tidak healthy

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml logs -f backend
```

### Frontend tidak update setelah edit

Cek apakah stack yang berjalan benar-benar dev:

```powershell
docker inspect spbe-frontend --format "{{ index .Config.Labels \"com.docker.compose.project.config_files\" }}"
```

Harus memuat:

```text
docker-compose.dev.yml,docker-compose.gpu.yml
```

### Dependency frontend/backend berubah tapi container masih error

Rebuild service terkait:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml build frontend
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d frontend
```

atau:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml build backend
docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d backend
```
