import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatView from '../ChatView.vue'

describe('ChatView.vue', () => {
  it('renders without compiler errors', () => {
    // This will fail to compile if there are missing end tags
    expect(ChatView).toBeTruthy()
  })
})
