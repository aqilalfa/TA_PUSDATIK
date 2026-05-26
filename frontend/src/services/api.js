import axios from 'axios'
import { getAccessToken, clearAccessToken, setAccessToken } from './authToken'

const FALLBACK_API_URL = 'http://localhost:8000'

export const DEFAULT_API_TIMEOUT_MS = 30_000
export const LONG_DOCUMENT_OPERATION_TIMEOUT_MS = 10 * 60 * 1000

function getDefaultApiBaseUrl() {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin
  }

  return FALLBACK_API_URL
}

function normalizeApiBaseUrl(value) {
  const candidate = String(value || '').trim()
  if (!candidate) {
    return getDefaultApiBaseUrl()
  }

  const hasProtocol = /^[a-zA-Z][a-zA-Z\d+.-]*:\/\//.test(candidate)
  const urlText = hasProtocol ? candidate : `http://${candidate}`

  try {
    const parsed = new URL(urlText)
    const normalized = `${parsed.origin}${parsed.pathname}`.replace(/\/$/, '')
    return normalized || getDefaultApiBaseUrl()
  } catch (error) {
    console.warn(
      `[api] Invalid VITE_API_URL="${candidate}". Falling back to current origin.`,
      error
    )
    return getDefaultApiBaseUrl()
  }
}

const rawApiUrl = import.meta.env.VITE_API_URL
export const API_BASE_URL = normalizeApiBaseUrl(rawApiUrl)

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_API_TIMEOUT_MS
})

const refreshClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_API_TIMEOUT_MS,
  withCredentials: true
})

export const SESSION_EXPIRED_NOTICE_KEY = 'spbe_session_expired_notice'

function redirectToLoginWithSessionNotice() {
  if (typeof window === 'undefined') return
  if (window.location.pathname.includes('/login')) return

  window.sessionStorage.setItem(
    SESSION_EXPIRED_NOTICE_KEY,
    'Sesi Anda telah berakhir. Silakan login kembali.'
  )
  clearAccessToken()
  window.location.href = '/login?reason=session-expired'
}

export async function refreshAccessToken() {
  const { data } = await refreshClient.post('/api/auth/refresh', {})
  const newToken = data?.access_token
  if (!newToken) {
    throw new Error('Refresh response did not include an access token')
  }

  setAccessToken(newToken)
  return newToken
}

export async function authenticatedFetch(input, init = {}) {
  const buildRequest = (token) => {
    const headers = new Headers(init.headers || {})
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }

    return {
      ...init,
      headers
    }
  }

  let response = await fetch(input, buildRequest(getAccessToken()))

  if (response.status !== 401) {
    return response
  }

  try {
    const newToken = await refreshAccessToken()
    response = await fetch(input, buildRequest(newToken))
    return response
  } catch (refreshError) {
    if (!window.location.pathname.includes('/login')) {
      redirectToLoginWithSessionNotice()
    }
    throw refreshError
  }
}

// Request interceptor to attach token
api.interceptors.request.use(config => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, error => {
  return Promise.reject(error)
})

// Response interceptor to handle 401 Unauthorized
api.interceptors.response.use(response => {
  return response
}, error => {
  const originalRequest = error.config || {}

  if (error.response && error.response.status === 401 && !originalRequest._retry) {
    originalRequest._retry = true

    return refreshAccessToken()
      .then((newToken) => {
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      })
      .catch((refreshError) => {
        if (!window.location.pathname.includes('/login') && !String(originalRequest.url || '').includes('/api/auth/login')) {
          redirectToLoginWithSessionNotice()
        }
        return Promise.reject(refreshError)
      })
  }
  return Promise.reject(error)
})

export function getErrorMessage(error, fallbackMessage = 'Request failed') {
  if (error?.code === 'ECONNABORTED') {
    return 'Permintaan melebihi batas waktu. Dokumen besar mungkin masih diproses; coba lagi beberapa saat lagi.'
  }

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
