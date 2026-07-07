import { describe, expect, it, vi } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import AppHeader from '../AppHeader.vue'

vi.mock('@/services/auth', () => ({
  formatRoleLabel: (role) => role,
  getCurrentUserProfile: vi.fn(() => ({
    username: 'evaluator@bssn.go.id',
    display_name: 'Evaluator SPBE',
    roles: ['staff']
  })),
  isAdminUser: vi.fn(() => false)
}))

describe('AppHeader role-based navigation', () => {
  it('hides document management navigation for non-admin users', () => {
    const wrapper = mount(AppHeader, {
      global: { stubs: { RouterLink: RouterLinkStub } }
    })

    const documentLinks = wrapper.findAllComponents(RouterLinkStub)
      .filter((link) => link.props('to') === '/documents')

    expect(documentLinks).toHaveLength(0)
  })
})
