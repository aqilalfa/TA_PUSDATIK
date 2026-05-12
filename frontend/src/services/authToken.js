const TOKEN_KEY = 'spbe_access_token'

let memoryToken = null

export const setAccessToken = (token) => {
  memoryToken = token || null

  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

export const getAccessToken = () => {
  if (memoryToken) {
    return memoryToken
  }

  return localStorage.getItem(TOKEN_KEY)
}

export const clearAccessToken = () => {
  memoryToken = null
  localStorage.removeItem(TOKEN_KEY)
}
