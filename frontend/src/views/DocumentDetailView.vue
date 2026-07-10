<template>
  <div class="detail-page">
    <AppHeader active="documents" />

    <!-- Page header -->
    <div class="page-header">
      <div class="header-content">
        <router-link to="/documents" class="back-link">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          Kembali
        </router-link>
        <div class="title-section">
          <h1>{{ document?.document_title || 'Memuat...' }}</h1>
          <div class="doc-meta" v-if="document">
            <span class="badge badge-info">{{ document.doc_type }}</span>
            <span class="badge" :class="document.status === 'indexed' ? 'badge-ok' : 'badge-warn'">{{ document.status }}</span>
            <span class="meta-item">{{ document.chunk_count }} konteks</span>
          </div>
        </div>
      </div>
      <div class="header-actions">
        <button @click="confirmDeleteDocument" class="btn-danger-outline">
          Hapus Dokumen
        </button>
        <button @click="showAddModal = true" class="btn-primary">
          + Tambah Chunk
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>Memuat konteks...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="chunks.length === 0" class="empty-state">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <p>Tidak ada konteks</p>
        <button @click="showAddModal = true" class="action-btn primary">Tambah Konteks Pertama</button>
      </div>

      <!-- Chunks List -->
      <div v-else class="chunks-container">
        <div class="chunks-header">
          <div class="chunks-info">
            <span>{{ chunks.length }} konteks</span>
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
            v-for="(chunk, index) in chunks"
            :key="chunk.id"
            class="chunk-card"
            :class="{ highlighted: highlightChunkIndex === chunk.chunk_index }"
          >
            <div class="chunk-header">
              <div class="chunk-badges">
                <span class="chunk-number">#{{ index + 1 }}</span>
                <span v-if="chunk.bab" class="badge bab">{{ extractBabShort(chunk.bab) }}</span>
                <span v-if="chunk.pasal" class="badge pasal">{{ chunk.pasal }}</span>
                <span v-if="chunk.ayat" class="badge ayat">{{ formatAyatLabel(chunk.ayat) }}</span>
                <span v-if="chunk.chunk_parts_total && Number(chunk.chunk_parts_total) > 1" class="badge part">
                  Bagian {{ chunk.chunk_part || 1 }}/{{ chunk.chunk_parts_total }}
                </span>
                <span v-if="chunk.is_indexed" class="badge indexed">indexed</span>
              </div>
              <div class="chunk-actions">
                <button @click="editChunk(chunk)" class="icon-btn" title="Edit" :aria-label="`Edit konteks #${index + 1}`">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button @click="confirmDeleteChunk(chunk)" class="icon-btn delete" title="Hapus" :aria-label="`Hapus konteks #${index + 1}`">
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
            <div
              v-if="chunk.canonical_context_id || chunk.citation_id"
              class="chunk-identity"
              data-testid="chunk-identity"
            >
              <div v-if="chunk.canonical_context_id" class="identity-item">
                <span class="identity-label">ID Konteks Teknis</span>
                <code>{{ chunk.canonical_context_id }}</code>
              </div>
              <div v-if="chunk.citation_id" class="identity-item">
                <span class="identity-label">ID Sitasi Teknis</span>
                <code>{{ chunk.citation_id }}</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add/Edit Modal -->
    <div v-if="showAddModal || editingChunk" class="modal-overlay" @click="closeModal" @keydown.escape="closeModal">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="chunk-modal-title" @click.stop>
        <h3 id="chunk-modal-title">{{ editingChunk ? 'Edit Konteks' : 'Tambah Konteks Baru' }}</h3>
        
        <div class="form-group">
          <label>Teks Konteks</label>
          <textarea 
            v-model="chunkForm.text" 
            placeholder="Masukkan teks konteks..."
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
          <button @click="closeModal" class="btn-cancel">Batal</button>
          <button @click="saveChunk" :disabled="saving" class="btn-primary">
            {{ saving ? 'Menyimpan...' : (editingChunk ? 'Simpan Perubahan' : 'Tambah Konteks') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Chunk Confirmation Modal -->
    <div v-if="deletingChunk" class="modal-overlay" @click="deletingChunk = null" @keydown.escape="deletingChunk = null">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="delete-chunk-modal-title" @click.stop>
        <h3 id="delete-chunk-modal-title">Hapus Konteks?</h3>
        <p>Yakin ingin menghapus konteks #{{ deletingChunk.chunk_index + 1 }}?</p>
        <div class="modal-actions">
          <button @click="deletingChunk = null" class="btn-cancel">Batal</button>
          <button @click="deleteChunk" :disabled="deleting" class="btn-danger">
            {{ deleting ? 'Menghapus...' : 'Hapus' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Document Confirmation Modal -->
    <div v-if="deletingDocument" class="modal-overlay" @click="deletingDocument = false" @keydown.escape="deletingDocument = false">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="delete-document-modal-title" @click.stop>
        <h3 id="delete-document-modal-title">Hapus Dokumen?</h3>
        <p class="delete-warning">Yakin ingin menghapus dokumen "<strong>{{ document?.document_title }}</strong>"?</p>
        <p class="delete-info">Semua {{ document?.chunk_count || 0 }} konteks akan ikut terhapus. Aksi ini tidak dapat dibatalkan.</p>
        <div class="modal-actions">
          <button @click="deletingDocument = false" class="btn-cancel">Batal</button>
          <button @click="deleteDocument" :disabled="deletingDocumentLoading" class="btn-danger">
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
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import {
  deleteChunk as deleteChunkById,
  deleteDocument as deleteDocumentById,
  getDocument,
  getDocumentChunks,
  updateChunk
} from '@/services/documentService'

const route = useRoute()
const router = useRouter()

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

// Highlight chunk dari query param ?highlight=<chunk_index>
const highlightChunkIndex = ref(null)

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

function extractFirstNumber(value) {
  if (value === null || value === undefined) return 0
  const match = String(value).match(/\d+/)
  return match ? parseInt(match[0], 10) : 0
}

function formatAyatLabel(ayat) {
  if (!ayat) return ''
  const text = String(ayat).trim()
  if (!text) return ''
  if (/^ayat\b/i.test(text)) return text
  const number = extractFirstNumber(text)
  return number > 0 ? `Ayat (${number})` : `Ayat ${text}`
}

// Sort chunks: BAB -> Pasal -> Ayat for peraturan, chunk_index for others
function sortChunks(chunkList, docType) {
  return [...chunkList].sort((a, b) => {
    // For peraturan: sort by BAB -> Pasal -> Ayat
    if (docType === 'peraturan') {
      // Extract BAB Roman numeral
      const babSourceA = a.bab || a.hierarchy || ''
      const babSourceB = b.bab || b.hierarchy || ''
      const babMatchA = babSourceA.match(/BAB\s+([IVXLCDM]+)/i)
      const babMatchB = babSourceB.match(/BAB\s+([IVXLCDM]+)/i)
      const babA = romanToInt(babMatchA?.[1] || '')
      const babB = romanToInt(babMatchB?.[1] || '')
      if (babA !== babB) return babA - babB

      // Extract Pasal number
      const pasalSourceA = a.pasal || a.hierarchy || ''
      const pasalSourceB = b.pasal || b.hierarchy || ''
      const pasalA = extractFirstNumber(pasalSourceA)
      const pasalB = extractFirstNumber(pasalSourceB)
      if (pasalA !== pasalB) return pasalA - pasalB

      // Extract Ayat number
      const ayatA = extractFirstNumber(a.ayat)
      const ayatB = extractFirstNumber(b.ayat)
      if (ayatA !== ayatB) return ayatA - ayatB

      // Keep split parts in natural order for long chunks
      const partA = Number(a.chunk_part || 1)
      const partB = Number(b.chunk_part || 1)
      if (partA !== partB) return partA - partB

      // Stable fallback to preserve original sequence
      const indexA = Number(a.chunk_index || 0)
      const indexB = Number(b.chunk_index || 0)
      if (indexA !== indexB) return indexA - indexB

      return Number(a.id || 0) - Number(b.id || 0)
    }

    // For non-peraturan: sort by chunk_index
    const indexA = Number(a.chunk_index || 0)
    const indexB = Number(b.chunk_index || 0)
    if (indexA !== indexB) return indexA - indexB

    const partA = Number(a.chunk_part || 1)
    const partB = Number(b.chunk_part || 1)
    if (partA !== partB) return partA - partB

    return Number(a.id || 0) - Number(b.id || 0)
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
    document.value = await getDocument(docId.value)
  } catch (e) {
    console.error('Load document error:', e)
  }
}

async function loadChunks() {
  loading.value = true
  try {
    // Load more chunks to ensure we have all for sorting
    const rawChunks = await getDocumentChunks(docId.value, 500, 0)
    // Sort chunks based on document type
    const docType = document.value?.doc_type || 'other'
    chunks.value = sortChunks(rawChunks, docType)
    offset.value = chunks.value.length
    hasMore.value = rawChunks.length >= 500
  } catch (e) {
    console.error('Load chunks error:', e)
            showToast('Gagal memuat konteks', 'error')
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  loadingMore.value = true
  try {
    const more = await getDocumentChunks(docId.value, limit, offset.value)
    const docType = document.value?.doc_type || 'other'
    // Add and re-sort all chunks
    chunks.value = sortChunks([...chunks.value, ...more], docType)
    offset.value += more.length
    hasMore.value = more.length >= limit
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
    await deleteDocumentById(docId.value)

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
      showToast('Teks konteks tidak boleh kosong', 'error')
    return
  }

  saving.value = true
  try {
    if (editingChunk.value) {
      // Update existing chunk
      await updateChunk(editingChunk.value.id, chunkForm.value.text)
      
      // Update local state
      const idx = chunks.value.findIndex(c => c.id === editingChunk.value.id)
      if (idx >= 0) {
        chunks.value[idx] = { ...chunks.value[idx], text: chunkForm.value.text }
      }
      
      showToast('Chunk berhasil diperbarui')
    } else {
      // Add new context - for now just show message
      showToast('Fitur tambah konteks baru akan segera tersedia', 'info')
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
    await deleteChunkById(deletingChunk.value.id)

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

  // Baca query param ?highlight=chunk_index dan scroll ke chunk yang dikutip
  const highlightParam = route.query.highlight
  if (highlightParam !== undefined && highlightParam !== '') {
    highlightChunkIndex.value = parseInt(highlightParam, 10)
    await nextTick()
    const el = document.querySelector('.chunk-card.highlighted')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
})
</script>

<style scoped>
.detail-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-cream);
}

/* Page header below topbar */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 32px 16px;
  background: white;
  border-bottom: 1px solid var(--color-border);
  max-width: 100%;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--color-text-muted);
  text-decoration: none;
  font-family: var(--font-ui);
  border: 1px solid var(--color-border);
  padding: 5px 10px;
  border-radius: 2px;
  transition: all 0.15s;
  white-space: nowrap;
}
.back-link:hover { border-color: var(--color-navy); color: var(--color-navy); }

.title-section h1 {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-navy);
  margin: 0 0 6px;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-item {
  font-size: 11px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* Buttons */
.btn-primary {
  background: var(--color-navy);
  color: white;
  border: none;
  padding: 8px 16px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  font-family: var(--font-ui);
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover:not(:disabled) { background: var(--color-navy-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-danger-outline {
  background: transparent;
  color: var(--color-danger);
  border: 1px solid var(--color-danger);
  padding: 7px 14px;
  font-size: 11px;
  font-family: var(--font-ui);
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-danger-outline:hover { background: rgba(192, 57, 43, 0.08); }

.btn-cancel {
  background: transparent;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  padding: 7px 14px;
  font-size: 11px;
  font-family: var(--font-ui);
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-cancel:hover { border-color: var(--color-text-muted); }

.btn-danger {
  background: var(--color-danger);
  color: white;
  border: none;
  padding: 7px 16px;
  font-size: 11px;
  font-family: var(--font-ui);
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-danger:hover:not(:disabled) { background: var(--color-danger-hover); }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

/* Main content */
.main-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 28px 32px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: var(--color-text-muted);
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 3px;
  font-family: var(--font-body);
  font-style: italic;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-gold);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}

.chunks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.chunks-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
}

.sort-indicator {
  padding: 3px 8px;
  background: var(--color-status-info-bg);
  border: 1px solid var(--color-status-info-border);
  border-radius: 2px;
  font-size: 9px;
  color: var(--color-status-info-text);
  font-family: var(--font-ui);
  letter-spacing: 0.3px;
}

.load-more-btn {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  color: var(--color-text-muted);
  font-size: 11px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all 0.15s;
}
.load-more-btn:hover { border-color: var(--color-navy); color: var(--color-navy); }

/* Chunks */
.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chunk-card {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 3px;
  overflow: hidden;
}

.chunk-card.highlighted {
  border-color: var(--color-gold);
  box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.20);
  animation: highlightFade 2.5s ease forwards;
}

@keyframes highlightFade {
  0%   { background: var(--color-status-warn-bg); }
  100% { background: white; }
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: var(--color-input-bg);
  border-bottom: 1px solid var(--color-border-light);
}

.chunk-badges {
  display: flex;
  gap: 5px;
  align-items: center;
  flex-wrap: wrap;
}

.chunk-number {
  font-size: 9px;
  font-weight: 600;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  background: var(--color-border-light);
  padding: 2px 7px;
  border-radius: 2px;
}

.badge.bab { background: var(--color-status-warn-bg); color: var(--color-status-warn-text); border: 1px solid var(--color-status-warn-border); font-size: 9px; padding: 2px 7px; border-radius: 2px; font-family: var(--font-ui); font-weight: 600; }
.badge.pasal { background: var(--color-status-info-bg); color: var(--color-status-info-text); border: 1px solid var(--color-status-info-border); font-size: 9px; padding: 2px 7px; border-radius: 2px; font-family: var(--font-ui); font-weight: 600; }
.badge.ayat { background: var(--color-status-ok-bg); color: var(--color-status-ok-text); border: 1px solid var(--color-status-ok-border); font-size: 9px; padding: 2px 7px; border-radius: 2px; font-family: var(--font-ui); font-weight: 600; }
.badge.part { background: var(--color-status-info-bg); color: var(--color-navy-hover); border: 1px solid var(--color-status-info-border); font-size: 9px; padding: 2px 7px; border-radius: 2px; font-family: var(--font-ui); }
.badge.indexed { background: var(--color-status-ok-bg); color: var(--color-status-ok-text); border: 1px solid var(--color-status-ok-border); font-size: 9px; padding: 2px 7px; border-radius: 2px; font-family: var(--font-ui); }

.chunk-actions {
  display: flex;
  gap: 3px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  position: relative; /* Impeccable Layout: Expand hit area */
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.icon-btn::before {
  content: '';
  position: absolute;
  inset: -10px; /* Expands touch target to ~48x48px without changing visuals */
}
.icon-btn:hover { border-color: var(--color-border); color: var(--color-navy); background: var(--color-status-info-bg); }
.icon-btn.delete:hover { border-color: var(--color-danger-border-light); color: var(--color-danger); background: rgba(192,57,43,0.06); }

.chunk-content {
  padding: 12px 14px;
}
.chunk-content p {
  margin: 0;
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.65;
  color: var(--color-text);
  white-space: pre-wrap;
}

.chunk-context {
  padding: 8px 14px;
  background: var(--color-cream-dark);
  border-top: 1px solid var(--color-border-light);
  font-size: 11px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-style: italic;
}

.chunk-identity {
  display: grid;
  gap: 5px;
  padding: 8px 14px 10px;
  background: var(--color-surface-soft);
  border-top: 1px solid var(--color-border-light);
}

.identity-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.identity-label {
  flex: 0 0 70px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
}

.identity-item code {
  min-width: 0;
  overflow-wrap: anywhere;
  padding: 2px 6px;
  background: #eef2f9;
  border: 1px solid #d8e0ed;
  border-radius: 2px;
  color: var(--color-navy);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
  line-height: 1.5;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(26, 58, 107, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal-backdrop);
}

.modal {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 3px;
  padding: 24px;
  max-width: 580px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(26, 58, 107, 0.15);
}

.modal h3 {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-navy);
  margin: 0 0 16px;
}

.modal p {
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--color-text);
  margin: 0 0 8px;
}

.delete-warning strong { color: #c0392b; }
.delete-info { font-size: 12px; color: var(--color-text-muted) !important; }

.form-group { margin-bottom: 14px; }
.form-group label {
  display: block;
  margin-bottom: 5px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
}
.form-group input,
.form-group textarea {
  width: 100%;
  padding: 9px 12px;
  background: #faf9f7;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  color: var(--color-text);
  font-size: 13px;
  font-family: var(--font-body);
  resize: vertical;
  transition: border-color 0.2s, background 0.2s;
}
.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--color-navy);
  background: white;
}
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  border-radius: 2px;
  font-size: 12px;
  font-family: var(--font-ui);
  z-index: var(--z-toast);
  animation: slideInRight 0.3s ease;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.toast.success { background: var(--color-navy); color: white; }
.toast.error { background: #c0392b; color: white; }
.toast.info { background: #8b7355; color: white; }
</style>
