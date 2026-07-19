import { beforeEach, describe, expect, it, vi } from 'vitest'

const post = vi.fn()

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      post,
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() }
      }
    }))
  }
}))

vi.mock('../authToken', () => ({
  getAccessToken: vi.fn(),
  clearAccessToken: vi.fn(),
  setAccessToken: vi.fn()
}))

const { refreshAccessToken } = await import('../api')

describe('refreshAccessToken single-flight', () => {
  beforeEach(() => {
    post.mockReset()
  })

  it('shares one backend refresh request across concurrent callers', async () => {
    let resolveRefresh
    post.mockReturnValueOnce(new Promise((resolve) => {
      resolveRefresh = resolve
    }))

    const first = refreshAccessToken()
    const second = refreshAccessToken()

    expect(post).toHaveBeenCalledTimes(1)

    resolveRefresh({ data: { access_token: 'new-token' } })

    await expect(first).resolves.toBe('new-token')
    await expect(second).resolves.toBe('new-token')
  })

  it('starts a new request after the shared refresh completes', async () => {
    post
      .mockResolvedValueOnce({ data: { access_token: 'first-token' } })
      .mockResolvedValueOnce({ data: { access_token: 'second-token' } })

    await expect(refreshAccessToken()).resolves.toBe('first-token')
    await expect(refreshAccessToken()).resolves.toBe('second-token')

    expect(post).toHaveBeenCalledTimes(2)
  })
})
