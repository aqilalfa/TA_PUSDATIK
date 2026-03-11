import { createRouter, createWebHistory } from 'vue-router'
import ChatView from './views/ChatView.vue'
import HomeView from './views/HomeView.vue'
import DocumentsView from './views/DocumentsView.vue'
import DocumentDetailView from './views/DocumentDetailView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: ChatView
    },
    {
      path: '/home',
      name: 'home',
      component: HomeView
    },
    {
      path: '/documents',
      name: 'documents',
      component: DocumentsView
    },
    {
      path: '/documents/:doc_id',
      name: 'document-detail',
      component: DocumentDetailView
    }
  ]
})

export default router
