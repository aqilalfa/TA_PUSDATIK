import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '../MessageBubble.vue'

const assistantMsg = (overrides = {}) => ({
  role: 'assistant',
  content: 'Test answer',
  ...overrides
})

describe('MessageBubble — timestamp', () => {
  it('renders timestamp in header when provided', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: assistantMsg({ timestamp: '09:45' }) }
    })
    expect(wrapper.find('.msg-ai-timestamp').exists()).toBe(true)
    expect(wrapper.find('.msg-ai-timestamp').text()).toBe('09:45')
  })

  it('omits timestamp element when timestamp is null', () => {
    const wrapper = mount(MessageBubble, {
      props: { message: assistantMsg({ timestamp: null }) }
    })
    expect(wrapper.find('.msg-ai-timestamp').exists()).toBe(false)
  })
})

describe('MessageBubble — warning dismissal', () => {
  it('shows validation warnings by default', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: assistantMsg({ validation: { warnings: ['Warning A'] } })
      }
    })
    expect(wrapper.find('.validation-warnings').exists()).toBe(true)
  })

  it('hides validation warnings after dismiss button clicked', async () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: assistantMsg({ validation: { warnings: ['Warning A'] } })
      }
    })
    await wrapper.find('.dismiss-btn').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.validation-warnings').exists()).toBe(false)
  })
})
