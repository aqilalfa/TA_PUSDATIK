<template>
  <div class="documents-page">
    <!-- Topbar -->
    <nav class="topbar">
      <div class="topbar-brand">
        <div class="topbar-logo">B</div>
        <div>
          <div class="topbar-title">SPBE Asisten</div>
          <div class="topbar-subtitle">Badan Siber dan Sandi Negara</div>
        </div>
      </div>
      <div class="topbar-nav">
        <router-link to="/home" class="topbar-nav-link">Beranda</router-link>
        <router-link to="/" class="topbar-nav-link">Chat</router-link>
        <router-link to="/documents" class="topbar-nav-link active">Dokumen</router-link>
      </div>
    </nav>

    <div class="docs-layout">
      <!-- Page header -->
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Manajemen Dokumen</h1>
          <p class="page-title-sub">Kelola sumber pengetahuan sistem RAG SPBE</p>
        </div>
        <div class="page-actions">
          <button @click="syncFromQdrant" :disabled="syncing" class="btn-outline">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ spinning: syncing }">
              <path d="M21 12a9 9 0 0 1-9 9m9-9a9 9 0 0 0-9-9m9 9H3m9 9a9 9 0 0 1-9-9m9 9c1.66 0 3-4.03 3-9s-1.34-9-3-9m0 18c-1.66 0-3-4.03-3-9s1.34-9 3-9"/>
            </svg>
            {{ syncing ? 'Menyinkronkan...' : '↻ Sinkronisasi Qdrant' }}
          </button>
        </div>
      </div>

      <!-- Stepper -->
      <div v-if="stepperState !== 'idle'" class="upload-stepper">
        <div class="stepper-step">
          <div class="stepper-circle" :class="stepClass(1)">
            <span v-if="stepClass(1) === 'done'">✓</span>
            <span v-else>1</span>
          </div>
          <span class="stepper-label">UNGGAH</span>
        </div>
        <div class="stepper-connector" :class="connectorClass(1)"></div>
        <div class="stepper-step">
          <div class="stepper-circle" :class="stepClass(2)">
            <span v-if="stepClass(2) === 'done'">✓</span>
            <span v-else>2</span>
          </div>
          <span class="stepper-label">PREVIEW</span>
        </div>
        <div class="stepper-connector" :class="connectorClass(2)"></div>
        <div class="stepper-step">
          <div class="stepper-circle" :class="stepClass(3)">
            <span v-if="stepClass(3) === 'done'">✓</span>
            <span v-else>3</span>
          </div>
          <span class="stepper-label">INDEKS</span>
        </div>
      </div>

      <!-- Upload zone -->
      <div
        class="upload-zone"
        :class="{ 'drag-over': isDragging, 'has-file': selectedFile }"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="handleDrop"
        @click="$refs.fileInput.click()"
      >
        <input type="file" ref="fileInput" accept=".pdf,.doc,.docx" @change="handleFileSelect" hidden />

        <div v-if="!selectedFile" class="upload-content">
          <div class="upload-icon">📄</div>
          <div class="upload-title">Seret & Lepas File di Sini</div>
          <div class="upload-desc">Mendukung PDF, DOC, DOCX · Maks. 50 MB</div>
          <div class="upload-or">atau</div>
          <div class="upload-browse">Pilih dari Komputer</div>
        </div>

        <div v-else class="file-selected">
          <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <div>
            <p class="file-name">{{ selectedFile.name }}</p>
            <small class="file-size">{{ formatFileSize(selectedFile.size) }}</small>
          </div>
          <button @click.stop="clearFile" class="file-clear-btn">✕</button>
        </div>
      </div>

      <!-- Validation messages -->
      <div v-if="validationErrors.length" class="validation-error">
        <span v-for="e in validationErrors" :key="e" class="validation-msg">⚠ {{ e }}</span>
      </div>
      <div v-if="validationWarnings.length" class="validation-warning">
        <span v-for="w in validationWarnings" :key="w" class="validation-msg">💡 {{ w }}</span>
      </div>

      <!-- Upload/Preview actions -->
      <div v-if="selectedFile && !uploadedDocId" class="upload-actions">
        <button
          data-testid="upload-btn"
          @click="uploadFile"
          :disabled="uploading || validationErrors.length > 0"
          class="btn-primary"
        >
          {{ uploading ? 'Mengunggah...' : 'Unggah Dokumen' }}
        </button>
      </div>
      <!-- Progress bar: shown while upload is in progress, regardless of uploadedDocId state -->
      <div v-if="uploading" class="upload-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
        </div>
        <span class="progress-label">{{ uploadProgress }}%</span>
      </div>
      <div v-if="uploadedDocId && !previewData" class="upload-actions">
        <button @click="previewChunks" :disabled="previewing" class="btn-outline">
          {{ previewing ? 'Mengekstrak chunks...' : 'Pratinjau Chunks' }}
        </button>
      </div>

      <!-- Preview section -->
      <div v-if="previewData" class="preview-section">
        <div class="preview-header">
          <div>
            <h2 class="preview-title">Pratinjau: {{ previewData.document_title }}</h2>
            <p class="preview-meta">{{ previewData.total_chunks }} chunk ditemukan ({{ previewData.doc_type }})</p>
          </div>
          <div class="preview-actions">
            <button @click="cancelPreview" class="btn-ghost">Batal</button>
            <button data-testid="save-btn" @click="saveDocument" :disabled="saving" class="btn-primary">
              {{ saving ? 'Menyimpan...' : 'Simpan ke Indeks' }}
            </button>
          </div>
        </div>

        <div class="chunks-list">
          <div v-for="(chunk, idx) in previewData.chunks" :key="idx" class="chunk-card">
            <div class="chunk-header">
              <span class="chunk-num">#{{ idx + 1 }}</span>
              <span v-if="chunk.pasal" class="chunk-tag pasal">{{ chunk.pasal }}</span>
              <span v-if="chunk.ayat" class="chunk-tag ayat">Ayat ({{ chunk.ayat }})</span>
            </div>
            <p class="chunk-text">{{ chunk.text }}</p>
          </div>
        </div>

        <div v-if="previewData.has_more" class="more-notice">
          + {{ previewData.total_chunks - previewData.chunks.length }} chunk lainnya
        </div>
      </div>

      <!-- Success card -->
      <div v-if="saveComplete" class="success-card">
        <div class="success-icon">✅</div>
        <div class="success-title">Dokumen berhasil diindeks</div>
        <div class="success-meta">{{ lastChunkCount }} chunks tersimpan · Siap untuk pencarian</div>
        <button data-testid="upload-another-btn" @click="resetUpload" class="btn-outline">
          + Unggah Dokumen Lain
        </button>
      </div>

      <!-- Document list -->
      <div class="docs-section">
        <div class="docs-list-header">
          <div class="section-heading">Dokumen Tersedia</div>
          <div class="docs-count" v-if="documents.length > 0">{{ documents.length }} dokumen</div>
        </div>

        <div v-if="loading" class="state-loading">Memuat dokumen...</div>

        <div v-else-if="documents.length === 0" class="state-empty">
          <div style="font-size:32px;margin-bottom:10px;">📄</div>
          <p>Belum ada dokumen terindekas</p>
          <small>Unggah dokumen PDF untuk memulai</small>
        </div>

        <div v-else class="docs-table">
          <div class="docs-thead">
            <div class="docs-row-grid docs-th-row">
              <span>Nama Dokumen</span>
              <span>Ukuran</span>
              <span>Chunk</span>
              <span>Status</span>
              <span>Aksi</span>
            </div>
          </div>
          <div
            v-for="doc in documents"
            :key="doc.doc_id"
            class="docs-row docs-row-grid"
            @click="goToDetail(doc.doc_id)"
          >
            <div class="doc-name-cell">
              <span class="doc-name">{{ doc.document_title || doc.filename }}</span>
              <span class="doc-type-tag">{{ doc.doc_type }}</span>
            </div>
            <span class="doc-cell">{{ formatFileSize(doc.file_size) }}</span>
            <span class="doc-cell">{{ doc.chunk_count || '—' }}</span>
            <span class="doc-cell">
              <span class="badge" :class="{
                'badge-ok': doc.status === 'indexed',
                'badge-warn': doc.status === 'uploaded' || doc.status === 'previewed'
              }">
                {{ doc.status === 'indexed' ? '✓ Terindeks' : doc.status === 'previewed' ? '👁 Pratinjau' : '⏳ Diunggah' }}
              </span>
            </span>
            <span class="doc-cell doc-actions" @click.stop>
              <button v-if="doc.status !== 'indexed'" @click="goToDetail(doc.doc_id)" class="doc-btn">Lihat</button>
              <button @click="goToDetail(doc.doc_id)" class="doc-btn">Detail</button>
              <button @click="confirmDelete(doc)" class="doc-btn danger">Hapus</button>
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Modal -->
    <div v-if="deleteTarget" class="modal-overlay" @click="deleteTarget = null">
      <div class="modal" @click.stop>
        <h3 class="modal-title">Hapus Dokumen?</h3>
        <p class="modal-body">Yakin ingin menghapus <strong>{{ deleteTarget.document_title || deleteTarget.filename }}</strong>?</p>
        <p class="modal-warning">{{ deleteTarget.chunk_count }} chunk akan dihapus dari indeks.</p>
        <div class="modal-actions">
          <button @click="deleteTarget = null" class="btn-ghost">Batal</button>
          <button @click="deleteDocument" :disabled="deleting" class="btn-danger">
            {{ deleting ? 'Menghapus...' : 'Hapus' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="toast.type">{{ toast.message }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  deleteDocument as deleteDocumentById,
  listDocuments,
  previewDocument,
  saveDocument as saveDocumentById,
  syncDocuments,
  uploadDocument
} from '@/services/documentService'
import { validateFile } from '@/utils/validateUploadFile'

const router = useRouter()

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
const syncing = ref(false)
const validationErrors = ref([])
const validationWarnings = ref([])
const uploadProgress = ref(0)
const saveComplete = ref(false)
const lastChunkCount = ref(0)

const stepperState = computed(() => {
  if (saveComplete.value) return 'done'
  if (previewData.value) return 'step3'
  if (uploadedDocId.value) return 'step2'
  if (selectedFile.value) return 'step1'
  return 'idle'
})

function stepClass(stepNum) {
  const s = stepperState.value
  if (s === 'done') return 'done'
  if (s === 'idle') return 'idle'
  const active = s === 'step1' ? 1 : s === 'step2' ? 2 : 3
  if (stepNum < active) return 'done'
  if (stepNum === active) {
    const inProg = (stepNum === 1 && uploading.value)
                 || (stepNum === 2 && previewing.value)
                 || (stepNum === 3 && saving.value)
    return inProg ? 'in-progress' : 'active'
  }
  return 'idle'
}

function connectorClass(afterStep) {
  const s = stepperState.value
  if (s === 'done') return 'done'
  const active = s === 'step1' ? 1 : s === 'step2' ? 2 : s === 'step3' ? 3 : 0
  return afterStep < active ? 'done' : ''
}

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

function handleFileChange(file) {
  if (!file) return
  const { errors, warnings } = validateFile(file)
  validationErrors.value = errors
  validationWarnings.value = warnings
  selectedFile.value = file
  uploadedDocId.value = null
  previewData.value = null
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) handleFileChange(file)
}

function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) handleFileChange(file)
}

function clearFile() {
  selectedFile.value = null
  uploadedDocId.value = null
  previewData.value = null
  saveComplete.value = false
  lastChunkCount.value = 0
  uploadProgress.value = 0
  validationErrors.value = []
  validationWarnings.value = []
}

function resetUpload() {
  clearFile()
}

async function uploadFile() {
  if (!selectedFile.value || validationErrors.value.length > 0) return
  uploading.value = true
  uploadProgress.value = 0
  try {
    const data = await uploadDocument(selectedFile.value, (pct) => {
      uploadProgress.value = pct
    })
    uploadedDocId.value = data.doc_id
    showToast('Upload berhasil! Klik Pratinjau untuk melihat chunks.')
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
    previewData.value = await previewDocument(uploadedDocId.value)
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
    const data = await saveDocumentById(uploadedDocId.value)
    lastChunkCount.value = data.chunks_indexed
    saveComplete.value = true
    loadDocuments()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    saving.value = false
  }
}

function cancelPreview() { previewData.value = null }

async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await listDocuments()
  } catch (e) {
    console.error('Load docs error:', e)
  } finally {
    loading.value = false
  }
}

function goToDetail(docId) { router.push(`/documents/${docId}`) }
function confirmDelete(doc) { deleteTarget.value = doc }

async function deleteDocument() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteDocumentById(deleteTarget.value.doc_id)
    showToast('Dokumen berhasil dihapus')
    deleteTarget.value = null
    loadDocuments()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    deleting.value = false
  }
}

async function syncFromQdrant() {
  syncing.value = true
  try {
    const data = await syncDocuments()
    const imported = Number(data.imported || 0)
    const updated = Number(data.updated || 0)
    const skipped = Number(data.skipped || 0)
    if (imported > 0 || updated > 0) {
      showToast(`Sync selesai: ${imported} baru, ${updated} diperbarui`)
    } else {
      showToast(`Sync selesai: tidak ada perubahan (${skipped} dilewati)`, 'info')
    }
    await loadDocuments()
  } catch (e) {
    showToast(e.message, 'error')
    console.error('Sync error:', e)
  } finally {
    syncing.value = false
  }
}

onMounted(async () => {
  await syncFromQdrant()
})

defineExpose({ handleFileChange, uploadedDocId, previewData, saveComplete, selectedFile, lastChunkCount })
</script>

<style scoped>
.documents-page {
  min-height: 100vh;
  background: var(--color-cream);
}

.docs-layout {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px;
}

/* Page title */
.page-title-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 28px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

.page-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-navy);
  margin: 0 0 3px;
}

.page-title-sub {
  font-family: var(--font-display);
  font-size: 13px;
  color: #8b7355;
  font-style: italic;
  margin: 0;
}

.page-actions { display: flex; gap: 8px; }

/* Buttons */
.btn-primary {
  background: var(--color-navy);
  color: white;
  border: none;
  padding: 8px 18px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  font-family: var(--font-ui);
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-primary:hover:not(:disabled) { background: var(--color-navy-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-outline {
  background: transparent;
  color: var(--color-navy);
  border: 1px solid var(--color-navy);
  padding: 7px 16px;
  font-size: 11px;
  font-family: var(--font-ui);
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-outline:hover:not(:disabled) { background: #eef2f9; }
.btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-ghost {
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
.btn-ghost:hover { border-color: var(--color-text-muted); color: var(--color-text); }

.btn-danger {
  background: #c0392b;
  color: white;
  border: none;
  padding: 7px 16px;
  font-size: 11px;
  font-family: var(--font-ui);
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-danger:hover:not(:disabled) { background: #a93226; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

/* Upload zone */
.upload-zone {
  border: 2px dashed var(--color-border);
  border-radius: 3px;
  background: white;
  padding: 32px;
  text-align: center;
  margin-bottom: 20px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.upload-zone:hover, .upload-zone.drag-over {
  border-color: var(--color-navy);
  background: #f5f8fd;
}
.upload-zone.has-file {
  border-color: var(--color-status-ok-border);
  background: var(--color-status-ok-bg);
  border-style: solid;
}

.upload-content { color: var(--color-text-muted); }
.upload-icon { font-size: 28px; margin-bottom: 10px; }
.upload-title {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-navy);
  margin-bottom: 5px;
}
.upload-desc {
  font-family: var(--font-body);
  font-size: 12px;
  color: var(--color-text-muted);
  font-style: italic;
  margin-bottom: 10px;
}
.upload-or {
  font-size: 10px;
  color: var(--color-text-light);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin: 8px 0;
}
.upload-browse {
  display: inline-block;
  padding: 7px 20px;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  font-size: 11px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  transition: all 0.15s;
}
.upload-zone:hover .upload-browse {
  border-color: var(--color-navy);
  color: var(--color-navy);
}

.file-selected {
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  color: var(--color-status-ok-text);
}
.file-name { font-weight: 600; margin: 0; font-size: 13px; color: var(--color-navy); }
.file-size { font-size: 11px; color: var(--color-text-muted); }
.file-clear-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  font-size: 14px;
  padding: 4px 6px;
  border-radius: 2px;
  transition: color 0.15s;
}
.file-clear-btn:hover { color: #c0392b; }

.upload-actions { margin-bottom: 20px; }

/* Preview */
.preview-section {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 3px;
  padding: 20px;
  margin-bottom: 28px;
}
.preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}
.preview-title {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-navy);
  margin: 0 0 3px;
}
.preview-meta { font-size: 12px; color: var(--color-text-muted); margin: 0; }
.preview-actions { display: flex; gap: 8px; }

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.chunk-card {
  border: 1px solid var(--color-border-light);
  border-radius: 2px;
  padding: 10px 12px;
  background: #faf9f7;
}
.chunk-header {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  align-items: center;
}
.chunk-num {
  font-size: 9px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-weight: 600;
}
.chunk-tag {
  font-size: 9px;
  padding: 2px 7px;
  border-radius: 2px;
  font-family: var(--font-ui);
  font-weight: 600;
}
.chunk-tag.pasal { background: var(--color-status-info-bg); color: var(--color-status-info-text); border: 1px solid var(--color-status-info-border); }
.chunk-tag.ayat { background: var(--color-status-ok-bg); color: var(--color-status-ok-text); border: 1px solid var(--color-status-ok-border); }
.chunk-text {
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-text);
  margin: 0;
}
.more-notice {
  text-align: center;
  color: var(--color-text-muted);
  padding: 12px;
  font-style: italic;
  font-family: var(--font-body);
  font-size: 12px;
}

/* Documents table */
.docs-section { }
.docs-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.docs-count { font-size: 11px; color: var(--color-text-muted); font-family: var(--font-ui); }

.docs-table {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 3px;
  overflow: hidden;
}

.docs-row-grid {
  display: grid;
  grid-template-columns: 1fr 80px 70px 110px 140px;
  gap: 12px;
  padding: 11px 16px;
  align-items: center;
}

.docs-thead {
  background: #faf9f7;
  border-bottom: 1px solid var(--color-border);
}
.docs-th-row span {
  font-size: 9px;
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  font-family: var(--font-ui);
}

.docs-row {
  border-bottom: 1px solid var(--color-border-light);
  cursor: pointer;
  transition: background 0.15s;
}
.docs-row:last-child { border-bottom: none; }
.docs-row:hover { background: #faf9f7; }

.doc-name-cell { min-width: 0; }
.doc-name {
  font-size: 12px;
  color: var(--color-navy);
  font-weight: 500;
  font-family: var(--font-ui);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}
.doc-type-tag {
  font-size: 9px;
  color: var(--color-text-light);
  font-family: var(--font-ui);
  font-style: italic;
}

.doc-cell {
  font-size: 11px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
}

.doc-actions {
  display: flex;
  gap: 4px;
  cursor: default;
}

.doc-btn {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  padding: 3px 8px;
  font-size: 9px;
  color: var(--color-text-muted);
  cursor: pointer;
  font-family: var(--font-ui);
  transition: all 0.15s;
}
.doc-btn:hover { border-color: var(--color-navy); color: var(--color-navy); }
.doc-btn.danger:hover { border-color: #c0392b; color: #c0392b; }

/* State messages */
.state-loading, .state-empty {
  text-align: center;
  padding: 40px;
  color: var(--color-text-muted);
  font-family: var(--font-body);
  font-style: italic;
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 3px;
}
.state-empty small { display: block; font-size: 11px; margin-top: 4px; }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(26, 58, 107, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 3px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(26, 58, 107, 0.15);
}
.modal-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-navy);
  margin: 0 0 12px;
}
.modal-body { font-family: var(--font-body); font-size: 13px; color: var(--color-text); margin: 0 0 6px; }
.modal-warning { font-size: 12px; color: #c0392b; font-family: var(--font-ui); margin: 0 0 20px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  border-radius: 2px;
  font-size: 12px;
  font-family: var(--font-ui);
  z-index: 1001;
  animation: slideInRight 0.3s ease;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.toast.success { background: var(--color-navy); color: white; }
.toast.error { background: #c0392b; color: white; }
.toast.info { background: #8b7355; color: white; }

.validation-error {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fff8f8;
  border: 1px solid #e74c3c;
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.validation-warning {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.validation-msg {
  font-size: 12px;
  line-height: 1.5;
}

.validation-error .validation-msg { color: #c0392b; }
.validation-warning .validation-msg { color: #856404; }

.upload-stepper {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  padding: 14px 20px;
  background: var(--color-white);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.stepper-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stepper-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-ui);
  transition: background 0.2s, color 0.2s;
}

.stepper-circle.idle { background: var(--color-border); color: #aaa; }
.stepper-circle.active { background: var(--color-navy); color: white; }
.stepper-circle.in-progress { background: var(--color-gold); color: var(--color-navy-dark); }
.stepper-circle.done { background: #2e7d32; color: white; }

.stepper-connector {
  flex: 1;
  height: 2px;
  background: var(--color-border);
  margin: 0 8px;
  margin-bottom: 16px;
  transition: background 0.2s;
}

.stepper-connector.done { background: var(--color-gold); }

.stepper-label {
  font-size: 8px;
  letter-spacing: 1px;
  font-weight: 600;
  font-family: var(--font-ui);
  color: #aaa;
  text-transform: uppercase;
}

.upload-progress {
  margin-top: 10px;
}

.progress-bar {
  background: var(--color-border);
  border-radius: 2px;
  height: 5px;
  overflow: hidden;
}

.progress-fill {
  height: 5px;
  background: var(--color-gold);
  border-radius: 2px;
  transition: width 0.2s ease;
}

.progress-label {
  display: block;
  text-align: right;
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 3px;
  font-family: var(--font-ui);
}

.success-card {
  border: 1px solid #2e7d32;
  border-radius: 4px;
  background: #f0faf0;
  padding: 24px;
  text-align: center;
  margin-bottom: 24px;
}

.success-icon { font-size: 32px; margin-bottom: 8px; }

.success-title {
  font-size: 16px;
  font-weight: 600;
  color: #2e7d32;
  font-family: var(--font-display);
  margin-bottom: 6px;
}

.success-meta {
  font-size: 12px;
  color: #555;
  font-family: var(--font-ui);
  margin-bottom: 16px;
}
</style>
