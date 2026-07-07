import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DocumentDetailView from '../DocumentDetailView.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { doc_id: '6' },
    query: {}
  }),
  useRouter: () => ({ push: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' }
}))

vi.mock('@/services/documentService', () => ({
  deleteChunk: vi.fn(),
  deleteDocument: vi.fn(),
  getDocument: vi.fn().mockResolvedValue({
    doc_id: '6',
    document_title: 'Perpres 95 Tahun 2018',
    doc_type: 'peraturan',
    status: 'indexed',
    chunk_count: 1
  }),
  getDocumentChunks: vi.fn().mockResolvedValue([
    {
      id: 42,
      chunk_index: 3,
      text: 'Pasal 1 Dalam Peraturan Presiden ini...',
      context_header: 'BAB I > Pasal 1',
      pasal: 'Pasal 1',
      is_indexed: true,
      canonical_context_id: 'doc6:idx3',
      citation_id: 'perpres95_2018:pasal_1'
    }
  ]),
  updateChunk: vi.fn()
}))

function mountView() {
  return mount(DocumentDetailView, {
    global: {
      stubs: {
        AppHeader: { template: '<header />' },
        RouterLink: { template: '<a><slot /></a>' }
      }
    }
  })
}

describe('DocumentDetailView — context identity metadata', () => {
  it('renders canonical and citation IDs for each chunk', async () => {
    const wrapper = mountView()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Context ID')
    expect(text).toContain('doc6:idx3')
    expect(text).toContain('Citation ID')
    expect(text).toContain('perpres95_2018:pasal_1')
  })
})
