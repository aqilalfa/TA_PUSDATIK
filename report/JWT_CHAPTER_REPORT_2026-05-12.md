# JWT Chapter Report

**Date**: 2026-05-12  
**Project**: SPBE RAG System PUSDATIK BSSN  
**Scope**: JWT Authentication, PBAC, frontend login, and alignment against PRD

## Executive Summary

Implementasi JWT pada repo ini sudah **kuat untuk baseline internal/local development**, tetapi **belum sepenuhnya memenuhi PRD asli** yang menuntut integrasi Active Directory, Redis-backed session management, rate limiting, dan audit logging. Dalam iterasi terakhir, frontend auth flow sudah diperbaiki agar lebih dekat ke model PRD: ada shared token store, refresh-token retry via cookie, dan cookie policy backend yang lebih aman untuk local development.

Step 1 dari roadmap berikutnya juga sudah diselesaikan: autentikasi kini dipisah ke layer provider yang modular, sehingga local login tetap menjadi default sementara LDAP/AD sudah punya jalur implementasi terpisah, shadow-user provisioning, dan mapping group ke role.

## What Is Implemented Now

### Backend
- JWT access token dan refresh token sudah ada.
- Token signing menggunakan HS256.
- Token blacklist berbasis SQLite sudah ada saat logout.
- PBAC dependency `require_roles` sudah ada.
- Login mengambil user dari SQLite `User` model dengan hashed password.
- Auth sekarang memakai abstraction provider: local provider + LDAP provider.
- LDAP provider melakukan shadow-user provisioning ke SQLite dan mapping group ke role lokal.
- Refresh token disimpan di HttpOnly cookie.
- Cookie `secure` kini mengikuti environment agar local browser testing berjalan.

### Frontend
- Login page sudah dibuat dan lulus 41/41 unit tests.
- Frontend auth client sekarang memakai shared token store.
- Axios interceptor mencoba refresh token otomatis saat menerima 401.
- Authorization header masih tetap disuntikkan untuk request protected.
- Login UI sudah responsive dan mengikuti visual language yang ada.

## PRD Traceability

| Requirement | Status | Notes |
|---|---:|---|
| FR-JWT-001 AD/LDAP Authentication | Missing | Saat ini masih local SQLite auth, belum LDAP/AD. |
| FR-JWT-002 Access Token Issuance | Partial | HS256 dan claims dasar sudah ada, tetapi belum lengkap seperti PRD. |
| FR-JWT-003 Refresh Token | Partial | Sudah ada cookie dan endpoint refresh, tetapi belum rolling rotation penuh. |
| FR-JWT-004 Token Validation | Partial | Signature, expiry, and blacklist check sudah ada. |
| FR-JWT-005 PBAC | Partial | `require_roles` ada, mapping AD group belum ada karena LDAP belum ada. |
| FR-JWT-006 Session Management | Missing | Belum ada Redis session store dan force logout lintas device. |
| FR-JWT-007 Rate Limiting | Missing | Belum ada middleware rate limiting per user/endpoint. |
| FR-JWT-008 Audit Logging | Missing | Belum ada audit log flow yang sesuai PRD. |

## Important Gaps

1. **LDAP/Active Directory belum ada**. Ini adalah gap terbesar terhadap PRD.
2. **Redis belum digunakan** untuk session, blacklist, dan rate limit.
3. **Audit logging** belum diimplementasikan sebagai komponen khusus.
4. **Refresh token rotation** masih perlu dibuat lebih ketat.
5. **Claims JWT** masih belum setara penuh dengan payload yang diminta PRD, terutama `dept`, `sid`, dan struktur yang konsisten di semua route.

Catatan update: gap nomor 1 sudah mulai ditangani secara modular, tetapi belum dianggap PRD-complete karena koneksi AD nyata dan konfigurasi produksi masih belum diverifikasi end-to-end.

## Recent Improvement Added

Saya menambahkan perbaikan berikut untuk mendekatkan flow frontend ke PRD:
- shared token store di frontend agar tidak seluruhnya bergantung pada satu tempat penyimpanan,
- refresh-token retry di Axios interceptor,
- cookie refresh token yang lebih cocok untuk local development,
- validasi syntax dan regression test tetap lulus.

Saya juga menambahkan perbaikan backend step 1:
- `backend/app/auth/auth_service.py` sebagai factory/service layer,
- `backend/app/auth/local_provider.py` untuk bcrypt lokal,
- `backend/app/auth/ldap_provider.py` untuk LDAP + shadow user,
- `backend/app/auth/role_mapper.py` untuk normalisasi grup ke role,
- penambahan field `auth_provider` dan `external_id` pada model user,
- test auth API dibuat self-contained dengan SQLite temporary file agar deterministik.

### Validation
- Backend auth regression: **8/8 passed** (`test_auth_provider`, `test_auth_api`, `test_local_auth`, `test_config`).
- Frontend unit test: **41/41 passed**.
- Syntax/error check pada file yang diubah: **no errors found**.

## Recommendation

Jika target Anda adalah **mendekat ke PRD penuh**, urutan kerja berikut paling masuk akal:
1. Validasi LDAP provider ke server AD nyata dan mapping group produksi.
2. Migrasi blacklist/session/rate limit ke Redis.
3. Tambahkan audit logging formal.
4. Lengkapi refresh token rotation.
5. Rapikan claim JWT agar konsisten dengan PRD.
6. Pertimbangkan mengganti sisa ketergantungan frontend yang masih mengandalkan localStorage.

## File Referenced
- [backend/app/api/auth_routes.py](../backend/app/api/auth_routes.py)
- [backend/app/dependencies/auth_dependencies.py](../backend/app/dependencies/auth_dependencies.py)
- [backend/app/auth/jwt_manager.py](../backend/app/auth/jwt_manager.py)
- [backend/app/models/db_models.py](../backend/app/models/db_models.py)
- [frontend/src/services/auth.js](../frontend/src/services/auth.js)
- [frontend/src/services/api.js](../frontend/src/services/api.js)
- [frontend/src/services/authToken.js](../frontend/src/services/authToken.js)
- [frontend/src/views/LoginView.vue](../frontend/src/views/LoginView.vue)

## Closing Verdict

Untuk **scope lokal / internal MVP**, implementasi ini sudah cukup usable. Untuk **scope PRD asli**, statusnya masih **partial** dan perlu beberapa komponen backend yang lebih besar sebelum bisa dianggap complete.
