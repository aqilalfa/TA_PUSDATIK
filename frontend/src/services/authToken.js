const TOKEN_KEY = 'spbe_access_token'

let memoryToken = null

function storageAvailable(method) {
  return typeof localStorage !== 'undefined' && typeof localStorage[method] === 'function'
}

export const setAccessToken = (token) => {
  memoryToken = token || null

  if (token) {
    if (storageAvailable('setItem')) {
      localStorage.setItem(TOKEN_KEY, token)
    }
  } else {
    if (storageAvailable('removeItem')) {
      localStorage.removeItem(TOKEN_KEY)
    }
  }
}

export const getAccessToken = () => {
  if (memoryToken) {
    return memoryToken
  }

  if (!storageAvailable('getItem')) {
    return null
  }

  return localStorage.getItem(TOKEN_KEY)
}

export const clearAccessToken = () => {
  memoryToken = null
  if (storageAvailable('removeItem')) {
    localStorage.removeItem(TOKEN_KEY)
  }
}
