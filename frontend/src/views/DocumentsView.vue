<template>
  <div class="documents-page">
    <AppHeader active="documents" />

    <div class="docs-layout">
      <div class="page-title-row docs-hero">
        <div class="page-copy">
          <span class="page-kicker">Arsip regulasi SPBE</span>
          <h1 class="page-title">Manajemen Dokumen</h1>
          <p class="page-title-sub">
            Kelola dokumen hukum, kebijakan, dan rujukan yang menjadi dasar jawaban Asisten Hukum SPBE.
          </p>
          <div class="document-summary" aria-label="Ringkasan dokumen tersedia">
            <span><strong>{{ documents.length }}</strong> dokumen</span>
            <span><strong>{{ indexedCount }}</strong> terindeks</span>
            <span><strong>{{ totalChunks }}</strong> konteks</span>
          </div>
        </div>
        <div class="page-actions">
          <button @click="syncFromQdrant" :disabled="syncing" class="btn-outline sync-button">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ spinning: syncing }">
              <path d="M21 12a9 9 0 0 1-9 9m9-9a9 9 0 0 0-9-9m9 9H3m9 9a9 9 0 0 1-9-9m9 9c1.66 0 3-4.03 3-9s-1.34-9-3-9m0 18c-1.66 0-3-4.03-3-9s1.34-9 3-9"/>
            </svg>
            {{ syncing ? 'Menyinkronkan...' : 'Sinkronisasi Qdrant' }}
          </button>
        </div>
      </div>

      <section class="upload-panel" aria-labelledby="upload-panel-title">
        <div class="upload-panel-header">
          <div>
            <span class="panel-kicker">Unggah sumber</span>
            <h2 id="upload-panel-title">Tambah dokumen rujukan</h2>
            <p>Dokumen yang tersimpan akan diproses menjadi konteks pencarian dan tetap dapat diperiksa kembali.</p>
          </div>
          <span class="upload-policy">PDF, DOC, DOCX · Maks. 50 MB</span>
        </div>

        <div v-if="stepperState !== 'idle'" class="upload-stepper" aria-label="Tahapan unggah dokumen">
          <div class="stepper-step">
            <div class="stepper-circle" :class="stepClass(1)">
              <span v-if="stepClass(1) === 'done'">✓</span>
              <span v-else>1</span>
            </div>
            <span class="stepper-label">Unggah</span>
          </div>
          <div class="stepper-connector" :class="connectorClass(1)"></div>
          <div class="stepper-step">
            <div class="stepper-circle" :class="stepClass(2)">
              <span v-if="stepClass(2) === 'done'">✓</span>
              <span v-else>2</span>
            </div>
            <span class="stepper-label">Preview</span>
          </div>
          <div class="stepper-connector" :class="connectorClass(2)"></div>
          <div class="stepper-step">
            <div class="stepper-circle" :class="stepClass(3)">
              <span v-if="stepClass(3) === 'done'">✓</span>
              <span v-else>3</span>
            </div>
            <span class="stepper-label">Indeks</span>
          </div>
        </div>

        <div
          class="upload-zone"
          :class="{ 'drag-over': isDragging, 'has-file': selectedFile }"
          role="button"
          tabindex="0"
          aria-label="Pilih atau seret dokumen untuk diunggah"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleDrop"
          @click="$refs.fileInput.click()"
          @keydown.enter.prevent="$refs.fileInput.click()"
          @keydown.space.prevent="$refs.fileInput.click()"
        >
          <input type="file" ref="fileInput" accept=".pdf,.doc,.docx" @change="handleFileSelect" hidden />

          <div v-if="!selectedFile" class="upload-content">
            <div class="upload-icon" aria-hidden="true">▤</div>
            <div>
              <div class="upload-title">Pilih dokumen rujukan</div>
              <div class="upload-desc">Seret berkas ke area ini, atau pilih dari komputer.</div>
            </div>
            <div class="upload-browse">Pilih dari komputer</div>
          </div>

          <div v-else class="file-selected">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <div>
              <p class="file-name">{{ selectedFile.name }}</p>
              <small class="file-size">{{ formatFileSize(selectedFile.size) }} · siap divalidasi</small>
            </div>
            <button @click.stop="clearFile" class="file-clear-btn" aria-label="Batalkan pilihan dokumen">✕</button>
          </div>
        </div>

        <div v-if="validationErrors.length" class="validation-error">
          <span v-for="e in validationErrors" :key="e" class="validation-msg">Peringatan: {{ e }}</span>
        </div>
        <div v-if="validationWarnings.length" class="validation-warning">
          <span v-for="w in validationWarnings" :key="w" class="validation-msg">Catatan: {{ w }}</span>
        </div>

        <div v-if="selectedFile && !uploadedDocId" class="upload-actions">
          <button
            data-testid="upload-btn"
            @click="uploadFile"
            :disabled="uploading || validationErrors.length > 0"
            class="btn-primary"
          >
            {{ uploading ? 'Mengunggah...' : 'Unggah dokumen' }}
          </button>
        </div>

        <div v-if="uploading" class="upload-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
          </div>
          <span class="progress-label">{{ uploadProgress }}%</span>
        </div>

        <div v-if="uploadedDocId && !previewData" class="upload-actions">
          <button @click="previewChunks" :disabled="previewing" class="btn-outline">
            {{ previewing ? 'Mengekstrak konteks...' : 'Pratinjau konteks' }}
          </button>
        </div>
      </section>

      <div v-if="previewData" class="preview-section">
        <div class="preview-header">
          <div>
            <h2 class="preview-title">Pratinjau: {{ previewData.document_title }}</h2>
            <p class="preview-meta">{{ previewData.total_chunks }} konteks ditemukan ({{ previewData.doc_type }})</p>
          </div>
          <div class="preview-actions">
            <button @click="cancelPreview" class="btn-ghost">Batal</button>
            <button data-testid="save-btn" @click="saveDocument" :disabled="saving" class="btn-primary">
              {{ saving ? 'Menyimpan...' : 'Simpan ke indeks' }}
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
          + {{ previewData.total_chunks - previewData.chunks.length }} konteks lainnya
        </div>
      </div>

      <div v-if="saveComplete" class="success-card">
        <div class="success-icon" aria-hidden="true">✓</div>
        <div class="success-title">Dokumen berhasil diindeks</div>
        <div class="success-meta">{{ lastChunkCount }} konteks tersimpan · Siap untuk pencarian</div>
        <button data-testid="upload-another-btn" @click="resetUpload" class="btn-outline">
          + Unggah dokumen lain
        </button>
      </div>

      <div class="docs-section">
        <div class="docs-list-header">
          <div>
            <div class="section-heading">Dokumen Tersedia</div>
            <p class="docs-list-subtitle">Daftar sumber yang dapat digunakan sistem untuk menelusuri rujukan SPBE.</p>
          </div>
          <div class="docs-count" v-if="documents.length > 0">{{ documents.length }} dokumen</div>
        </div>

        <div v-if="loading" class="state-loading">Memuat dokumen...</div>

        <div v-else-if="documents.length === 0" class="state-empty">
          <div class="state-icon">▤</div>
          <p>Belum ada dokumen terindeks</p>
          <small>Unggah dokumen resmi untuk mulai membangun rujukan sistem.</small>
        </div>

        <div v-else class="table-responsive">
          <div class="docs-table">
          <div class="docs-thead">
            <div class="docs-row-grid docs-th-row">
              <span>Nama Dokumen</span>
              <span>Ukuran</span>
              <span>Konteks</span>
              <span>Status</span>
              <span>Aksi</span>
            </div>
          </div>
          <div
            v-for="doc in documents"
            :key="doc.doc_id"
            class="docs-row docs-row-grid"
            role="button"
            tabindex="0"
            :aria-label="`Buka detail dokumen ${doc.document_title || doc.filename}`"
            @click="goToDetail(doc.doc_id)"
            @keydown.enter.prevent="goToDetail(doc.doc_id)"
            @keydown.space.prevent="goToDetail(doc.doc_id)"
          >
            <div class="doc-name-cell">
              <span class="doc-name">{{ doc.document_title || doc.filename }}</span>
              <span class="doc-type-tag">{{ doc.doc_type || 'Dokumen' }}</span>
            </div>
            <span class="doc-cell" data-label="Ukuran">{{ formatFileSize(doc.file_size) }}</span>
            <span class="doc-cell" data-label="Konteks">{{ doc.chunk_count || '—' }}</span>
            <span class="doc-cell" data-label="Status">
              <span class="badge" :class="{
                'badge-ok': doc.status === 'indexed',
                'badge-warn': doc.status === 'uploaded' || doc.status === 'previewed'
              }">
                {{ doc.status === 'indexed' ? 'Terindeks' : doc.status === 'previewed' ? 'Pratinjau' : 'Diunggah' }}
              </span>
            </span>
            <span class="doc-cell doc-actions" data-label="Aksi" @click.stop @keydown.stop>
              <button v-if="doc.status !== 'indexed'" @click="goToDetail(doc.doc_id)" class="doc-btn">Lihat</button>
              <button @click="goToDetail(doc.doc_id)" class="doc-btn">Detail</button>
              <button @click="confirmDelete(doc)" class="doc-btn danger">Hapus</button>
            </span>
          </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="deleteTarget" class="modal-overlay" @click="deleteTarget = null">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title" @click.stop>
        <h3 id="delete-modal-title" class="modal-title">Hapus Dokumen?</h3>
        <p class="modal-body">Yakin ingin menghapus <strong>{{ deleteTarget.document_title || deleteTarget.filename }}</strong>?</p>
        <p class="modal-warning">{{ deleteTarget.chunk_count }} konteks akan dihapus dari indeks.</p>
        <div class="modal-actions">
          <button @click="deleteTarget = null" class="btn-ghost">Batal</button>
          <button @click="deleteDocument" :disabled="deleting" class="btn-danger">
            {{ deleting ? 'Menghapus...' : 'Hapus' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="toast" :class="toast.type">{{ toast.message }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
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

const indexedCount = computed(() => documents.value.filter((doc) => doc.status === 'indexed').length)
const totalChunks = computed(() => documents.value.reduce((total, doc) => total + Number(doc.chunk_count || 0), 0))

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
    showToast('Unggah berhasil. Lanjutkan ke pratinjau konteks.')
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
    showToast(e.message || 'Gagal memuat dokumen', 'error')
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
  min-height: 100dvh;
  background: var(--color-cream);
}

.docs-layout {
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 32px 56px;
}

.docs-hero,
.upload-panel,
.preview-section,
.success-card,
.docs-table,
.state-loading,
.state-empty {
  border: 1px solid var(--color-border-blue);
  border-radius: 14px;
  background: var(--color-white);
  box-shadow: 0 14px 34px rgba(18, 45, 87, 0.06);
}

.docs-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
  padding: 22px 24px;
}

.page-copy {
  max-width: 720px;
}

.page-kicker,
.panel-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--color-gold-ink);
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
}

.page-kicker::before,
.panel-kicker::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--color-gold);
  box-shadow: 0 0 0 4px rgba(201, 168, 76, 0.14);
}

.page-title {
  margin: 0 0 6px;
  color: var(--color-text-heading);
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.15;
  text-wrap: balance;
}

.page-title-sub {
  max-width: 68ch;
  margin: 0;
  color: var(--color-text-panel-muted);
  font-family: var(--font-ui);
  font-size: 14px;
  line-height: 1.6;
}

.document-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.document-summary span,
.upload-policy,
.docs-count {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--color-border-blue-light);
  border-radius: 999px;
  background: var(--color-surface-page);
  color: var(--color-text-panel-muted);
  font-family: var(--font-ui);
  font-size: 12px;
}

.document-summary span {
  gap: 5px;
}

.document-summary strong {
  color: var(--color-text-heading);
  font-weight: 700;
}

.page-actions,
.preview-actions,
.upload-actions,
.modal-actions {
  display: flex;
  gap: 8px;
}

.btn-primary,
.btn-outline,
.btn-ghost,
.btn-danger,
.doc-btn,
.file-clear-btn {
  min-height: 38px;
  border-radius: 8px;
  cursor: pointer;
  font-family: var(--font-ui);
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.btn-primary,
.btn-outline {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 18px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.btn-primary {
  border: none;
  background: var(--color-action-blue-dark);
  color: var(--color-white);
  box-shadow: 0 10px 20px rgba(11, 54, 112, 0.14);
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-action-blue);
  transform: translateY(-1px);
}

.btn-outline {
  border: 1px solid var(--color-border-blue);
  background: var(--color-white);
  color: var(--color-text-heading);
}

.btn-outline:hover:not(:disabled) {
  border-color: var(--color-action-blue);
  background: var(--color-surface-soft-blue);
  color: var(--color-action-blue-dark);
}

.btn-ghost,
.btn-danger {
  padding: 8px 14px;
  font-size: 11px;
}

.btn-ghost {
  border: 1px solid var(--color-border);
  background: var(--color-white);
  color: var(--color-text-panel-muted);
}

.btn-ghost:hover {
  border-color: var(--color-border-blue);
  background: var(--color-surface-page);
  color: var(--color-text-heading);
}

.btn-danger {
  border: none;
  background: var(--color-danger);
  color: var(--color-white);
}

.btn-danger:hover:not(:disabled) {
  background: #9f2f24;
}

.btn-primary:disabled,
.btn-outline:disabled,
.btn-danger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}

.btn-primary:focus-visible,
.btn-outline:focus-visible,
.btn-ghost:focus-visible,
.btn-danger:focus-visible,
.doc-btn:focus-visible,
.file-clear-btn:focus-visible,
.upload-zone:focus-visible,
.docs-row:focus-visible {
  outline: 3px solid rgba(201, 168, 76, 0.42);
  outline-offset: 3px;
}

.sync-button {
  min-height: 40px;
  white-space: nowrap;
}

.spinning {
  animation: spin 1s linear infinite;
}

.upload-panel,
.preview-section,
.success-card {
  margin-bottom: 28px;
  padding: 24px;
}

.upload-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.upload-panel-header h2 {
  margin: 0 0 6px;
  color: var(--color-text-heading);
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.2;
}

.upload-panel-header p,
.docs-list-subtitle {
  max-width: 62ch;
  margin: 0;
  color: var(--color-text-panel-muted);
  font-size: 13px;
  line-height: 1.6;
}

.upload-policy {
  flex: 0 0 auto;
  color: var(--color-text-blue-muted);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.upload-stepper {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
  padding: 14px 18px;
  border: 1px solid var(--color-border-blue-light);
  border-radius: 12px;
  background: var(--color-surface-page);
}

.stepper-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stepper-circle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  border-radius: 50%;
  font: 700 11px var(--font-ui);
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}

.stepper-circle.idle {
  border-color: var(--color-border-blue);
  background: var(--color-white);
  color: var(--color-text-panel-muted);
}

.stepper-circle.active {
  background: var(--color-action-blue-dark);
  color: var(--color-white);
}

.stepper-circle.in-progress {
  background: var(--color-gold);
  color: var(--color-navy-dark);
}

.stepper-circle.done {
  background: var(--color-status-ok-text);
  color: var(--color-white);
}

.stepper-connector {
  flex: 1;
  height: 2px;
  margin: 0 8px 16px;
  background: var(--color-border-blue);
  transition: background 0.2s ease;
}

.stepper-connector.done {
  background: var(--color-gold);
}

.stepper-label {
  color: var(--color-text-panel-muted);
  font: 600 9px var(--font-ui);
  letter-spacing: 0.6px;
}

.upload-zone {
  margin-bottom: 16px;
  padding: 26px;
  border: 1.5px dashed var(--color-border-blue);
  border-radius: 14px;
  background: linear-gradient(180deg, var(--color-white), var(--color-surface-page));
  cursor: pointer;
  text-align: left;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.upload-zone:hover,
.upload-zone.drag-over {
  border-color: var(--color-action-blue);
  background: var(--color-surface-soft-blue);
  box-shadow: inset 0 0 0 1px rgba(11, 74, 191, 0.08);
}

.upload-zone.has-file {
  border-color: var(--color-status-ok-border);
  border-style: solid;
  background: var(--color-status-ok-bg);
}

.upload-content,
.file-selected {
  display: flex;
  align-items: center;
  gap: 16px;
}

.upload-icon,
.state-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  border: 1px solid var(--color-border-blue);
  border-radius: 12px;
  background: var(--color-white);
  color: var(--color-action-blue-dark);
  font-size: 22px;
}

.upload-title {
  margin-bottom: 4px;
  color: var(--color-text-heading);
  font: 700 15px var(--font-ui);
}

.upload-desc,
.file-size,
.preview-meta,
.progress-label,
.docs-count {
  color: var(--color-text-panel-muted);
  font-family: var(--font-ui);
}

.upload-desc {
  font-size: 13px;
  line-height: 1.5;
}

.upload-browse {
  margin-left: auto;
  padding: 7px 20px;
  border: 1px solid var(--color-border-blue);
  border-radius: 8px;
  background: var(--color-white);
  color: var(--color-text-heading);
  font: 600 11px var(--font-ui);
}

.file-selected {
  color: var(--color-status-ok-text);
}

.file-selected svg {
  flex: 0 0 auto;
}

.file-name {
  margin: 0;
  color: var(--color-text-heading);
  font: 600 14px var(--font-ui);
}

.file-size {
  font-size: 11px;
}

.file-clear-btn {
  min-width: 38px;
  margin-left: auto;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-danger);
  font-size: 14px;
}

.file-clear-btn:hover {
  border-color: var(--color-danger-bg);
  background: var(--color-danger-bg);
}

.upload-actions {
  justify-content: flex-end;
  margin-top: 14px;
}

.upload-progress {
  margin-top: 14px;
}

.progress-bar {
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-border-blue-light);
}

.progress-fill {
  height: 5px;
  border-radius: 999px;
  background: var(--color-action-blue);
  transition: none;
}

.progress-label {
  display: block;
  margin-top: 4px;
  text-align: right;
  font-size: 10px;
}

.validation-error,
.validation-warning {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  font-family: var(--font-ui);
}

.validation-error {
  border: 1px solid rgba(192, 57, 43, 0.35);
  background: var(--color-danger-bg);
}

.validation-warning {
  border: 1px solid var(--color-status-warn-border);
  background: var(--color-status-warn-bg);
}

.validation-error .validation-msg {
  color: var(--color-danger);
}

.validation-warning .validation-msg {
  color: var(--color-status-warn-text);
}

.validation-msg {
  font-size: 12px;
  line-height: 1.5;
}

.preview-header,
.docs-list-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.preview-header {
  margin-bottom: 16px;
}

.preview-title,
.success-title,
.modal-title {
  margin: 0;
  color: var(--color-text-heading);
  font-family: var(--font-display);
  font-weight: 700;
}

.preview-title {
  margin-bottom: 4px;
  font-size: 18px;
}

.preview-meta {
  margin: 0;
  font-size: 12px;
}

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.chunk-card {
  padding: 10px 12px;
  border: 1px solid var(--color-border-blue-light);
  border-radius: 10px;
  background: var(--color-surface-page);
}

.chunk-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.chunk-num,
.chunk-tag {
  font-family: var(--font-ui);
  font-size: 9px;
  font-weight: 600;
}

.chunk-num {
  color: var(--color-text-panel-muted);
}

.chunk-tag {
  padding: 2px 7px;
  border-radius: 6px;
}

.chunk-tag.pasal {
  border: 1px solid var(--color-status-info-border);
  background: var(--color-status-info-bg);
  color: var(--color-status-info-text);
}

.chunk-tag.ayat {
  border: 1px solid var(--color-status-ok-border);
  background: var(--color-status-ok-bg);
  color: var(--color-status-ok-text);
}

.chunk-text {
  margin: 0;
  color: var(--color-text-panel);
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.6;
}

.more-notice {
  padding: 12px;
  color: var(--color-text-panel-muted);
  font-family: var(--font-ui);
  font-size: 12px;
  text-align: center;
}

.success-card {
  border-color: var(--color-status-ok-border);
  background: var(--color-status-ok-bg);
  text-align: center;
}

.success-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-bottom: 10px;
  border-radius: 999px;
  background: var(--color-status-ok-text);
  color: var(--color-white);
  font-size: 22px;
  font-weight: 700;
}

.success-title {
  margin-bottom: 6px;
  color: var(--color-status-ok-text);
  font-size: 16px;
}

.success-meta {
  margin-bottom: 16px;
  color: var(--color-text-panel-muted);
  font: 12px var(--font-ui);
}

.docs-section {
  margin-top: 8px;
}

.docs-list-header {
  align-items: flex-end;
  margin-bottom: 14px;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  color: var(--color-text-heading);
  font: 600 9px var(--font-ui);
  letter-spacing: 1.4px;
  text-transform: uppercase;
}

.section-heading::after {
  content: '';
  flex: 1;
  height: 1px;
  min-width: 80px;
  background: var(--color-border-blue);
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.docs-table {
  overflow: hidden;
  min-width: 700px; /* Ensure table has minimum width before scrolling */
}

.docs-row-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px 78px 116px 168px;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
}

.docs-thead {
  border-bottom: 1px solid var(--color-border-blue-light);
  background: var(--color-surface-page);
}

.docs-th-row span {
  color: var(--color-text-blue-muted);
  font: 600 9px var(--font-ui);
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.docs-row {
  border-bottom: 1px solid var(--color-border-blue-light);
  cursor: pointer;
  transition: background 0.16s ease, box-shadow 0.16s ease;
}

.docs-row:last-child {
  border-bottom: none;
}

.docs-row:hover {
  background: var(--color-surface-page);
}

.doc-name-cell {
  min-width: 0;
}

.doc-name {
  display: block;
  overflow: hidden;
  color: var(--color-text-heading);
  font: 600 13px var(--font-ui);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-type-tag {
  color: var(--color-text-blue-muted);
  font: 9px var(--font-ui);
}

.doc-cell {
  color: var(--color-text-panel-muted);
  font: 12px var(--font-ui);
}

.badge {
  display: inline-block;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.badge-ok {
  border: 1px solid var(--color-status-ok-border);
  background: var(--color-status-ok-bg);
  color: var(--color-status-ok-text);
}

.badge-warn {
  border: 1px solid var(--color-status-warn-border);
  background: var(--color-status-warn-bg);
  color: var(--color-status-warn-text);
}

.doc-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  cursor: default;
}

.doc-btn {
  min-height: 44px; /* Increased touch target for pointer: coarse / all screens */
  padding: 8px 12px;
  border: 1px solid var(--color-border-blue);
  background: var(--color-white);
  color: var(--color-text-blue-muted);
  font-size: 11px;
  font-weight: 600;
}

.doc-btn:hover {
  border-color: var(--color-action-blue);
  background: var(--color-surface-soft-blue);
  color: var(--color-action-blue-dark);
}

.doc-btn.danger:hover {
  border-color: rgba(192, 57, 43, 0.35);
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.state-loading,
.state-empty {
  padding: 44px 24px;
  color: var(--color-text-panel-muted);
  font-family: var(--font-ui);
  text-align: center;
}

.state-empty {
  display: grid;
  justify-items: center;
  gap: 8px;
}

.state-empty p {
  margin: 0;
  color: var(--color-text-heading);
  font-weight: 700;
}

.state-empty small {
  max-width: 42ch;
  color: var(--color-text-panel-muted);
  font-size: 11px;
  line-height: 1.5;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(7, 31, 69, 0.48);
}

.modal {
  width: 90%;
  max-width: 400px;
  padding: 24px;
  border: 1px solid var(--color-border-blue);
  border-radius: 14px;
  background: var(--color-white);
  box-shadow: 0 24px 60px rgba(7, 31, 69, 0.22);
}

.modal-title {
  margin-bottom: 12px;
  font-size: 18px;
}

.modal-body {
  margin: 0 0 6px;
  color: var(--color-text-panel);
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.6;
}

.modal-warning {
  margin: 0 0 20px;
  color: var(--color-danger);
  font: 12px var(--font-ui);
}

.modal-actions {
  justify-content: flex-end;
}

.toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1001;
  padding: 12px 20px;
  border-radius: 10px;
  box-shadow: 0 16px 36px rgba(7, 31, 69, 0.22);
  color: var(--color-white);
  font: 12px var(--font-ui);
  animation: slideInRight 0.3s ease;
}

.toast.success {
  background: var(--color-navy);
}

.toast.error {
  background: var(--color-danger);
}

.toast.info {
  background: #755f3f;
}

@media (max-width: 920px) {
  .docs-layout {
    padding: 20px 16px 40px;
  }

  .docs-hero,
  .preview-header,
  .docs-list-header,
  .upload-panel-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .document-summary,
  .page-actions,
  .preview-actions,
  .upload-actions,
  .upload-policy {
    width: 100%;
  }

  .document-summary span {
    flex: 1 1 150px;
    justify-content: center;
  }

  .page-actions > *,
  .preview-actions > *,
  .upload-actions > * {
    width: 100%;
    min-height: 44px;
  }

  .upload-policy {
    justify-content: center;
  }

  .upload-zone {
    padding: 26px 18px;
  }

  .upload-stepper {
    overflow-x: auto;
  }

  .upload-browse {
    margin-left: 0;
  }

  .docs-thead {
    display: none;
  }

  .docs-table {
    display: grid;
    gap: 12px;
    border: 0;
    background: transparent;
    box-shadow: none;
  }

  .docs-row-grid {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 16px;
  }

  .docs-row {
    border: 1px solid var(--color-border-blue);
    border-radius: 12px;
    background: var(--color-white);
    box-shadow: 0 10px 24px rgba(18, 45, 87, 0.05);
  }

  .docs-row:hover {
    background: var(--color-white);
  }

  .doc-cell {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 32px;
    padding-top: 8px;
    border-top: 1px solid var(--color-border-blue-light);
    color: var(--color-text);
  }

  .doc-cell::before {
    content: attr(data-label);
    color: var(--color-text-panel-muted);
    font: 700 10px var(--font-ui);
    letter-spacing: 0.6px;
    text-transform: uppercase;
  }

  .doc-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    padding-top: 10px;
  }

  .doc-actions::before {
    content: none;
  }

  .doc-btn {
    min-height: 44px;
    padding: 8px 10px;
    font-size: 11px;
  }
}

@media (max-width: 560px) {
  .docs-layout {
    padding: 16px 12px 32px;
  }

  .docs-hero,
  .upload-panel {
    padding: 18px;
  }

  .page-title {
    font-size: 24px;
  }

  .document-summary span {
    flex-basis: 100%;
  }

  .upload-content {
    display: grid;
    justify-items: start;
  }

  .upload-browse {
    width: 100%;
    text-align: center;
  }

  .file-selected {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: flex-start;
  }

  .file-clear-btn {
    min-width: 44px;
    min-height: 44px;
  }

  .preview-section,
  .success-card {
    padding: 16px;
  }

  .preview-actions,
  .doc-actions {
    grid-template-columns: 1fr;
  }

  .modal {
    width: calc(100% - 24px);
    padding: 20px;
  }

  .modal-actions {
    flex-direction: column-reverse;
  }

  .modal-actions > * {
    min-height: 44px;
    width: 100%;
  }

  .toast {
    right: 12px;
    bottom: 12px;
    left: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .btn-primary,
  .btn-outline,
  .btn-ghost,
  .btn-danger,
  .doc-btn,
  .file-clear-btn,
  .upload-zone,
  .docs-row,
  .stepper-circle,
  .stepper-connector {
    transition: none;
  }

  .spinning,
  .toast {
    animation: none;
  }
}
</style>
