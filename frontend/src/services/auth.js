import api from './api'
import { setAccessToken, getAccessToken, clearAccessToken } from './authToken'

const USER_KEY = 'spbe_current_user'

function storageAvailable(method) {
  return typeof localStorage !== 'undefined' && typeof localStorage[method] === 'function'
}

function safeStorageGet(key) {
  if (!storageAvailable('getItem')) return null
  return localStorage.getItem(key)
}

function safeStorageSet(key, value) {
  if (!storageAvailable('setItem')) return
  localStorage.setItem(key, value)
}

function safeStorageRemove(key) {
  if (!storageAvailable('removeItem')) return
  localStorage.removeItem(key)
}

function decodeTokenPayload(token) {
  if (!token) return null

  try {
    const [, payload] = token.split('.')
    if (!payload) return null

    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const decoded = atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '='))
    return JSON.parse(decoded)
  } catch (error) {
    console.warn('Failed to decode access token payload', error)
    return null
  }
}

function normalizeUserProfile(user) {
  if (!user) return null

  return {
    username: user.username || user.email || '',
    display_name: user.display_name || user.name || user.username || user.email || 'Pengguna SPBE',
    roles: Array.isArray(user.roles) ? user.roles : [],
    department: user.department || user.dept || '',
    auth_provider: user.auth_provider || 'local',
    session_id: user.session_id || user.sid || ''
  }
}

function storeCurrentUser(user) {
  const normalized = normalizeUserProfile(user)
  if (!normalized) {
    safeStorageRemove(USER_KEY)
    return null
  }

  safeStorageSet(USER_KEY, JSON.stringify(normalized))
  return normalized
}

function clearCurrentUser() {
  safeStorageRemove(USER_KEY)
}

export const login = async (username, password) => {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  
  const response = await api.post('/api/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  })
  
  const data = response.data
  if (data && data.access_token) {
    setAccessToken(data.access_token)
    storeCurrentUser(data.user || decodeTokenPayload(data.access_token))
  }
  return data
}

export const logout = async () => {
  try {
    await api.post('/api/auth/logout')
  } catch (error) {
    console.error('Logout error', error)
  } finally {
    clearCurrentUser()
    clearAccessToken()
  }
}

export const getToken = () => {
  return getAccessToken()
}

export const isAuthenticated = () => {
  return !!getToken()
}

export const getCurrentUserProfile = () => {
  const stored = safeStorageGet(USER_KEY)
  if (stored) {
    try {
      return normalizeUserProfile(JSON.parse(stored))
    } catch (error) {
      console.warn('Failed to parse stored user profile', error)
      clearCurrentUser()
    }
  }

  const tokenProfile = normalizeUserProfile(decodeTokenPayload(getToken()))
  if (tokenProfile) {
    storeCurrentUser(tokenProfile)
  }
  return tokenProfile
}

export const formatRoleLabel = (role) => {
  const roleMap = {
    admin_pusdatik: 'Admin PUSDATIK',
    evaluator_spbe: 'Evaluator SPBE',
    user: 'Pengguna'
  }

  return roleMap[role] || String(role || 'Pengguna')
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
