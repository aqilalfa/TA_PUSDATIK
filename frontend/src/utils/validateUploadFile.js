const MAX_SIZE = 50 * 1024 * 1024
const ACCEPTED_EXT = /\.(pdf|doc|docx)$/i
const SAFE_NAME = /^[a-zA-Z0-9_\-.()\s]+$/

export function validateFile(file) {
  const errors = []
  const warnings = []

  if (!ACCEPTED_EXT.test(file.name)) {
    errors.push('Format tidak didukung. Gunakan PDF, DOC, atau DOCX.')
  }

  if (file.size > MAX_SIZE) {
    errors.push(`Ukuran file (${formatSize(file.size)}) melebihi batas 50 MB.`)
  }

  if (!SAFE_NAME.test(file.name)) {
    const suggested = file.name.replace(/[^a-zA-Z0-9_\-.()\s]/g, '').replace(/\s+/g, '_')
    warnings.push(`Nama file mengandung karakter tidak umum. Saran: ${suggested}`)
  }

  return { errors, warnings }
}

function formatSize(bytes) {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}
