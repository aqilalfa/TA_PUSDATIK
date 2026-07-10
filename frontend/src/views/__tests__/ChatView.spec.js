import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatView from '../ChatView.vue'

vi.mock('@/services/chatService', () => ({
  checkHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  deleteSession: vi.fn().mockResolvedValue({}),
  getSession: vi.fn().mockResolvedValue({ id: 'session-1' }),
  getSessionHistory: vi.fn().mockResolvedValue([]),
  getSessions: vi.fn().mockResolvedValue([]),
  streamChat: vi.fn(),
  updateSessionTitle: vi.fn().mockResolvedValue({})
}))

describe('ChatView.vue', () => {
  it('renders without compiler errors', () => {
    // This will fail to compile if there are missing end tags
    expect(ChatView).toBeTruthy()
  })

  it('opens inline edit mode when the user message edit button is clicked', async () => {
    const wrapper = mount(ChatView, {
      global: {
        stubs: {
          ChatSidebar: true,
          AppHeader: true,
          ChatInput: true,
          ScrollToTop: true
        }
      }
    })

    wrapper.vm.messages = [
      { role: 'user', content: 'Pertanyaan awal', timestamp: '04:23' },
      { role: 'assistant', content: 'Jawaban awal', timestamp: '04:24' }
    ]
    await wrapper.vm.$nextTick()

    await wrapper.find('.user-edit-btn').trigger('click')

    const editor = wrapper.find('.inline-edit-textarea')
    expect(editor.exists()).toBe(true)
    expect(editor.element.value).toBe('Pertanyaan awal')
  })
})
