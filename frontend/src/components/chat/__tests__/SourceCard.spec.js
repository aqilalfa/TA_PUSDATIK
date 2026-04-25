import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SourceCard from '../SourceCard.vue'

const baseSource = {
  id: 1,
  doc_id: 'doc-abc',
  document: 'Perpres No. 95 Tahun 2018',
  citation_title: 'Perpres No. 95 Tahun 2018',
  section: 'Pasal 1 Ayat 3',
  score: 0.87,
  snippet: 'penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi',
  hierarchy_path: 'BAB I › Ketentuan Umum'
}

describe('SourceCard', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders document title and section', () => {
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    expect(wrapper.find('.source-title').text()).toContain('Perpres No. 95')
    expect(wrapper.find('.source-meta').text()).toContain('Pasal 1 Ayat 3')
  })

  it('shows score when source.score > 0', () => {
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    expect(wrapper.find('.source-score').text()).toContain('0.87')
  })

  it('does not show score element when score is 0', () => {
    const wrapper = mount(SourceCard, { props: { source: { ...baseSource, score: 0 } } })
    expect(wrapper.find('.source-score').exists()).toBe(false)
  })

  it('renders score safely when score is provided as a string', () => {
    const wrapper = mount(SourceCard, { props: { source: { ...baseSource, score: '0.87' } } })
    expect(wrapper.find('.source-score').text()).toContain('0.87')
  })

  it('renders snippet in expand panel when present', () => {
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    expect(wrapper.find('.expand-snippet').text()).toContain('penyelenggaraan pemerintahan')
  })

  it('does not render snippet element when snippet is absent', () => {
    const wrapper = mount(SourceCard, { props: { source: { ...baseSource, snippet: undefined } } })
    expect(wrapper.find('.expand-snippet').exists()).toBe(false)
  })

  it('calls window.open with correct URL on click when doc_id present', async () => {
    vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = mount(SourceCard, { props: { source: baseSource } })
    await wrapper.find('.source-card-wrapper').trigger('click')
    expect(window.open).toHaveBeenCalledWith('/documents/doc-abc', '_blank', 'noopener,noreferrer')
  })

  it('does not call window.open when doc_id is empty', async () => {
    vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = mount(SourceCard, {
      props: { source: { ...baseSource, doc_id: '' } }
    })
    await wrapper.find('.source-card-wrapper').trigger('click')
    expect(window.open).not.toHaveBeenCalled()
  })
})
