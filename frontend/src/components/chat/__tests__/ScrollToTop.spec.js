import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ScrollToTop from '../ScrollToTop.vue'

describe('ScrollToTop', () => {
  it('renders a button', () => {
    const wrapper = mount(ScrollToTop)
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('emits click when button is clicked', async () => {
    const wrapper = mount(ScrollToTop)
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })
})
