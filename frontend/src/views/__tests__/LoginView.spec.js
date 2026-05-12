import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import LoginView from '../LoginView.vue'
import * as authService from '@/services/auth'
import { createRouter, createWebHistory } from 'vue-router'

// Mock the router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: { template: '<div>Login</div>' } },
    { path: '/', component: { template: '<div>Home</div>' } }
  ]
})

// Mock auth service
vi.mock('@/services/auth', () => ({
  login: vi.fn(),
  isAuthenticated: vi.fn(() => false)
}))

describe('LoginView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    router.push('/login')
  })

  it('renders login form properly', () => {
    const wrapper = mount(LoginView, {
      global: {
        plugins: [router]
      }
    })
    
    expect(wrapper.find('.login-view').exists()).toBe(true)
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('shows error when login fails', async () => {
    authService.login.mockRejectedValueOnce(new Error('Invalid credentials'))
    
    const wrapper = mount(LoginView, {
      global: {
        plugins: [router]
      }
    })
    
    await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
    await wrapper.find('input[type="password"]').setValue('wrong')
    await wrapper.find('form').trigger('submit.prevent')
    
    // wait for promises
    await new Promise(r => setTimeout(r, 0))
    
    expect(authService.login).toHaveBeenCalledWith('admin@bssn.go.id', 'wrong')
    expect(wrapper.find('.error-msg').exists()).toBe(true)
  })

  it('redirects to home on successful login', async () => {
    authService.login.mockResolvedValueOnce({ access_token: 'fake-token' })
    const pushSpy = vi.spyOn(router, 'push')
    
    const wrapper = mount(LoginView, {
      global: {
        plugins: [router]
      }
    })
    
    await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
    await wrapper.find('input[type="password"]').setValue('password123')
    await wrapper.find('form').trigger('submit.prevent')
    
    await new Promise(r => setTimeout(r, 0))
    
    expect(authService.login).toHaveBeenCalledWith('admin@bssn.go.id', 'password123')
    expect(pushSpy).toHaveBeenCalledWith('/')
  })
})
