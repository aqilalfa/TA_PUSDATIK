import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageActions from '../MessageActions.vue'

describe('MessageActions', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
      writable: true
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('copy button calls clipboard API with content', async () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'Hello world', hasWarning: false }
    })
    await wrapper.find('.copy-btn').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Hello world')
  })

  it('shows Tersalin after successful copy and resets after 2s', async () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: false }
    })
    await wrapper.find('.copy-btn').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Tersalin')
    vi.advanceTimersByTime(2000)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Salin')
  })

  it('shows Gagal if clipboard throws and resets after 2s', async () => {
    navigator.clipboard.writeText = vi.fn().mockRejectedValue(new Error('denied'))
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: false }
    })
    await wrapper.find('.copy-btn').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Gagal')
    vi.advanceTimersByTime(2000)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.copy-btn').text()).toContain('Salin')
  })

  it('emits dismiss-warning when dismiss button clicked', async () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: true }
    })
    await wrapper.find('.dismiss-btn').trigger('click')
    expect(wrapper.emitted('dismiss-warning')).toBeTruthy()
  })

  it('dismiss button absent when hasWarning is false', () => {
    const wrapper = mount(MessageActions, {
      props: { content: 'test', hasWarning: false }
    })
    expect(wrapper.find('.dismiss-btn').exists()).toBe(false)
  })
})
