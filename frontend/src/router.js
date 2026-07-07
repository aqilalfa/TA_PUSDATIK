import { createRouter, createWebHistory } from 'vue-router'
import ChatView from './views/ChatView.vue'
import HomeView from './views/HomeView.vue'
import DocumentsView from './views/DocumentsView.vue'
import DocumentDetailView from './views/DocumentDetailView.vue'
import LoginView from './views/LoginView.vue'
import LogoutView from './views/LogoutView.vue'
import { isAdminUser, isAuthenticated } from '@/services/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresAuth: false }
    },
    {
      path: '/logout',
      name: 'logout',
      component: LogoutView,
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      name: 'home',
      component: HomeView,
      alias: '/home',
      meta: { requiresAuth: true }
    },
    {
      path: '/chat',
      name: 'chat',
      component: ChatView,
      meta: { requiresAuth: true }
    },
    {
      path: '/documents',
      name: 'documents',
      component: DocumentsView,
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/documents/:doc_id',
      name: 'document-detail',
      component: DocumentDetailView,
      meta: { requiresAuth: true, requiresAdmin: true }
    }
  ]
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth !== false)
  const isAuth = isAuthenticated()

  if (requiresAuth && !isAuth) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.name === 'login' && isAuth) {
    next({ name: 'home' })
  } else if (to.matched.some(record => record.meta.requiresAdmin) && !isAdminUser()) {
    next({ name: 'chat' })
  } else {
    next()
  }
})

export default router
