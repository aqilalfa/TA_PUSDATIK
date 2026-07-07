# Draft: Akses Aplikasi dari Jaringan Berbeda

## Requirements (confirmed)
- User ingin menjalankan aplikasi di PC lokal sebagai server.
- Orang lain harus bisa memakai aplikasi tersebut dari jaringan yang berbeda.
- User meminta susunan planning terbaik untuk pendekatan Cloudflare Tunnel dan daftar hal yang perlu dilakukan nantinya.

## Technical Decisions
- Diputuskan: pendekatan utama adalah Cloudflare Tunnel ke frontend production Nginx port 80.
- Aplikasi sebaiknya dijalankan via Docker Compose production, bukan Vite dev server, agar frontend dan backend berada di satu origin melalui Nginx `/api` reverse proxy.

## Research Findings
- Stack terdeteksi: Vue 3 + Vite frontend, FastAPI Python backend, Qdrant, SQLite, Docker Compose.
- `docker-compose.prod.yml` mengekspos frontend Nginx pada host port 80.
- `frontend/nginx.conf` mem-proxy `/api/` ke service backend Docker `http://backend:8000`.
- `docker-compose.dev.yml` mengekspos frontend 5173 dan backend 8000; ini kurang ideal untuk akses lintas jaringan karena konfigurasi dev dan potensi URL localhost.
- `vite.config.js` dev server sudah host `0.0.0.0`, tetapi production lebih tepat untuk akses orang lain.

## Open Questions
- Apakah user sudah punya domain di Cloudflare? Jika belum, plan memakai fallback quick tunnel sementara untuk uji coba dan named tunnel saat domain tersedia.
- Apakah target akses hanya demo terbatas atau dipakai semi-permanen? Default plan: aman untuk demo/semi-permanen terbatas.
- Apakah login/data sensitif aktif? Default plan: jangan expose Qdrant/backend langsung, gunakan HTTPS Cloudflare, aktifkan Cloudflare Access jika user terbatas.

## Scope Boundaries
- INCLUDE: Work plan untuk menjalankan aplikasi di PC lokal sebagai server melalui Cloudflare Tunnel, dengan checklist operasional yang harus dilakukan user nantinya.
- INCLUDE: Validasi Docker production stack, tunnel ke port 80, DNS/domain atau quick tunnel, firewall lokal, CORS/API URL, security guardrails, dan QA dari jaringan luar.
- EXCLUDE: Membuka port router manual, expose Qdrant/Backend langsung ke publik, deploy ke VPS/cloud, atau perubahan besar arsitektur aplikasi.

## Test Strategy Decision
- **Infrastructure exists**: YES (backend pytest, frontend vitest, Docker healthcheck).
- **Automated tests**: Tests-after / verification-after untuk deployment plan; tidak perlu TDD karena fokusnya konfigurasi deployment operasional, bukan fitur kode baru.
- **Agent-Executed QA**: ALWAYS — curl healthcheck, akses frontend via tunnel, API `/api/health`, chat/document smoke test jika data/model tersedia.
