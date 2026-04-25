import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentsView from '../DocumentsView.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' }
}))

vi.mock('@/services/documentService', () => ({
  uploadDocument: vi.fn().mockResolvedValue({ doc_id: 'doc-1' }),
  previewDocument: vi.fn().mockResolvedValue({
    document_title: 'Test Doc',
    total_chunks: 5,
    doc_type: 'Peraturan',
    chunks: [{ text: 'chunk 1', pasal: null, ayat: null }],
    has_more: false
  }),
  saveDocument: vi.fn().mockResolvedValue({ chunks_indexed: 5 }),
  listDocuments: vi.fn().mockResolvedValue([]),
  syncDocuments: vi.fn().mockResolvedValue({}),
  deleteDocument: vi.fn()
}))

const MB = 1024 * 1024

function makeFile(name, sizeBytes, type = 'application/pdf') {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

function mountView() {
  return mount(DocumentsView, {
    global: {
      stubs: { RouterLink: { template: '<a><slot /></a>' } }
    }
  })
}

describe('DocumentsView — validation UI', () => {
  it('upload button disabled when file has validation error (oversized)', async () => {
    const wrapper = mountView()
    const file = makeFile('big.pdf', 60 * MB)
    await wrapper.vm.handleFileChange(file)
    const btn = wrapper.find('[data-testid="upload-btn"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('validation error message shown when file is oversized', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('big.pdf', 60 * MB))
    expect(wrapper.find('.validation-error').exists()).toBe(true)
    expect(wrapper.find('.validation-error').text()).toContain('50 MB')
  })

  it('no validation error for .docx file under 50 MB', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Laporan.docx', 3 * MB, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
    expect(wrapper.find('.validation-error').exists()).toBe(false)
  })

  it('warning shown (not error) for filename with special characters', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Laporan (FINAL)!.pdf', 1 * MB))
    expect(wrapper.find('.validation-error').exists()).toBe(false)
    expect(wrapper.find('.validation-warning').exists()).toBe(true)
  })
})
