import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { useRouter, useRoute } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import * as authService from '@/services/auth'

// Mock router and route
vi.mock('vue-router', () => ({
  useRouter: vi.fn(),
  useRoute: vi.fn()
}))

// Mock auth service
vi.mock('@/services/auth')

describe('LoginView.vue - TDD Test Suite', () => {
  let wrapper
  let mockRouter
  let mockRoute

  beforeEach(() => {
    // Setup router mock
    mockRouter = {
      push: vi.fn()
    }

    // Setup route mock with default values
    mockRoute = {
      query: {}
    }

    // Mock implementations
    vi.mocked(useRouter).mockReturnValue(mockRouter)
    vi.mocked(useRoute).mockReturnValue(mockRoute)

    // Mount component
    wrapper = mount(LoginView, {
      global: {
        stubs: {
          teleport: true
        }
      }
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  // ============ RENDERING TESTS ============

  describe('Rendering', () => {
    it('should render topbar with BSSN branding', () => {
      const topbar = wrapper.find('.topbar')
      expect(topbar.exists()).toBe(true)
      expect(topbar.text()).toContain('SPBE Asisten')
      expect(topbar.text()).toContain('Badan Siber dan Sandi Negara')
    })

    it('should render topbar logo "B"', () => {
      const logo = wrapper.find('.topbar-logo')
      expect(logo.exists()).toBe(true)
      expect(logo.text()).toBe('B')
    })

    it('should render login container with proper styling', () => {
      const container = wrapper.find('.login-container')
      expect(container.exists()).toBe(true)
    })

    it('should render login card centered', () => {
      const card = wrapper.find('.login-card')
      expect(card.exists()).toBe(true)
    })

    it('should render header with lock icon', () => {
      const icon = wrapper.find('.login-icon')
      expect(icon.exists()).toBe(true)
      expect(icon.text()).toBe('🔒')
    })

    it('should render correct header title', () => {
      const title = wrapper.find('.login-title')
      expect(title.exists()).toBe(true)
      expect(title.text()).toBe('Autentikasi Sistem')
    })

    it('should render correct subtitle', () => {
      const subtitle = wrapper.find('.login-subtitle')
      expect(subtitle.exists()).toBe(true)
      expect(subtitle.text()).toContain('Masuk untuk mengakses layanan')
    })

    it('should render email input field', () => {
      const emailInput = wrapper.find('input[type="email"]')
      expect(emailInput.exists()).toBe(true)
    })

    it('should render password input field', () => {
      const passwordInput = wrapper.find('input[type="password"]')
      expect(passwordInput.exists()).toBe(true)
    })

    it('should render submit button with correct text', () => {
      const button = wrapper.find('.login-button')
      expect(button.exists()).toBe(true)
      expect(button.text()).toContain('MASUK')
    })

    it('should render footer text', () => {
      const footer = wrapper.find('.login-footer')
      expect(footer.exists()).toBe(true)
      expect(footer.text()).toContain('BSSN')
    })

    it('should have form with submit prevention', () => {
      const form = wrapper.find('.login-form')
      expect(form.exists()).toBe(true)
    })
  })

  // ============ INPUT BINDING TESTS ============

  describe('Form Input Binding', () => {
    it('should bind email input to reactive state', async () => {
      const emailInput = wrapper.find('input[type="email"]')
      await emailInput.setValue('test@example.com')
      expect(wrapper.vm.email).toBe('test@example.com')
    })

    it('should bind password input to reactive state', async () => {
      const passwordInput = wrapper.find('input[type="password"]')
      await passwordInput.setValue('password123')
      expect(wrapper.vm.password).toBe('password123')
    })

    it('should clear email when input is reset', async () => {
      const emailInput = wrapper.find('input[type="email"]')
      await emailInput.setValue('test@example.com')
      await emailInput.setValue('')
      expect(wrapper.vm.email).toBe('')
    })

    it('should disable inputs during loading', async () => {
      wrapper.vm.loading = true
      await wrapper.vm.$nextTick()
      const emailInput = wrapper.find('input[type="email"]')
      const passwordInput = wrapper.find('input[type="password"]')
      expect(emailInput.attributes('disabled')).toBeDefined()
      expect(passwordInput.attributes('disabled')).toBeDefined()
    })
  })

  // ============ FORM VALIDATION TESTS ============

  describe('Client-Side Validation', () => {
    it('should require email field', async () => {
      const emailInput = wrapper.find('input[type="email"]')
      expect(emailInput.attributes('required')).toBe('')
    })

    it('should require password field', async () => {
      const passwordInput = wrapper.find('input[type="password"]')
      expect(passwordInput.attributes('required')).toBe('')
    })

    it('should have email type validation', async () => {
      const emailInput = wrapper.find('input[type="email"]')
      expect(emailInput.attributes('type')).toBe('email')
    })

    it('should show placeholder for email', () => {
      const emailInput = wrapper.find('input[type="email"]')
      expect(emailInput.attributes('placeholder')).toBe('admin@bssn.go.id')
    })

    it('should show placeholder for password', () => {
      const passwordInput = wrapper.find('input[type="password"]')
      expect(passwordInput.attributes('placeholder')).toBe('••••••••')
    })
  })

  // ============ SUBMISSION TESTS ============

  describe('Form Submission', () => {
    it('should call auth.login with email and password on submit', async () => {
      vi.mocked(authService.login).mockResolvedValueOnce({ access_token: 'token123' })

      const emailInput = wrapper.find('input[type="email"]')
      const passwordInput = wrapper.find('input[type="password"]')
      const form = wrapper.find('.login-form')

      await emailInput.setValue('admin@bssn.go.id')
      await passwordInput.setValue('password123')
      await form.trigger('submit')
      await flushPromises()

      expect(authService.login).toHaveBeenCalledWith('admin@bssn.go.id', 'password123')
    })

    it('should set loading state during submission', async () => {
      let resolveLogin
      vi.mocked(authService.login).mockImplementation(() =>
        new Promise(resolve => { resolveLogin = resolve })
      )

      const form = wrapper.find('.login-form')
      await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
      await wrapper.find('input[type="password"]').setValue('password123')

      form.trigger('submit')
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.loading).toBe(true)

      resolveLogin({ access_token: 'token123' })
      await flushPromises()
      expect(wrapper.vm.loading).toBe(false)
    })

    it('should show spinner button during loading', async () => {
      wrapper.vm.loading = true
      await wrapper.vm.$nextTick()
      const spinner = wrapper.find('.button-spinner')
      expect(spinner.exists()).toBe(true)
    })

    it('should show button text when not loading', async () => {
      wrapper.vm.loading = false
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.login-button').text()).toContain('MASUK')
    })
  })

  // ============ ERROR HANDLING TESTS ============

  describe('Error Handling', () => {
    it('should display error message on 401 (invalid credentials)', async () => {
      vi.mocked(authService.login).mockRejectedValueOnce({
        response: { status: 401 }
      })

      const form = wrapper.find('.login-form')
      await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
      await wrapper.find('input[type="password"]').setValue('wrongpassword')
      await form.trigger('submit')
      await flushPromises()

      expect(wrapper.vm.errorMsg).toBe('Email atau password salah.')
    })

    it('should display generic error on non-401 errors', async () => {
      vi.mocked(authService.login).mockRejectedValueOnce({
        response: { status: 500 }
      })

      const form = wrapper.find('.login-form')
      await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
      await wrapper.find('input[type="password"]').setValue('password123')
      await form.trigger('submit')
      await flushPromises()

      expect(wrapper.vm.errorMsg).toBe('Terjadi kesalahan pada sistem. Silakan coba lagi.')
    })

    it('should display error message in template', async () => {
      wrapper.vm.errorMsg = 'Email atau password salah.'
      await wrapper.vm.$nextTick()

      const errorMsg = wrapper.find('.error-msg')
      expect(errorMsg.exists()).toBe(true)
      expect(errorMsg.text()).toContain('Email atau password salah.')
    })

    it('should hide error message initially', () => {
      const errorMsg = wrapper.find('.error-msg')
      expect(errorMsg.exists()).toBe(false)
    })

    it('should clear error message on new submission attempt', async () => {
      wrapper.vm.errorMsg = 'Previous error'
      vi.mocked(authService.login).mockResolvedValueOnce({ access_token: 'token123' })

      const form = wrapper.find('.login-form')
      await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
      await wrapper.find('input[type="password"]').setValue('password123')

      expect(wrapper.vm.errorMsg).toBe('Previous error')
      await form.trigger('submit')
      await flushPromises()
      expect(wrapper.vm.errorMsg).toBe('')
    })
  })

  // ============ SUCCESSFUL LOGIN TESTS ============

  describe('Successful Login', () => {
    it('should redirect to home on successful login', async () => {
      vi.mocked(authService.login).mockResolvedValueOnce({ access_token: 'token123' })

      const form = wrapper.find('.login-form')
      await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
      await wrapper.find('input[type="password"]').setValue('password123')
      await form.trigger('submit')
      await flushPromises()

      expect(mockRouter.push).toHaveBeenCalledWith('/')
    })

    it('should redirect to query.redirect if provided', async () => {
      mockRoute.query.redirect = '/documents'
      vi.mocked(useRoute).mockReturnValue(mockRoute)

      wrapper = mount(LoginView, {
        global: {
          stubs: {
            teleport: true
          }
        }
      })

      vi.mocked(authService.login).mockResolvedValueOnce({ access_token: 'token123' })

      const form = wrapper.find('.login-form')
      await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
      await wrapper.find('input[type="password"]').setValue('password123')
      await form.trigger('submit')
      await flushPromises()

      expect(mockRouter.push).toHaveBeenCalledWith('/documents')
    })

    it('should disable inputs after successful login', async () => {
      vi.mocked(authService.login).mockResolvedValueOnce({ access_token: 'token123' })

      const form = wrapper.find('.login-form')
      await wrapper.find('input[type="email"]').setValue('admin@bssn.go.id')
      await wrapper.find('input[type="password"]').setValue('password123')
      await form.trigger('submit')
      await flushPromises()

      expect(wrapper.vm.loading).toBe(false)
    })
  })

  // ============ BUTTON STATE TESTS ============

  describe('Button States', () => {
    it('should disable button when loading', async () => {
      wrapper.vm.loading = true
      await wrapper.vm.$nextTick()

      const button = wrapper.find('.login-button')
      expect(button.attributes('disabled')).toBeDefined()
    })

    it('should enable button when not loading', async () => {
      wrapper.vm.loading = false
      await wrapper.vm.$nextTick()

      const button = wrapper.find('.login-button')
      expect(button.attributes('disabled')).toBeUndefined()
    })
  })

  // ============ PLACEHOLDER & LABELS TESTS ============

  describe('Form Labels & Accessibility', () => {
    it('should have label for email input', () => {
      const label = wrapper.find('label[for="email"]')
      expect(label.exists()).toBe(true)
      expect(label.text()).toBe('Alamat Email')
    })

    it('should have label for password input', () => {
      const label = wrapper.find('label[for="password"]')
      expect(label.exists()).toBe(true)
      expect(label.text()).toBe('Kata Sandi')
    })

    it('should have correct input IDs matching labels', () => {
      const emailInput = wrapper.find('input[type="email"]')
      const passwordInput = wrapper.find('input[type="password"]')

      expect(emailInput.attributes('id')).toBe('email')
      expect(passwordInput.attributes('id')).toBe('password')
    })
  })

  // ============ RESPONSIVE DESIGN TESTS ============

  describe('Responsive Design', () => {
    it('should have login-view container', () => {
      const view = wrapper.find('.login-view')
      expect(view.exists()).toBe(true)
      expect(view.classes()).toContain('login-view')
    })

    it('should render card within container', () => {
      const card = wrapper.find('.login-card')
      expect(card.exists()).toBe(true)
    })

    it('should have proper CSS classes for styling', () => {
      const form = wrapper.find('.login-form')
      const container = wrapper.find('.login-container')

      expect(form.exists()).toBe(true)
      expect(container.exists()).toBe(true)
    })
  })
})
