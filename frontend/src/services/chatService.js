import api, { API_BASE_URL, getErrorMessage } from './api'

export async function getModels() {
  try {
    const { data } = await api.get('/api/models')
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to fetch models'))
  }
}

export async function getDefaultModel() {
  try {
    const { data } = await api.get('/api/models/default')
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to fetch default model'))
  }
}

export async function setDefaultModel(model) {
  try {
    const { data } = await api.post('/api/models/default', null, {
      params: { model }
    })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to set default model'))
  }
}

export async function getSessions() {
  try {
    const { data } = await api.get('/api/sessions')
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to fetch sessions'))
  }
}

export async function getSession(sessionId) {
  try {
    const { data } = await api.get(`/api/sessions/${sessionId}`)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to fetch session'))
  }
}

export async function getSessionHistory(sessionId) {
  try {
    const { data } = await api.get(`/api/chat/history/${sessionId}`)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to fetch chat history'))
  }
}

export async function deleteSession(sessionId) {
  try {
    const { data } = await api.delete(`/api/sessions/${sessionId}`)
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to delete session'))
  }
}

export async function updateSessionTitle(sessionId, title) {
  try {
    const { data } = await api.put(`/api/sessions/${sessionId}/title`, null, {
      params: { title }
    })
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Failed to update session title'))
  }
}

export async function checkHealth() {
  try {
    const { data } = await api.get('/api/health')
    return data
  } catch (error) {
    throw new Error(getErrorMessage(error, 'Health check failed'))
  }
}

export async function streamChat(payload, handlers = {}) {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    throw new Error(`HTTP error: ${response.status}`)
  }

  if (!response.body) {
    throw new Error('Stream body is not available')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    const events = buffer.split('\n\n')
    buffer = events.pop() || ''

    for (const eventBlock of events) {
      if (!eventBlock.trim()) continue

      let eventType = 'message'
      const dataLines = []

      for (const line of eventBlock.split('\n')) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          dataLines.push(line.slice(6))
        }
      }

      const payloadText = dataLines.join('\n')
      if (!payloadText) continue

      let data
      try {
        data = JSON.parse(payloadText)
      } catch (error) {
        console.warn('SSE parse error:', error, payloadText)
        continue
      }

      if (eventType === 'retrieval' && handlers.onRetrieval) {
        await handlers.onRetrieval(data)
      } else if (eventType === 'token' && handlers.onToken) {
        await handlers.onToken(data)
      } else if (eventType === 'complete' && handlers.onComplete) {
        await handlers.onComplete(data)
      } else if (eventType === 'session' && handlers.onSession) {
        await handlers.onSession(data)
      } else if (eventType === 'validation' && handlers.onValidation) {
        await handlers.onValidation(data)
      } else if (eventType === 'error' && handlers.onError) {
        await handlers.onError(data)
      }
    }
  }
}
