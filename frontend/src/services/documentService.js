import api, {
  API_BASE_URL,
  LONG_DOCUMENT_OPERATION_TIMEOUT_MS,
  authenticatedFetch,
  getErrorMessage
} from './api'

export async function uploadDocument(file, onProgress) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/api/documents/upload', formData, {
      onUploadProgress: (e) => {
        if (typeof onProgress === 'function' && e.total > 0) {
          onProgress(Math.min(100, Math.round((e.loaded / e.total) * 100)))
        }
      }
    })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Upload failed'))
  }
}

export async function previewDocument(docId) {
  try {
    const { data } = await api.post(`/api/documents/${docId}/preview`, undefined, {
      timeout: LONG_DOCUMENT_OPERATION_TIMEOUT_MS
    })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Preview failed'))
  }
}

export async function saveDocument(docId) {
  try {
    const { data } = await api.post(`/api/documents/${docId}/save`, undefined, {
      timeout: LONG_DOCUMENT_OPERATION_TIMEOUT_MS
    })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Indexing failed'))
  }
}

export async function listDocuments() {
  try {
    const { data } = await api.get('/api/documents')
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to load documents'))
  }
}

export async function syncDocuments() {
  try {
    const { data } = await api.post('/api/documents/sync')
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Sync failed'))
  }
}

export async function getDocument(docId) {
  try {
    const { data } = await api.get(`/api/documents/${docId}`)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to load document'))
  }
}

export async function getDocumentChunks(docId, limit = 50, offset = 0) {
  try {
    const { data } = await api.get(`/api/documents/${docId}/chunks`, {
      params: { limit, offset }
    })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to load chunks'))
  }
}

export async function updateChunk(chunkId, text) {
  try {
    const { data } = await api.put(`/api/documents/chunks/${chunkId}`, { text })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to update chunk'))
  }
}

export async function deleteChunk(chunkId) {
  try {
    const { data } = await api.delete(`/api/documents/chunks/${chunkId}`)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to delete chunk'))
  }
}

export async function deleteDocument(docId) {
  try {
    const { data } = await api.delete(`/api/documents/${docId}`)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to delete document'))
  }
}

/**
 * Returns a direct URL to open/download the original PDF for a document.
 * Gunakan sebagai href atau window.open — bukan fetch.
 */
export function getDocumentFileUrl(docId) {
  return `${API_BASE_URL}/api/rag/documents/by-doc-id/${docId}/file`
}

function pdfOpenErrorMessage(status) {
  if (status === 401) return 'Sesi berakhir. Login ulang untuk membuka PDF.'
  if (status === 403) return 'Akses ke file PDF ditolak.'
  if (status === 404) return 'File PDF tidak ditemukan di server.'
  return `Gagal membuka PDF (HTTP ${status}).`
}

/**
 * Open original PDF in a new tab.
 * Opens about:blank synchronously (keeps user-gesture so popup blockers allow it),
 * then navigates to the authenticated blob URL after fetch.
 */
export async function openDocumentFile(docId) {
  if (!docId) {
    throw new Error('Dokumen tidak memiliki ID file.')
  }

  // Must open before any await — async window.open is blocked by browsers.
  // Do NOT pass "noopener" here: modern browsers then return null and we
  // cannot navigate the tab after the authenticated fetch completes.
  const tab = window.open('about:blank', '_blank')
  if (!tab) {
    throw new Error(
      'Browser memblokir tab baru. Izinkan pop-up untuk situs ini, lalu coba lagi.'
    )
  }
  try {
    tab.opener = null
  } catch {
    // some browsers lock opener after open
  }

  try {
    const response = await authenticatedFetch(getDocumentFileUrl(docId))
    if (!response.ok) {
      throw new Error(pdfOpenErrorMessage(response.status))
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    tab.location.href = url
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    try {
      tab.close()
    } catch {
      // ignore close failures on already-closed tabs
    }
    throw error
  }
}

/**
 * Fetch a single chunk by doc_id + chunk_index.
 * Digunakan oleh CitationPopup untuk menampilkan preview teks chunk.
 */
export async function getChunkByIndex(docId, chunkIndex) {
  try {
    const { data } = await api.get(
      `/api/rag/documents/by-doc-id/${docId}/chunks/${chunkIndex}`
    )
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to fetch chunk'))
  }
}
