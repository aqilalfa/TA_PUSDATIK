import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/auth', () => ({
  isAuthenticated: vi.fn(() => true),
  isAdminUser: vi.fn(() => false)
}))

describe('router document management authorization', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('redirects authenticated non-admin users away from /documents', async () => {
    const router = (await import('../router')).default

    await router.push('/documents')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('chat')
  })

  it('redirects authenticated non-admin users away from document detail routes', async () => {
    const router = (await import('../router')).default

    await router.push('/documents/doc-123')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('chat')
  })
})
