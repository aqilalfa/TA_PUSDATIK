import { beforeEach, describe, expect, it, vi } from 'vitest'

const authenticatedFetch = vi.fn()

vi.mock('../api', () => ({
  API_BASE_URL: 'http://localhost:8000',
  LONG_DOCUMENT_OPERATION_TIMEOUT_MS: 1000,
  authenticatedFetch: (...args) => authenticatedFetch(...args),
  getErrorMessage: (error, fallback) => error?.message || fallback,
  default: {},
}))

import { openDocumentFile } from '../documentService'

describe('openDocumentFile', () => {
  beforeEach(() => {
    authenticatedFetch.mockReset()
    vi.restoreAllMocks()
  })

  it('opens a tab synchronously then navigates it to the PDF blob URL', async () => {
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    authenticatedFetch.mockResolvedValue({
      ok: true,
      blob: async () => blob,
    })

    const tab = { location: { href: 'about:blank' }, close: vi.fn() }
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(tab)
    const createObjectURL = vi.fn(() => 'blob:http://localhost/pdf-1')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', {
      createObjectURL,
      revokeObjectURL,
    })

    await openDocumentFile('doc-abc')

    expect(openSpy).toHaveBeenCalledWith('about:blank', '_blank')
    expect(tab.opener).toBe(null)
    expect(authenticatedFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/rag/documents/by-doc-id/doc-abc/file'
    )
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(tab.location.href).toBe('blob:http://localhost/pdf-1')
  })

  it('closes the placeholder tab and throws a clear error when HTTP fails', async () => {
    authenticatedFetch.mockResolvedValue({
      ok: false,
      status: 404,
    })

    const tab = { location: { href: 'about:blank' }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(tab)

    await expect(openDocumentFile('missing')).rejects.toThrow(
      /File PDF tidak ditemukan|HTTP 404/i
    )
    expect(tab.close).toHaveBeenCalled()
  })
})
