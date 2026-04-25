import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import ChatSidebar from '../ChatSidebar.vue'

const NOW = new Date('2026-04-25T10:00:00')
const YESTERDAY = new Date('2026-04-24T10:00:00')
const THREE_DAYS_AGO = new Date('2026-04-22T10:00:00')
const TEN_DAYS_AGO = new Date('2026-04-15T10:00:00')

function makeSession(id, title, updatedAt) {
  return {
    id,
    title,
    updated_at: updatedAt.toISOString(),
    user_id: 1,
    created_at: updatedAt.toISOString(),
    is_active: true
  }
}

const allSessions = [
  makeSession('s1', 'Apa itu SPBE?', NOW),
  makeSession('s2', 'Audit BSSN 2024', YESTERDAY),
  makeSession('s3', 'Perpres 95 Pasal 5', THREE_DAYS_AGO),
  makeSession('s4', 'SE BSSN No. 4', TEN_DAYS_AGO),
]

function mountSidebar(sessions = allSessions, extra = {}) {
  return mount(ChatSidebar, {
    props: {
      sessions,
      currentSessionId: null,
      collapsed: false,
      models: [],
      selectedModel: '',
      ...extra
    },
    global: { stubs: { RouterLink: RouterLinkStub } }
  })
}

describe('ChatSidebar — date grouping', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows HARI INI group for today session', () => {
    const wrapper = mountSidebar()
    const labels = wrapper.findAll('.session-group-label').map(el => el.text())
    expect(labels).toContain('HARI INI')
  })

  it('shows KEMARIN group for yesterday session', () => {
    const wrapper = mountSidebar()
    const labels = wrapper.findAll('.session-group-label').map(el => el.text())
    expect(labels).toContain('KEMARIN')
  })

  it('shows 7 HARI LALU group for 3-day-old session', () => {
    const wrapper = mountSidebar()
    const labels = wrapper.findAll('.session-group-label').map(el => el.text())
    expect(labels).toContain('7 HARI LALU')
  })

  it('shows LEBIH LAMA group for 10-day-old session', () => {
    const wrapper = mountSidebar()
    const labels = wrapper.findAll('.session-group-label').map(el => el.text())
    expect(labels).toContain('LEBIH LAMA')
  })

  it('hides group label when no sessions fall in that bucket', () => {
    const wrapper = mountSidebar([makeSession('s1', 'Apa itu SPBE?', NOW)])
    const labels = wrapper.findAll('.session-group-label').map(el => el.text())
    expect(labels).toContain('HARI INI')
    expect(labels).not.toContain('KEMARIN')
    expect(labels).not.toContain('7 HARI LALU')
    expect(labels).not.toContain('LEBIH LAMA')
  })
})

describe('ChatSidebar — inline rename', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows rename input when pencil button is clicked', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.session-rename-btn').trigger('click')
    expect(wrapper.find('.session-rename-input').exists()).toBe(true)
  })

  it('emits rename-session with {id, title} when Enter pressed', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.session-rename-btn').trigger('click')
    const input = wrapper.find('.session-rename-input')
    await input.setValue('Judul Baru')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('rename-session')).toBeTruthy()
    expect(wrapper.emitted('rename-session')[0][0]).toEqual({ id: 's1', title: 'Judul Baru' })
  })

  it('hides rename input and does not emit when Escape pressed', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.session-rename-btn').trigger('click')
    await wrapper.find('.session-rename-input').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('.session-rename-input').exists()).toBe(false)
    expect(wrapper.emitted('rename-session')).toBeFalsy()
    expect(wrapper.find('.session-title').text()).toBe('Apa itu SPBE?')
  })

  it('does not emit rename-session when title is blank after trim', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.session-rename-btn').trigger('click')
    await wrapper.find('.session-rename-input').setValue('   ')
    await wrapper.find('.session-rename-input').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('rename-session')).toBeFalsy()
  })

  it('does not emit rename-session when title is unchanged', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.session-rename-btn').trigger('click')
    // title field pre-filled with original — do not change it
    await wrapper.find('.session-rename-input').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('rename-session')).toBeFalsy()
  })

  it('emits rename-session on blur with a changed title', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.session-rename-btn').trigger('click')
    const input = wrapper.find('.session-rename-input')
    await input.setValue('Nama Baru via Blur')
    await input.trigger('blur')
    expect(wrapper.emitted('rename-session')?.[0]?.[0]).toEqual({ id: 's1', title: 'Nama Baru via Blur' })
  })

  it('does not emit load-session when clicking an editing session item', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.session-rename-btn').trigger('click')
    await wrapper.find('.session-item').trigger('click')
    expect(wrapper.emitted('load-session')).toBeFalsy()
  })
})
