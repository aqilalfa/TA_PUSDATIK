import api from './api'
import { setAccessToken, getAccessToken, clearAccessToken } from './authToken'

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
  }
  return data
}

export const logout = async () => {
  try {
    await api.post('/api/auth/logout')
  } catch (error) {
    console.error('Logout error', error)
  } finally {
    clearAccessToken()
  }
}

export const getToken = () => {
  return getAccessToken()
}

export const isAuthenticated = () => {
  return !!getToken()
}
