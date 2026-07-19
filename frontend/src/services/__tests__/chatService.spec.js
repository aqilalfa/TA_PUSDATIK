import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({
  API_BASE_URL: 'http://test',
  default: {},
  authenticatedFetch: vi.fn(),
  getErrorMessage: vi.fn()
}))

const { authenticatedFetch } = await import('../api')
const { streamChat } = await import('../chatService')

function streamResponse(text) {
  const bytes = new TextEncoder().encode(text)
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: vi.fn()
          .mockResolvedValueOnce({ done: false, value: bytes })
          .mockResolvedValueOnce({ done: true })
      })
    }
  }
}

describe('streamChat hardened SSE events', () => {
  beforeEach(() => authenticatedFetch.mockReset())

  it('dispatches meta, replace, security, and llm09_guard handlers', async () => {
    authenticatedFetch.mockResolvedValue(streamResponse([
      'event: meta\ndata: {"request_id":"r1"}',
      'event: replace\ndata: {"answer":"safe"}',
      'event: security\ndata: {"blocked":true}',
      'event: llm09_guard\ndata: {"blocked":true}',
      ''
    ].join('\n\n')))
    const handlers = {
      onMeta: vi.fn(),
      onReplace: vi.fn(),
      onSecurity: vi.fn(),
      onLlm09Guard: vi.fn()
    }

    await streamChat({ message: 'q' }, handlers)

    expect(handlers.onMeta).toHaveBeenCalledWith({ request_id: 'r1' })
    expect(handlers.onReplace).toHaveBeenCalledWith({ answer: 'safe' })
    expect(handlers.onSecurity).toHaveBeenCalledWith({ blocked: true })
    expect(handlers.onLlm09Guard).toHaveBeenCalledWith({ blocked: true })
  })
})
