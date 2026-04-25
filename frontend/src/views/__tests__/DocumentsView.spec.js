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

describe('DocumentsView — stepper + progress + success', () => {
  it('stepper step 1 is active after file is selected', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    const circles = wrapper.findAll('.stepper-circle')
    expect(circles[0].classes()).toContain('active')
    expect(circles[1].classes()).toContain('idle')
    expect(circles[2].classes()).toContain('idle')
  })

  it('stepper step 2 is active after successful upload', async () => {
    const { uploadDocument } = await import('@/services/documentService')
    uploadDocument.mockResolvedValueOnce({ doc_id: 'doc-1' })
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    await wrapper.find('[data-testid="upload-btn"]').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    const circles = wrapper.findAll('.stepper-circle')
    expect(circles[0].classes()).toContain('done')
    expect(circles[1].classes()).toContain('active')
  })

  it('progress bar is visible while uploading', async () => {
    let resolveUpload
    const { uploadDocument } = await import('@/services/documentService')
    uploadDocument.mockImplementationOnce(() => new Promise(r => { resolveUpload = r }))
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    wrapper.find('[data-testid="upload-btn"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.upload-progress').exists()).toBe(true)
    resolveUpload({ doc_id: 'doc-1' })
  })

  it('success card shown after saveDocument completes', async () => {
    const wrapper = mountView()
    await wrapper.vm.handleFileChange(makeFile('Perpres.pdf', 1 * MB))
    wrapper.vm.uploadedDocId = 'doc-1'
    wrapper.vm.previewData = { document_title: 'Test', total_chunks: 5, doc_type: 'PP', chunks: [], has_more: false }
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-testid="save-btn"]').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.success-card').exists()).toBe(true)
    expect(wrapper.find('.success-card').text()).toContain('5')
  })

  it('clicking Unggah Dokumen Lain resets all state', async () => {
    const wrapper = mountView()
    wrapper.vm.saveComplete = true
    wrapper.vm.selectedFile = makeFile('test.pdf', 1 * MB)
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-testid="upload-another-btn"]').trigger('click')
    expect(wrapper.find('.success-card').exists()).toBe(false)
    expect(wrapper.vm.selectedFile).toBeNull()
  })

  it('all stepper steps show done after save completes', async () => {
    const wrapper = mountView()
    wrapper.vm.saveComplete = true
    await wrapper.vm.$nextTick()
    const circles = wrapper.findAll('.stepper-circle')
    circles.forEach(c => expect(c.classes()).toContain('done'))
  })
})
