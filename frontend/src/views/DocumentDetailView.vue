<template>
  <div class="detail-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <router-link to="/documents" class="back-link">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
        </router-link>
        <div class="title-section">
          <h1>{{ document?.document_title || 'Loading...' }}</h1>
          <div class="doc-meta" v-if="document">
            <span class="badge type">{{ document.doc_type }}</span>
            <span class="badge status" :class="document.status">{{ document.status }}</span>
            <span class="meta-item">{{ document.chunk_count }} chunks</span>
          </div>
        </div>
      </div>
      <div class="header-actions">
        <button @click="confirmDeleteDocument" class="action-btn danger">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
          Hapus Dokumen
        </button>
        <button @click="showAddModal = true" class="action-btn primary">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Tambah Chunk
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <div class="main-content">
      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>Memuat chunks...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="chunks.length === 0" class="empty-state">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <p>Tidak ada chunks</p>
        <button @click="showAddModal = true" class="action-btn primary">Tambah Chunk Pertama</button>
      </div>

      <!-- Chunks List -->
      <div v-else class="chunks-container">
        <div class="chunks-header">
          <div class="chunks-info">
            <span>{{ chunks.length }} chunks</span>
            <span class="sort-indicator" v-if="document?.doc_type === 'peraturan'">
              Diurutkan: BAB → Pasal → Ayat
            </span>
            <span class="sort-indicator" v-else>
              Diurutkan: Urutan dokumen
            </span>
          </div>
          <button v-if="hasMore" @click="loadMore" :disabled="loadingMore" class="load-more-btn">
            {{ loadingMore ? 'Memuat...' : 'Muat Lebih Banyak' }}
          </button>
        </div>

        <div class="chunks-list">
          <div 
            v-for="chunk in chunks" 
            :key="chunk.id"
            class="chunk-card"
          >
            <div class="chunk-header">
              <div class="chunk-badges">
                <span class="chunk-number">#{{ chunks.indexOf(chunk) + 1 }}</span>
                <span v-if="chunk.bab" class="badge bab">{{ extractBabShort(chunk.bab) }}</span>
                <span v-if="chunk.pasal" class="badge pasal">{{ chunk.pasal }}</span>
                <span v-if="chunk.ayat" class="badge ayat">Ayat ({{ chunk.ayat }})</span>
                <span v-if="chunk.is_indexed" class="badge indexed">indexed</span>
              </div>
              <div class="chunk-actions">
                <button @click="editChunk(chunk)" class="icon-btn" title="Edit">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button @click="confirmDeleteChunk(chunk)" class="icon-btn delete" title="Hapus">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>
            </div>
            <div class="chunk-content">
              <p>{{ chunk.text }}</p>
            </div>
            <div v-if="chunk.context_header" class="chunk-context">
              {{ chunk.context_header }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add/Edit Modal -->
    <div v-if="showAddModal || editingChunk" class="modal-overlay" @click="closeModal">
      <div class="modal" @click.stop>
        <h3>{{ editingChunk ? 'Edit Chunk' : 'Tambah Chunk Baru' }}</h3>
        
        <div class="form-group">
          <label>Teks Chunk</label>
          <textarea 
            v-model="chunkForm.text" 
            placeholder="Masukkan teks chunk..."
            rows="8"
          ></textarea>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Pasal</label>
            <input v-model="chunkForm.pasal" placeholder="Pasal 1" />
          </div>
          <div class="form-group">
            <label>Ayat</label>
            <input v-model="chunkForm.ayat" placeholder="1" />
          </div>
        </div>

        <div class="modal-actions">
          <button @click="closeModal" class="action-btn cancel">Batal</button>
          <button @click="saveChunk" :disabled="saving" class="action-btn primary">
            {{ saving ? 'Menyimpan...' : (editingChunk ? 'Simpan Perubahan' : 'Tambah Chunk') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Chunk Confirmation Modal -->
    <div v-if="deletingChunk" class="modal-overlay" @click="deletingChunk = null">
      <div class="modal" @click.stop>
        <h3>Hapus Chunk?</h3>
        <p>Yakin ingin menghapus chunk #{{ deletingChunk.chunk_index + 1 }}?</p>
        <div class="modal-actions">
          <button @click="deletingChunk = null" class="action-btn cancel">Batal</button>
          <button @click="deleteChunk" :disabled="deleting" class="action-btn danger">
            {{ deleting ? 'Menghapus...' : 'Hapus' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Document Confirmation Modal -->
    <div v-if="deletingDocument" class="modal-overlay" @click="deletingDocument = false">
      <div class="modal" @click.stop>
        <h3>Hapus Dokumen?</h3>
        <p class="delete-warning">Yakin ingin menghapus dokumen "<strong>{{ document?.document_title }}</strong>"?</p>
        <p class="delete-info">Semua {{ document?.chunk_count || 0 }} chunks akan ikut terhapus. Aksi ini tidak dapat dibatalkan.</p>
        <div class="modal-actions">
          <button @click="deletingDocument = false" class="action-btn cancel">Batal</button>
          <button @click="deleteDocument" :disabled="deletingDocumentLoading" class="action-btn danger">
            {{ deletingDocumentLoading ? 'Menghapus...' : 'Hapus Dokumen' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="toast.type">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const API_BASE = 'http://localhost:8000'

// State
const docId = ref(route.params.doc_id)
const document = ref(null)
const chunks = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMore = ref(false)
const offset = ref(0)
const limit = 50

const showAddModal = ref(false)
const editingChunk = ref(null)
const deletingChunk = ref(null)
const deletingDocument = ref(false)
const deletingDocumentLoading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const toast = ref(null)

const chunkForm = ref({
  text: '',
  pasal: '',
  ayat: ''
})

// Helper: Convert Roman numerals to integer
function romanToInt(roman) {
  if (!roman) return 0
  const values = { I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000 }
  let result = 0
  const upperRoman = roman.toUpperCase()
  for (let i = 0; i < upperRoman.length; i++) {
    const curr = values[upperRoman[i]] || 0
    const next = values[upperRoman[i + 1]] || 0
    result += curr < next ? -curr : curr
  }
  return result
}

// Sort chunks: BAB -> Pasal -> Ayat for peraturan, chunk_index for others
function sortChunks(chunkList, docType) {
  return [...chunkList].sort((a, b) => {
    // For peraturan: sort by BAB -> Pasal -> Ayat
    if (docType === 'peraturan') {
      // Extract BAB Roman numeral
      const babMatchA = a.bab?.match(/BAB\s+([IVXLCDM]+)/i)
      const babMatchB = b.bab?.match(/BAB\s+([IVXLCDM]+)/i)
      const babA = romanToInt(babMatchA?.[1] || '')
      const babB = romanToInt(babMatchB?.[1] || '')
      if (babA !== babB) return babA - babB

      // Extract Pasal number
      const pasalA = parseInt(a.pasal?.match(/\d+/)?.[0] || '0')
      const pasalB = parseInt(b.pasal?.match(/\d+/)?.[0] || '0')
      if (pasalA !== pasalB) return pasalA - pasalB

      // Extract Ayat number
      const ayatA = parseInt(a.ayat || '0')
      const ayatB = parseInt(b.ayat || '0')
      return ayatA - ayatB
    }

    // For non-peraturan: sort by chunk_index
    return (a.chunk_index || 0) - (b.chunk_index || 0)
  })
}

// Extract short BAB label (e.g., "BAB III MANAJEMEN..." -> "BAB III")
function extractBabShort(bab) {
  if (!bab) return ''
  const match = bab.match(/BAB\s+[IVXLCDM]+/i)
  return match ? match[0] : bab.substring(0, 10)
}

// Methods
function showToast(message, type = 'success') {
  toast.value = { message, type }
  setTimeout(() => toast.value = null, 3000)
}

async function loadDocument() {
  try {
    const resp = await fetch(`${API_BASE}/api/documents/${docId.value}`)
    if (resp.ok) {
      document.value = await resp.json()
    }
  } catch (e) {
    console.error('Load document error:', e)
  }
}

async function loadChunks() {
  loading.value = true
  try {
    // Load more chunks to ensure we have all for sorting
    const resp = await fetch(`${API_BASE}/api/documents/${docId.value}/chunks?limit=500&offset=0`)
    if (resp.ok) {
      let rawChunks = await resp.json()
      // Sort chunks based on document type
      const docType = document.value?.doc_type || 'other'
      chunks.value = sortChunks(rawChunks, docType)
      offset.value = chunks.value.length
      hasMore.value = rawChunks.length >= 500
    }
  } catch (e) {
    console.error('Load chunks error:', e)
    showToast('Gagal memuat chunks', 'error')
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  loadingMore.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents/${docId.value}/chunks?limit=${limit}&offset=${offset.value}`)
    if (resp.ok) {
      const more = await resp.json()
      const docType = document.value?.doc_type || 'other'
      // Add and re-sort all chunks
      chunks.value = sortChunks([...chunks.value, ...more], docType)
      offset.value += more.length
      hasMore.value = more.length >= limit
    }
  } catch (e) {
    console.error('Load more error:', e)
  } finally {
    loadingMore.value = false
  }
}

function editChunk(chunk) {
  editingChunk.value = chunk
  chunkForm.value = {
    text: chunk.text,
    pasal: chunk.pasal || '',
    ayat: chunk.ayat || ''
  }
}

function confirmDeleteChunk(chunk) {
  deletingChunk.value = chunk
}

function confirmDeleteDocument() {
  deletingDocument.value = true
}

async function deleteDocument() {
  deletingDocumentLoading.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents/${docId.value}`, {
      method: 'DELETE'
    })

    if (!resp.ok) {
      const error = await resp.json()
      throw new Error(error.detail || 'Gagal menghapus dokumen')
    }

    showToast('Dokumen berhasil dihapus')
    
    // Redirect ke halaman daftar dokumen setelah 1 detik
    setTimeout(() => {
      router.push('/documents')
    }, 1000)
  } catch (e) {
    showToast(e.message, 'error')
    deletingDocument.value = false
  } finally {
    deletingDocumentLoading.value = false
  }
}

function closeModal() {
  showAddModal.value = false
  editingChunk.value = null
  chunkForm.value = { text: '', pasal: '', ayat: '' }
}

async function saveChunk() {
  if (!chunkForm.value.text.trim()) {
    showToast('Teks chunk tidak boleh kosong', 'error')
    return
  }

  saving.value = true
  try {
    if (editingChunk.value) {
      // Update existing chunk
      const resp = await fetch(`${API_BASE}/api/documents/chunks/${editingChunk.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: chunkForm.value.text })
      })
      
      if (!resp.ok) throw new Error('Update gagal')
      
      // Update local state
      const idx = chunks.value.findIndex(c => c.id === editingChunk.value.id)
      if (idx >= 0) {
        chunks.value[idx] = { ...chunks.value[idx], text: chunkForm.value.text }
      }
      
      showToast('Chunk berhasil diperbarui')
    } else {
      // Add new chunk - for now just show message
      showToast('Fitur tambah chunk baru akan segera tersedia', 'info')
    }
    
    closeModal()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    saving.value = false
  }
}

async function deleteChunk() {
  if (!deletingChunk.value) return

  deleting.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents/chunks/${deletingChunk.value.id}`, {
      method: 'DELETE'
    })

    if (!resp.ok) throw new Error('Delete gagal')

    // Remove from local state
    chunks.value = chunks.value.filter(c => c.id !== deletingChunk.value.id)
    showToast('Chunk berhasil dihapus')
    deletingChunk.value = null
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await loadDocument()
  await loadChunks()
})
</script>

<style scoped>
.detail-page {
  min-height: 100vh;
  background: #1a1a2e;
  color: #e4e4e7;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  background: #16162a;
  border-bottom: 1px solid #2a2a4a;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-link {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: #2a2a4a;
  border-radius: 8px;
  color: #a1a1aa;
  transition: all 0.2s;
}

.back-link:hover {
  background: #3a3a5a;
  color: #e4e4e7;
}

.title-section h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.badge {
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge.type {
  background: #3a3a5a;
  color: #a1a1aa;
}

.badge.status {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.badge.status.uploaded,
.badge.status.previewed {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.meta-item {
  color: #71717a;
  font-size: 0.875rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1rem;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn.primary {
  background: #6366f1;
  color: white;
}

.action-btn.primary:hover {
  background: #5558e3;
}

.action-btn.cancel {
  background: transparent;
  border: 1px solid #3a3a5a;
  color: #a1a1aa;
}

.action-btn.danger {
  background: #ef4444;
  color: white;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.main-content {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  color: #71717a;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #3a3a5a;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state svg {
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state .action-btn {
  margin-top: 1rem;
}

.chunks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  color: #71717a;
  font-size: 0.875rem;
}

.chunks-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.sort-indicator {
  padding: 0.25rem 0.5rem;
  background: #2a2a4a;
  border-radius: 4px;
  font-size: 0.75rem;
  color: #a1a1aa;
}

.load-more-btn {
  padding: 0.5rem 1rem;
  background: #2a2a4a;
  border: 1px solid #3a3a5a;
  border-radius: 6px;
  color: #e4e4e7;
  font-size: 0.8125rem;
  cursor: pointer;
}

.load-more-btn:hover {
  background: #3a3a5a;
}

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.chunk-card {
  background: #16162a;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  overflow: hidden;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #1a1a30;
  border-bottom: 1px solid #2a2a4a;
}

.chunk-badges {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.chunk-number {
  background: #3a3a5a;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #a1a1aa;
}

.badge.bab {
  background: #f59e0b;
  color: #000;
}

.badge.pasal {
  background: #6366f1;
  color: white;
}

.badge.ayat {
  background: #22c55e;
  color: #000;
}

.badge.indexed {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.chunk-actions {
  display: flex;
  gap: 0.25rem;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #71717a;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover {
  background: #2a2a4a;
  color: #e4e4e7;
}

.icon-btn.delete:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.chunk-content {
  padding: 1rem;
}

.chunk-content p {
  margin: 0;
  line-height: 1.6;
  color: #d4d4d8;
  white-space: pre-wrap;
}

.chunk-context {
  padding: 0.75rem 1rem;
  background: #14142a;
  border-top: 1px solid #2a2a4a;
  font-size: 0.8125rem;
  color: #71717a;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #16162a;
  border: 1px solid #2a2a4a;
  border-radius: 12px;
  padding: 1.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.modal h3 {
  margin: 0 0 1.5rem;
  font-size: 1.125rem;
}

.modal p {
  margin: 0 0 0.5rem;
  color: #d4d4d8;
}

.delete-warning {
  font-size: 0.9375rem;
}

.delete-warning strong {
  color: #ef4444;
}

.delete-info {
  font-size: 0.8125rem;
  color: #71717a !important;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: #a1a1aa;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 0.75rem;
  background: #1a1a2e;
  border: 1px solid #3a3a5a;
  border-radius: 6px;
  color: #e4e4e7;
  font-size: 0.875rem;
  font-family: inherit;
  resize: vertical;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #6366f1;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  font-size: 0.875rem;
  z-index: 1001;
  animation: slideIn 0.3s ease;
}

.toast.success {
  background: #22c55e;
  color: white;
}

.toast.error {
  background: #ef4444;
  color: white;
}

.toast.info {
  background: #3b82f6;
  color: white;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>
