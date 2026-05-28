# OWASP API Security JWT & Rate Limiting Report

**Date**: 2026-05-27  
**Project**: SPBE RAG System PUSDATIK BSSN  
**Scope**: JWT authentication security testing, token lifecycle validation, failed-login rate limiting, and request flood/load-test preparation.

## Executive Summary

Implementasi terbaru menambahkan cakupan pengujian keamanan API yang lebih dekat dengan praktik OWASP API Security untuk area autentikasi JWT. Pengujian sekarang mencakup penolakan token dengan manipulasi header `alg: none`, token dengan payload/signature yang dimodifikasi, token malformed, token expired, token tanpa required claims, dan token yang sudah di-revoke/blacklist setelah logout.

Selain itu, endpoint login sekarang memiliki mekanisme rate limiting untuk percobaan login gagal berulang. Setelah 5 percobaan gagal dalam window 60 detik untuk kombinasi `client_ip:username`, request berikutnya ditolak dengan HTTP `429 Too Many Requests` dan header `Retry-After`. Script k6 juga ditambahkan untuk mendukung simulasi request flood pada endpoint auth dan chatbot.

## OWASP-Oriented Coverage Matrix

| Area Evaluasi | Status | Bukti Implementasi | Catatan |
|---|---:|---|---|
| JWT `alg: none` manipulation | Implemented | `backend/tests/test_jwt_manager.py::test_alg_none_token_is_rejected` | Memastikan token unsigned dengan header `alg: none` ditolak. |
| Token payload/signature tampering | Implemented | `backend/tests/test_jwt_manager.py::test_tampered_payload_token_is_rejected` | Payload diganti tetapi signature lama dipakai; verifikasi harus gagal. |
| Malformed token handling | Implemented | `backend/tests/test_jwt_manager.py::test_malformed_token_is_rejected` | Input JWT tidak valid harus fail closed. |
| Missing required claims | Implemented | `backend/tests/test_jwt_manager.py::test_token_missing_required_claims_is_rejected` | Token tanpa `sub`, `exp`, `jti`, atau `type` ditolak. |
| Token expiry | Implemented | `backend/tests/test_jwt_manager.py::test_expired_token` dan `backend/tests/test_auth_api.py::test_logout_rejects_expired_access_token` | Unit dan endpoint-level expiry rejection tersedia. |
| Session invalidation / token revocation | Implemented | `backend/tests/test_auth_api.py::test_logout_rejects_access_token_after_revocation` | Token yang sudah logout/blacklisted ditolak pada request berikutnya. |
| Refresh token rotation reuse | Implemented | `backend/tests/test_auth_api.py::test_reusing_rotated_refresh_token_is_rejected` | Refresh token lama ditolak setelah rotation. |
| Failed login rate limiting | Implemented | `backend/app/auth/login_rate_limiter.py`, `backend/app/api/auth_routes.py` | 5 failed login / 60 detik per `client_ip:username`. |
| HTTP 429 + `Retry-After` | Implemented | `backend/tests/test_auth_api.py::test_repeated_failed_login_attempts_return_429_with_retry_after` | Response rate-limited menyertakan header `Retry-After`. |
| Request flood/load-test script | Implemented | `backend/load_tests/auth_chat_flood_test.js` | Script k6 untuk failed-login flood dan unauthorized chatbot flood. |
| Chatbot endpoint runtime rate limiting | Implemented | `backend/app/api/routes/chat.py`, `backend/tests/test_chat_rate_limit.py` | `/api/chat/` dan `/api/chat/stream` dibatasi per user ID dengan fallback IP. |
| Redis-backed distributed controls | Implemented with fallback | `backend/app/core/redis_client.py`, `backend/app/auth/login_rate_limiter.py`, `backend/app/auth/token_revocation.py` | Redis digunakan saat `REDIS_ENABLED=true`; fallback in-memory tersedia untuk local/test. |
| Security metrics monitoring | Implemented | `backend/app/core/security_metrics.py` | Mencatat `401`, `403`, `429`, failed login per username/IP, dan token revocation. |

## Files Added or Updated

### `backend/tests/test_jwt_manager.py`

Pengujian JWT security ditambahkan untuk memastikan verifier menolak token yang umum dipakai dalam skenario serangan autentikasi:

- `test_alg_none_token_is_rejected`
- `test_tampered_payload_token_is_rejected`
- `test_malformed_token_is_rejected`
- `test_token_missing_required_claims_is_rejected`

Test ini memperkuat validasi terhadap implementasi di `backend/app/auth/jwt_manager.py`, yang sudah menggunakan PyJWT dengan daftar algoritma eksplisit:

```python
jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
```

Konfigurasi tersebut mencegah penerimaan algoritma yang tidak diizinkan seperti `none`.

### `backend/tests/test_auth_api.py`

Pengujian endpoint-level ditambahkan untuk memastikan proteksi tidak hanya benar di level helper JWT, tetapi juga berlaku saat endpoint API dipanggil:

- malformed bearer token ditolak oleh endpoint protected;
- expired access token ditolak;
- access token yang sudah di-blacklist setelah logout ditolak;
- failed login berulang menghasilkan `429 Too Many Requests` dan `Retry-After`.

### `backend/app/auth/login_rate_limiter.py`

Menambahkan Redis-backed limiter dengan fallback in-memory untuk failed login dan chatbot:

- key: `client_ip:username`;
- default: 5 failed attempts;
- window: 60 detik;
- thread-safe menggunakan `Lock`;
- menyediakan perhitungan `Retry-After`.
- Redis atomic counter menggunakan `INCR` + `EXPIRE` saat Redis aktif.

### `backend/app/auth/token_revocation.py`

Menambahkan store revocation token berbasis Redis dengan fallback in-memory. Token yang di-blacklist saat logout atau refresh rotation disimpan dengan TTL hingga expiry token sehingga konsisten untuk multi-instance deployment saat Redis aktif.

### `backend/app/core/security_metrics.py`

Menambahkan counter security metrics untuk:

- HTTP `401`;
- HTTP `403`;
- HTTP `429`;
- failed login per username/IP;
- token revocation events.

Metrics menggunakan Redis saat tersedia dan fallback in-memory untuk local/test.

### `backend/app/api/auth_routes.py`

Endpoint login sekarang:

1. membuat key rate limit dari IP dan username yang dinormalisasi;
2. mengecek apakah key tersebut sedang rate-limited;
3. mengembalikan `429 Too Many Requests` jika limit terlampaui;
4. mencatat failed login ke limiter;
5. mereset counter jika login berhasil;
6. mencatat rate-limited event ke audit log.

### `backend/app/api/routes/chat.py`

Endpoint chatbot sekarang menerapkan rate limit runtime pada:

- `POST /api/chat/`;
- `POST /api/chat/stream`.

Key rate limit menggunakan `user:{id}` jika user terautentikasi memiliki ID, dan fallback ke `ip:{client_ip}` bila user ID tidak tersedia. Jika limit terlampaui, endpoint mengembalikan `429 Too Many Requests` dengan header `Retry-After`.

### `backend/load_tests/auth_chat_flood_test.js` dan `backend/scripts/run_k6_security_eval.py`

Script k6 ditambahkan untuk simulasi:

- failed login flood terhadap `/api/auth/login`;
- unauthorized chatbot flood terhadap `/api/chat/`;
- validasi response `401` atau `429`;
- validasi `Retry-After` pada response `429`;
- threshold awal untuk latency p95 dan rate-limited response.

Runner `run_k6_security_eval.py` menjalankan k6 dengan `--summary-export`, lalu menyimpan artefak ringkas berisi QPS, p95 latency, jumlah `429`, jumlah error status, dan error rate ke `backend/data/security_eval/`.

Contoh penggunaan:

```bash
k6 run backend/load_tests/auth_chat_flood_test.js
```

Opsional dengan parameter environment:

```bash
k6 run \
  -e BASE_URL=http://localhost:8000 \
  -e AUTH_RPS=20 \
  -e CHAT_RPS=10 \
  backend/load_tests/auth_chat_flood_test.js
```

## Verification

Command yang dijalankan dari direktori `backend`:

```bash
venv\Scripts\python.exe -m pytest tests/test_jwt_manager.py tests/test_auth_api.py tests/test_pbac.py -q
```

Hasil:

```text
25 passed
```

Compile check untuk file Python yang berubah juga berhasil:

```bash
venv\Scripts\python.exe -m compileall app\auth\login_rate_limiter.py app\api\auth_routes.py tests\test_jwt_manager.py tests\test_auth_api.py
```

Command verifikasi terbaru:

```bash
venv\Scripts\python.exe -m pytest tests/test_jwt_manager.py tests/test_auth_api.py tests/test_chat_rate_limit.py tests/test_security_redis_stores.py tests/test_pbac.py -q
```

Hasil:

```text
25 passed
```

## Security Assessment

### Improvements Achieved

1. **JWT verification hardening is now test-backed**  
   Skenario manipulasi algoritma, token malformed, payload tampering, dan missing claims sekarang punya regression tests.

2. **Token lifecycle behavior is better covered**  
   Expiry, refresh token rotation reuse, logout blacklist, dan revoked token rejection sudah diuji.

3. **Redis-backed failed-login and chatbot rate limiting is now enforced**  
   Percobaan login gagal dan request chatbot berlebih dibatasi dan menghasilkan `429` dengan `Retry-After`.

4. **Request flood evaluation can be executed with k6**  
   Script load test menyediakan baseline untuk mengukur perilaku endpoint saat flood.

### Current Limitations

1. **Redis harus tersedia dan `REDIS_ENABLED=true` untuk mode distributed**  
   Jika Redis tidak aktif atau tidak bisa dijangkau, sistem fallback ke in-memory agar local/test tetap berjalan. Mode fallback tidak menjamin konsistensi multi-instance.

2. **Limiter chatbot memakai window sederhana**  
   Implementasi saat ini memakai counter fixed-window. Jika perlu akurasi lebih halus, dapat ditingkatkan ke sliding window/token bucket.

3. **Automatic anomaly blocking masih baseline**  
   Implementasi saat ini memblokir sementara berdasarkan failed login count. Deteksi anomali yang lebih luas, seperti korelasi IP, device fingerprint, user-agent, dan pola akses lintas endpoint, belum tersedia.

4. **Security metrics masih counter dasar**  
   Counter sudah tersedia, tetapi belum diekspos sebagai endpoint Prometheus/Grafana.

## Recommended Next Steps

1. **Aktifkan Redis di deployment produksi**  
   Set `REDIS_ENABLED=true` dan `REDIS_URL` ke Redis production agar counter failed login, rate limit chatbot, dan token revocation konsisten di multi-instance deployment.

2. **Ekspos security metrics ke monitoring stack**  
   Hubungkan counter `401`, `403`, `429`, failed login, dan token revocation ke Prometheus/Grafana atau sistem SIEM internal.

3. **Jalankan k6 sebagai evaluasi berkala**  
   Gunakan `backend/scripts/run_k6_security_eval.py` dan simpan artefak `backend/data/security_eval/` sebagai bukti evaluasi non-unit.

4. **Tambahkan monitoring security metrics**  
   Catat jumlah `401`, `403`, `429`, failed login per username/IP, dan token revocation events sebagai indikator anomali.

5. **Pertimbangkan sliding-window limiter**  
   Jika traffic production tinggi, fixed-window dapat diganti sliding window/token bucket agar fairness lebih baik.

## Closing Verdict

Untuk scope OWASP API Security pada area JWT authentication dan request flood baseline, implementasi sekarang **lebih kuat dan test-backed**. Sistem sudah mencakup pengujian manipulasi token, token lifecycle, session invalidation, Redis-backed failed-login/chatbot rate limiting, security metrics, serta runner k6 untuk artefak evaluasi non-unit.

Untuk production multi-instance, pastikan Redis benar-benar aktif dan dimonitor. Tanpa Redis, sistem tetap berjalan memakai fallback in-memory, tetapi konsistensi lintas instance tidak dijamin.
