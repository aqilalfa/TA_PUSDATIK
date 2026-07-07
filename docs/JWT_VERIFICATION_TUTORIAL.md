# Tutorial Mengecek Mekanisme JWT

Dokumen ini menjelaskan cara mengecek apakah mekanisme JWT aplikasi SPBE RAG sudah berjalan dengan benar.

## Prasyarat

Pastikan aplikasi sudah berjalan dengan Docker Compose production:

```powershell
docker compose --env-file .env.docker -f docker-compose.prod.yml ps
```

Status yang diharapkan:

- `spbe-backend-prod`: `healthy`
- `spbe-frontend-prod`: `Up`
- `spbe-qdrant-prod`: `healthy`

---

## 1. Cek Login Menghasilkan Access Token

Jalankan perintah berikut di PowerShell dari root project:

```powershell
$body = 'username=admin%40bssn.go.id&password=password123'

$login = Invoke-RestMethod `
  -Method Post `
  -Uri 'http://localhost/api/auth/login' `
  -ContentType 'application/x-www-form-urlencoded' `
  -Body $body

$login.access_token
```

Jika berhasil, output akan berupa token panjang seperti:

```text
eyJhbGciOiJIUzI1NiIsInR5cCI6...
```

Artinya login berhasil dan backend menerbitkan JWT access token.

---

## 2. Cek Endpoint Protected Tanpa Token Harus Ditolak

Endpoint yang dilindungi tidak boleh bisa diakses tanpa JWT.

```powershell
try {
  Invoke-RestMethod -Method Get -Uri 'http://localhost/api/sessions/' -ErrorAction Stop
  'GAGAL: endpoint bisa diakses tanpa token'
} catch {
  'OK: ditolak dengan status ' + [int]$_.Exception.Response.StatusCode
}
```

Hasil yang benar:

```text
OK: ditolak dengan status 401
```

Ulangi untuk endpoint lain:

```powershell
try {
  Invoke-RestMethod -Method Get -Uri 'http://localhost/api/models' -ErrorAction Stop
  'GAGAL: endpoint bisa diakses tanpa token'
} catch {
  'OK: ditolak dengan status ' + [int]$_.Exception.Response.StatusCode
}
```

Hasil yang benar juga `401`.

---

## 3. Cek Endpoint Protected Dengan Token Harus Berhasil

Gunakan token dari hasil login:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri 'http://localhost/api/sessions/' `
  -Headers @{ Authorization = "Bearer $($login.access_token)" }
```

Jika tidak error, berarti token valid dan backend menerima JWT Bearer token.

---

## 4. Cek Refresh Token

Refresh token disimpan di cookie `HttpOnly`, sehingga tidak dibaca langsung oleh JavaScript. Untuk mengeceknya via PowerShell/curl:

```powershell
$loginResponse = Invoke-WebRequest `
  -UseBasicParsing `
  -Method Post `
  -Uri 'http://localhost/api/auth/login' `
  -ContentType 'application/x-www-form-urlencoded' `
  -Body $body

$cookie = [regex]::Match(
  $loginResponse.Headers['Set-Cookie'],
  'refresh_token=([^;]+)'
).Groups[1].Value

curl.exe -s -X POST 'http://localhost/api/auth/refresh' `
  -H "Cookie: refresh_token=$cookie"
```

Hasil yang benar adalah JSON yang berisi `access_token` baru:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
  "token_type": "bearer"
}
```

---

## 5. Cek JWT Dari Browser DevTools

1. Buka aplikasi:

   ```text
   http://localhost
   ```

2. Login dengan kredensial:

   ```text
   admin@bssn.go.id
   password123
   ```

3. Buka DevTools:

   - Firefox/Chrome: tekan `F12`
   - Masuk ke tab **Network**

4. Lakukan aktivitas di aplikasi, misalnya:

   - kirim chat
   - buka session
   - ubah judul session
   - buka dokumen atau citation

5. Klik request API di tab Network.

   Contoh request API:

   | Method | Nama/File di Network | Endpoint sebenarnya |
   |---|---|---|
   | `POST` | `stream` | `/api/chat/stream` |
   | `GET` | `sessions` atau `/api/sessions/` | `/api/sessions/` |
   | `PUT` | `title?...` | `/api/sessions/{id}/title` |
   | `GET` | `models` | `/api/models` |
   | `GET` | `health` | `/api/health` |

6. Buka tab/detail **Headers**.

7. Cari bagian **Request Headers**.

8. Pastikan ada header:

   ```text
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6...
   ```

Jika header tersebut ada pada request seperti `/api/chat/stream`, `/api/sessions/`, atau `/api/models`, berarti frontend sudah mengirim JWT dengan benar.

> Catatan: request seperti font `.woff2`, gambar, CSS, JS, atau domain eksternal bukan request API aplikasi. Abaikan request tersebut saat mengecek JWT.

---

## 6. Cek Cookie Refresh Token Di Browser

Di DevTools:

1. Buka tab **Storage** atau **Application**.
2. Pilih **Cookies**.
3. Pilih domain `http://localhost`.
4. Cari cookie:

   ```text
   refresh_token
   ```

Properti yang diharapkan:

- `HttpOnly`: aktif
- `Secure`: aktif saat environment production
- `Path`: `/api/auth/refresh`
- `SameSite`: `Strict` atau sesuai konfigurasi production

Karena `HttpOnly`, cookie ini memang tidak bisa dibaca dari JavaScript. Itu perilaku yang benar.

---

## 7. Indikator JWT Berjalan Dengan Benar

JWT dianggap berjalan benar jika semua kondisi berikut terpenuhi:

- Login menghasilkan `access_token`.
- Endpoint protected tanpa token mengembalikan `401`.
- Endpoint protected dengan token berhasil diakses.
- Request API frontend memiliki header `Authorization: Bearer ...`.
- Refresh endpoint menghasilkan access token baru.
- Cookie `refresh_token` memiliki `HttpOnly` dan path `/api/auth/refresh`.

---

## Troubleshooting

### Request API tidak punya header Authorization

Kemungkinan:

- Belum login.
- Access token belum tersimpan di browser.
- Request yang diklik bukan request API aplikasi.
- Frontend belum rebuild/restart setelah perubahan.

Solusi:

```powershell
docker compose --env-file .env.docker -f docker-compose.prod.yml up -d --build frontend
```

### Endpoint protected bisa diakses tanpa token

Artinya route backend belum memakai dependency auth.

Cek file route terkait dan pastikan memakai salah satu dependency:

```python
Depends(get_current_user)
```

atau:

```python
Depends(require_roles(["admin_pusdatik"]))
```

### Refresh token missing

Kemungkinan cookie tidak terkirim.

Untuk test manual, pastikan header cookie dikirim seperti contoh:

```powershell
curl.exe -s -X POST 'http://localhost/api/auth/refresh' `
  -H "Cookie: refresh_token=$cookie"
```

### Backend tidak healthy

Cek log backend:

```powershell
docker compose --env-file .env.docker -f docker-compose.prod.yml logs --tail 100 backend
```
