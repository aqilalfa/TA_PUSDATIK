# Cloudflare Tunnel Deployment Guide

Panduan ini menjalankan aplikasi SPBE RAG di PC lokal sebagai server, lalu mengekspos frontend production melalui Cloudflare Tunnel.

## Arsitektur

```text
User luar jaringan
  -> HTTPS Cloudflare
  -> Cloudflare Tunnel
  -> PC lokal
  -> frontend nginx container port 80
  -> /api proxy ke backend FastAPI container
  -> Qdrant + SQLite tetap internal Docker
```

Hanya frontend nginx yang diekspos melalui tunnel. Backend (`8000`) dan Qdrant (`6333`) tidak perlu dibuka ke publik.

## File yang dipakai

- `docker-compose.prod.yml` — stack production aplikasi.
- `docker-compose.cloudflare.yml` — service `cloudflared` untuk tunnel.
- `.env.docker` — konfigurasi aplikasi production.
- `.env.cloudflare` — token rahasia tunnel Cloudflare.
- `frontend/nginx.conf` — reverse proxy `/api` ke backend.

## Persiapan sekali saja

### 1. Buat environment production

Copy template:

```bash
copy .env.docker.example .env.docker
copy .env.cloudflare.example .env.cloudflare
```

Pastikan `VITE_API_URL` di `.env.docker` dikosongkan untuk deployment Cloudflare Tunnel:

```env
VITE_API_URL=
```

Dengan nilai kosong, frontend otomatis memakai origin saat ini, misalnya:

```text
https://spbe-rag.example.com/api/health
```

bukan `localhost` milik komputer pengguna.

### 2. Buat tunnel di Cloudflare

Di Cloudflare Zero Trust:

1. Buka **Networks > Tunnels**.
2. Pilih **Create a tunnel**.
3. Pilih connector **Docker**.
4. Copy token tunnel.
5. Masukkan token ke `.env.cloudflare`:

```env
CLOUDFLARED_TUNNEL_TOKEN=isi-token-dari-cloudflare
```

### 3. Tambahkan Public Hostname

Di tunnel yang sama, tambahkan Public Hostname:

```text
Subdomain: spbe-rag
Domain: domain-anda.com
Service Type: HTTP
URL: http://frontend:80
```

Karena `cloudflared` berjalan di network Docker yang sama, hostname service Docker `frontend` bisa dipakai.

## Menjalankan aplikasi

Jalankan dari root repository:

```bash
docker compose \
  --env-file .env.docker \
  --env-file .env.cloudflare \
  -f docker-compose.prod.yml \
  -f docker-compose.cloudflare.yml \
  up -d --build
```

Untuk melihat status:

```bash
docker compose \
  --env-file .env.docker \
  --env-file .env.cloudflare \
  -f docker-compose.prod.yml \
  -f docker-compose.cloudflare.yml \
  ps
```

Untuk melihat log tunnel:

```bash
docker logs -f spbe-cloudflared
```

## Verifikasi

### Lokal di PC server

Buka:

```text
http://localhost
http://localhost/api/health
```

### Dari jaringan luar

Gunakan HP dengan paket data, bukan Wi-Fi yang sama, lalu buka:

```text
https://spbe-rag.domain-anda.com
https://spbe-rag.domain-anda.com/api/health
```

Checklist berhasil:

- Halaman frontend terbuka.
- Login berjalan.
- `/api/health` mengembalikan respons sehat.
- Chat/streaming response berjalan.
- Dokumen/citation/PDF endpoint berjalan jika fitur itu dipakai.

## Security checklist

- Jangan expose port `8000` backend ke internet.
- Jangan expose port `6333` Qdrant ke internet.
- Jangan commit `.env.cloudflare`.
- Ganti password user default sebelum digunakan orang lain.
- Jika hanya user tertentu yang boleh akses, aktifkan **Cloudflare Access** untuk hostname ini.
- Pastikan PC server selalu menyala dan Docker Desktop auto-start jika ingin layanan selalu tersedia.

## Stop / restart

Stop semua service:

```bash
docker compose \
  --env-file .env.docker \
  --env-file .env.cloudflare \
  -f docker-compose.prod.yml \
  -f docker-compose.cloudflare.yml \
  down
```

Restart:

```bash
docker compose \
  --env-file .env.docker \
  --env-file .env.cloudflare \
  -f docker-compose.prod.yml \
  -f docker-compose.cloudflare.yml \
  up -d --build
```
