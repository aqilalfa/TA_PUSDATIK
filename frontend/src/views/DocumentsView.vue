<template>
  <div class="documents-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <h1>Document Management</h1>
        <p>Upload dan kelola dokumen peraturan SPBE</p>
      </div>
      <router-link to="/" class="back-btn">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
        Kembali ke Chat
      </router-link>
    </header>

    <!-- Main Content -->
    <div class="main-content">
      <!-- Upload Section -->
      <section class="upload-section">
        <h2>Upload Dokumen</h2>
        
        <!-- Drop Zone -->
        <div 
          class="drop-zone"
          :class="{ 'drag-over': isDragging, 'has-file': selectedFile }"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleDrop"
          @click="$refs.fileInput.click()"
        >
          <input 
            type="file" 
            ref="fileInput" 
            accept=".pdf"
            @change="handleFileSelect"
            hidden
          />
          
          <div v-if="!selectedFile" class="drop-content">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <p>Drag & drop file PDF atau <span>klik untuk browse</span></p>
            <small>Maksimum 50MB</small>
          </div>
          
          <div v-else class="file-info">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <div>
              <p class="filename">{{ selectedFile.name }}</p>
              <small>{{ formatFileSize(selectedFile.size) }}</small>
            </div>
            <button @click.stop="clearFile" class="clear-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Upload Button -->
        <button 
          v-if="selectedFile && !uploadedDocId"
          @click="uploadFile"
          :disabled="uploading"
          class="action-btn primary"
        >
          <span v-if="uploading">Mengupload...</span>
          <span v-else>Upload Dokumen</span>
        </button>

        <!-- Preview Button (after upload) -->
        <button 
          v-if="uploadedDocId && !previewData"
          @click="previewChunks"
          :disabled="previewing"
          class="action-btn secondary"
        >
          <span v-if="previewing">Mengekstrak chunks...</span>
          <span v-else>Preview Chunks</span>
        </button>
      </section>

      <!-- Preview Section -->
      <section v-if="previewData" class="preview-section">
        <div class="preview-header">
          <div>
            <h2>Preview: {{ previewData.document_title }}</h2>
            <p>{{ previewData.total_chunks }} chunks ditemukan ({{ previewData.doc_type }})</p>
          </div>
          <div class="preview-actions">
            <button @click="cancelPreview" class="action-btn cancel">Batal</button>
            <button @click="saveDocument" :disabled="saving" class="action-btn primary">
              <span v-if="saving">Menyimpan...</span>
              <span v-else>Simpan ke Index</span>
            </button>
          </div>
        </div>

        <div class="chunks-list">
          <div 
            v-for="(chunk, idx) in previewData.chunks" 
            :key="idx"
            class="chunk-card"
          >
            <div class="chunk-header">
              <span class="chunk-number">#{{ idx + 1 }}</span>
              <span v-if="chunk.pasal" class="chunk-pasal">{{ chunk.pasal }}</span>
              <span v-if="chunk.ayat" class="chunk-ayat">Ayat ({{ chunk.ayat }})</span>
            </div>
            <div class="chunk-content">
              <p>{{ chunk.text }}</p>
            </div>
          </div>
        </div>
        
        <div v-if="previewData.has_more" class="more-notice">
          + {{ previewData.total_chunks - previewData.chunks.length }} chunks lainnya
        </div>
      </section>

      <!-- Documents List -->
      <section class="documents-section">
        <div class="section-header">
          <h2>Dokumen Terindeks</h2>
          <div class="header-actions">
            <button @click="syncFromQdrant" :disabled="syncing" class="sync-btn" title="Sync dari Qdrant">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ spinning: syncing }">
                <path d="M21 12a9 9 0 0 1-9 9m9-9a9 9 0 0 0-9-9m9 9H3m9 9a9 9 0 0 1-9-9m9 9c1.66 0 3-4.03 3-9s-1.34-9-3-9m0 18c-1.66 0-3-4.03-3-9s1.34-9 3-9"/>
              </svg>
              <span v-if="syncing">Syncing...</span>
              <span v-else>Sync Qdrant</span>
            </button>
            <button @click="loadDocuments" class="refresh-btn" title="Refresh">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
          </div>
        </div>

        <div v-if="loading" class="loading">Memuat dokumen...</div>
        
        <div v-else-if="documents.length === 0" class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <p>Belum ada dokumen</p>
          <small>Upload dokumen PDF untuk memulai</small>
        </div>

        <div v-else class="documents-grid">
          <div 
            v-for="doc in documents" 
            :key="doc.doc_id"
            class="document-card"
            @click="goToDetail(doc.doc_id)"
          >
            <div class="doc-header">
              <div class="doc-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <div class="doc-info">
                <h3>{{ doc.document_title || doc.filename }}</h3>
                <div class="doc-meta">
                  <span class="doc-type">{{ doc.doc_type }}</span>
                  <span class="doc-chunks">{{ doc.chunk_count }} chunks</span>
                  <span class="doc-size">{{ formatFileSize(doc.file_size) }}</span>
                </div>
              </div>
              <div class="doc-status" :class="doc.status">
                {{ doc.status }}
              </div>
              <button @click.stop="confirmDelete(doc)" class="delete-btn">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="deleteTarget" class="modal-overlay" @click="deleteTarget = null">
      <div class="modal" @click.stop>
        <h3>Hapus Dokumen?</h3>
        <p>Yakin ingin menghapus <strong>{{ deleteTarget.document_title || deleteTarget.filename }}</strong>?</p>
        <p class="warning">{{ deleteTarget.chunk_count }} chunks akan dihapus dari index.</p>
        <div class="modal-actions">
          <button @click="deleteTarget = null" class="action-btn cancel">Batal</button>
          <button @click="deleteDocument" :disabled="deleting" class="action-btn danger">
            <span v-if="deleting">Menghapus...</span>
            <span v-else>Hapus</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Toast Notification -->
    <div v-if="toast" class="toast" :class="toast.type">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const API_BASE = 'http://localhost:8000'

// State
const isDragging = ref(false)
const selectedFile = ref(null)
const uploading = ref(false)
const uploadedDocId = ref(null)
const previewing = ref(false)
const previewData = ref(null)
const saving = ref(false)
const loading = ref(false)
const documents = ref([])
const deleteTarget = ref(null)
const deleting = ref(false)
const toast = ref(null)

// Methods
function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function showToast(message, type = 'success') {
  toast.value = { message, type }
  setTimeout(() => toast.value = null, 3000)
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.name.toLowerCase().endsWith('.pdf')) {
    selectedFile.value = file
    uploadedDocId.value = null
    previewData.value = null
  } else {
    showToast('Hanya file PDF yang didukung', 'error')
  }
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) {
    selectedFile.value = file
    uploadedDocId.value = null
    previewData.value = null
  }
}

function clearFile() {
  selectedFile.value = null
  uploadedDocId.value = null
  previewData.value = null
}

async function uploadFile() {
  if (!selectedFile.value) return
  
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    const resp = await fetch(`${API_BASE}/api/documents/upload`, {
      method: 'POST',
      body: formData
    })
    
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || 'Upload gagal')
    }
    
    const data = await resp.json()
    uploadedDocId.value = data.doc_id
    showToast('Upload berhasil! Klik Preview untuk melihat chunks.')
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    uploading.value = false
  }
}

async function previewChunks() {
  if (!uploadedDocId.value) return
  
  previewing.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents/${uploadedDocId.value}/preview`, {
      method: 'POST'
    })
    
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || 'Preview gagal')
    }
    
    previewData.value = await resp.json()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    previewing.value = false
  }
}

async function saveDocument() {
  if (!uploadedDocId.value) return
  
  saving.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents/${uploadedDocId.value}/save`, {
      method: 'POST'
    })
    
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || 'Indexing gagal')
    }
    
    const data = await resp.json()
    showToast(`Berhasil mengindeks ${data.chunks_indexed} chunks!`)
    
    // Reset and reload
    clearFile()
    loadDocuments()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    saving.value = false
  }
}

function cancelPreview() {
  previewData.value = null
  // Optionally delete the uploaded but not indexed document
}

async function loadDocuments() {
  loading.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents`)
    if (resp.ok) {
      documents.value = await resp.json()
    }
  } catch (e) {
    console.error('Load docs error:', e)
  } finally {
    loading.value = false
  }
}

function goToDetail(docId) {
  router.push(`/documents/${docId}`)
}

function confirmDelete(doc) {
  deleteTarget.value = doc
}

async function deleteDocument() {
  if (!deleteTarget.value) return
  
  deleting.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents/${deleteTarget.value.doc_id}`, {
      method: 'DELETE'
    })
    
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || 'Delete gagal')
    }
    
    showToast('Dokumen berhasil dihapus')
    deleteTarget.value = null
    loadDocuments()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    deleting.value = false
  }
}

const syncing = ref(false)

async function syncFromQdrant() {
  syncing.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/documents/sync`, {
      method: 'POST'
    })
    if (resp.ok) {
      const data = await resp.json()
      if (data.imported > 0) {
        showToast(`Sync: ${data.imported} dokumen baru diimport dari Qdrant`)
      }
    }
  } catch (e) {
    console.error('Sync error:', e)
  } finally {
    syncing.value = false
  }
}

onMounted(async () => {
  // Auto-sync from Qdrant first, then load documents
  await syncFromQdrant()
  await loadDocuments()
})
</script>

<style scoped>
.documents-page {
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

.header-content h1 {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
}

.header-content p {
  color: #a1a1aa;
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #2a2a4a;
  color: #e4e4e7;
  border: none;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.875rem;
  transition: background 0.2s;
}

.back-btn:hover {
  background: #3a3a5a;
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

/* Upload Section */
.upload-section {
  background: #16162a;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.upload-section h2 {
  margin: 0 0 1rem;
  font-size: 1.125rem;
}

.drop-zone {
  border: 2px dashed #3a3a5a;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.drop-zone:hover,
.drop-zone.drag-over {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
}

.drop-zone.has-file {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
}

.drop-content {
  color: #a1a1aa;
}

.drop-content svg {
  margin-bottom: 1rem;
  color: #6366f1;
}

.drop-content span {
  color: #6366f1;
  text-decoration: underline;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  text-align: left;
}

.file-info svg {
  color: #22c55e;
}

.filename {
  font-weight: 500;
  margin: 0;
}

.clear-btn {
  margin-left: auto;
  padding: 0.5rem;
  background: transparent;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
}

.clear-btn:hover {
  color: #ef4444;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 1rem;
}

.action-btn.primary {
  background: #6366f1;
  color: white;
}

.action-btn.primary:hover {
  background: #5558e3;
}

.action-btn.secondary {
  background: #2a2a4a;
  color: #e4e4e7;
}

.action-btn.secondary:hover {
  background: #3a3a5a;
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

.action-btn.danger:hover {
  background: #dc2626;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Preview Section */
.preview-section {
  background: #16162a;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.preview-header h2 {
  margin: 0;
  font-size: 1.125rem;
}

.preview-header p {
  color: #a1a1aa;
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
}

.preview-actions {
  display: flex;
  gap: 0.5rem;
}

.preview-actions .action-btn {
  margin: 0;
}

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 500px;
  overflow-y: auto;
}

.chunk-card {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  padding: 1rem;
}

.chunk-header {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.chunk-number {
  background: #3a3a5a;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.chunk-pasal {
  background: #6366f1;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.chunk-ayat {
  background: #22c55e;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  color: #000;
}

.chunk-content p {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.6;
  color: #d4d4d8;
}

.more-notice {
  text-align: center;
  color: #a1a1aa;
  padding: 1rem;
  font-style: italic;
}

/* Documents Section */
.documents-section {
  background: #16162a;
  border-radius: 12px;
  padding: 1.5rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h2 {
  margin: 0;
  font-size: 1.125rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.sync-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #2a2a4a;
  border: 1px solid #3a3a5a;
  border-radius: 6px;
  color: #e4e4e7;
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.2s;
}

.sync-btn:hover {
  background: #3a3a5a;
  border-color: #6366f1;
}

.sync-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sync-btn .spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.refresh-btn {
  padding: 0.5rem;
  background: transparent;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
}

.refresh-btn:hover {
  color: #6366f1;
}

.loading {
  text-align: center;
  color: #a1a1aa;
  padding: 2rem;
}

.empty-state {
  text-align: center;
  color: #a1a1aa;
  padding: 3rem;
}

.empty-state svg {
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state p {
  margin: 0;
}

.documents-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.document-card {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.document-card:hover {
  border-color: #6366f1;
  transform: translateY(-2px);
}

.doc-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  transition: background 0.2s;
}

.doc-icon {
  color: #6366f1;
}

.doc-info {
  flex: 1;
  min-width: 0;
}

.doc-info h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-meta {
  display: flex;
  gap: 1rem;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: #a1a1aa;
}

.doc-type {
  background: #3a3a5a;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
}

.doc-status {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.doc-status.indexed {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.doc-status.uploaded,
.doc-status.previewed {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.delete-btn {
  padding: 0.5rem;
  background: transparent;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
}

.delete-btn:hover {
  color: #ef4444;
}

.doc-chunks {
  border-top: 1px solid #2a2a4a;
  padding: 1rem;
  background: #14142a;
}

.chunks-mini-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
}

.chunk-mini {
  padding: 0.5rem;
  background: #1a1a2e;
  border-radius: 4px;
  font-size: 0.8125rem;
}

.chunk-mini .chunk-idx {
  color: #6366f1;
  margin-right: 0.5rem;
}

.chunk-mini .chunk-ref {
  color: #22c55e;
  margin-right: 0.5rem;
}

.chunk-mini p {
  margin: 0.25rem 0 0;
  color: #a1a1aa;
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
  border-radius: 12px;
  padding: 1.5rem;
  max-width: 400px;
  width: 90%;
}

.modal h3 {
  margin: 0 0 1rem;
}

.modal p {
  color: #a1a1aa;
  margin: 0 0 0.5rem;
}

.modal .warning {
  color: #ef4444;
  font-size: 0.875rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.modal-actions .action-btn {
  margin: 0;
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
