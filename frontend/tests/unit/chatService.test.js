import { describe, expect, it, vi, beforeEach } from 'vitest'

const apiMock = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn()
}

vi.mock('@/services/api', () => ({
  default: apiMock,
  API_BASE_URL: 'http://localhost:5173',
  authenticatedFetch: vi.fn(),
  getErrorMessage: vi.fn((_error, fallback) => fallback)
}))

describe('chatService API paths', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.get.mockResolvedValue({ data: [] })
    apiMock.post.mockResolvedValue({ data: {} })
    apiMock.put.mockResolvedValue({ data: {} })
    apiMock.delete.mockResolvedValue({ data: {} })
  })

  it('uses canonical trailing slash paths for collection endpoints', async () => {
    const { getModels, getSessions } = await import('@/services/chatService')

    await getModels()
    await getSessions()

    expect(apiMock.get).toHaveBeenCalledWith('/api/models/')
    expect(apiMock.get).toHaveBeenCalledWith('/api/sessions/')
  })
})
