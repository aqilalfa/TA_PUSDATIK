import axios from 'axios'

const FALLBACK_API_URL = 'http://localhost:8000'

function normalizeApiBaseUrl(value) {
  const candidate = String(value || '').trim()
  if (!candidate) {
    return FALLBACK_API_URL
  }

  const hasProtocol = /^[a-zA-Z][a-zA-Z\d+.-]*:\/\//.test(candidate)
  const urlText = hasProtocol ? candidate : `http://${candidate}`

  try {
    const parsed = new URL(urlText)
    const normalized = `${parsed.origin}${parsed.pathname}`.replace(/\/$/, '')
    return normalized || FALLBACK_API_URL
  } catch (error) {
    console.warn(
      `[api] Invalid VITE_API_URL="${candidate}". Falling back to ${FALLBACK_API_URL}.`,
      error
    )
    return FALLBACK_API_URL
  }
}

const rawApiUrl = import.meta.env.VITE_API_URL
export const API_BASE_URL = normalizeApiBaseUrl(rawApiUrl)

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000
})

export function getErrorMessage(error, fallbackMessage = 'Request failed') {
  if (error?.response?.data?.detail) {
    if (typeof error.response.data.detail === 'string') {
      return error.response.data.detail
    }
    if (Array.isArray(error.response.data.detail)) {
      return error.response.data.detail.map((d) => d.msg || String(d)).join(', ')
    }
  }

  if (error?.message) {
    return error.message
  }

  return fallbackMessage
}

export default api
