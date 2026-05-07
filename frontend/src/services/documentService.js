import api, { API_BASE_URL, getErrorMessage } from './api'

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
    const { data } = await api.post(`/api/documents/${docId}/preview`)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Preview failed'))
  }
}

export async function saveDocument(docId) {
  try {
    const { data } = await api.post(`/api/documents/${docId}/save`)
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
