# 13 — FASE 3: Frontend Refactor

## Ringkasan
FASE 3 memecah frontend chat monolitik menjadi arsitektur komponen + service layer, menutup gap keamanan markdown rendering, dan membersihkan dependency styling yang tidak dipakai.

## Perubahan Utama

### 1) Service Layer Terpusat
- File: `frontend/src/services/api.js`
  - Menambahkan axios instance dengan base URL dari `VITE_API_URL`.
  - Menambahkan helper `getErrorMessage()` untuk normalisasi pesan error API.
- File: `frontend/src/services/chatService.js`
  - Menambahkan method model/session/health.
  - Menambahkan parser SSE terpusat `streamChat()` untuk event `retrieval`, `token`, `complete`, `session`, `validation`, `error`.
- File: `frontend/src/services/documentService.js`
  - Menambahkan wrapper API dokumen: upload, preview, save, sync, list, detail, chunks, update chunk, delete chunk, delete document.

### 2) Pemecahan Komponen Chat
- File: `frontend/src/components/chat/SourceCard.vue`
- File: `frontend/src/components/chat/MessageBubble.vue`
- File: `frontend/src/components/chat/ChatInput.vue`
- File: `frontend/src/components/chat/ChatSidebar.vue`

Komponen ini memecah tanggung jawab UI menjadi unit kecil agar `ChatView` fokus sebagai orchestrator state dan event.

### 3) Refactor ChatView menjadi Orchestration-Only
- File: `frontend/src/views/ChatView.vue`
  - Menghilangkan markup sidebar/input/message monolitik.
  - Menggunakan komponen hasil ekstraksi.
  - Menggunakan service layer untuk semua API call.
  - Mempertahankan alur SSE lengkap termasuk `validation` warning.
- File: `frontend/src/assets/chat-view.css`
  - Memindahkan style besar dari SFC ke file aset terpisah.

### 4) Markdown Rendering Aman
- File: `frontend/src/components/chat/MessageBubble.vue`
  - Mengganti custom markdown parser regex ke `marked`.
  - Menambahkan sanitasi HTML memakai `DOMPurify`.
  - Tetap mempertahankan highlight citation `[n]` ke badge.

### 5) Konsistensi API di View Lain
- File: `frontend/src/views/DocumentsView.vue`
- File: `frontend/src/views/DocumentDetailView.vue`
- File: `frontend/src/views/HomeView.vue`

Semua view di atas kini memakai service layer, tidak lagi fetch langsung dengan URL hardcoded.

### 6) Tailwind/PostCSS Cleanup
- File: `frontend/package.json`
  - Menambahkan dependency baru: `axios`, `marked`, `dompurify`.
  - Menghapus dependency: `tailwindcss`, `autoprefixer`, `postcss`.
- File: `frontend/tailwind.config.js` (dihapus)
- File: `frontend/postcss.config.js` (dihapus)
- File: `frontend/src/assets/main.css`
  - Menghapus directive `@tailwind` dan menyisakan base style global minimal.

## Verifikasi

```bash
cd frontend
npm run build
```

Hasil build sukses:
- `dist/assets/index-*.css` sekitar 24.21 kB (gzip 4.74 kB)
- `dist/assets/index-*.js` sekitar 230.64 kB (gzip 82.78 kB)

## Catatan
- FASE 3 selesai dengan cakupan lebih luas dari target minimum karena migrasi service layer juga diterapkan ke halaman dokumen dan home.
- Alur backend SSE dan warning validasi tetap kompatibel setelah refactor frontend.
