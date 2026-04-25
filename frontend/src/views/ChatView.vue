<template>
  <div class="chat-layout">
    <ChatSidebar
      :collapsed="sidebarCollapsed"
      :sessions="sessions"
      :current-session-id="currentSessionId"
      :models="models"
      v-model:selected-model="selectedModel"
      @toggle-sidebar="toggleSidebar"
      @new-chat="createNewChat"
      @load-session="loadSession"
      @delete-session="deleteSession"
      @rename-session="handleRenameSession"
      @model-change="onModelChange"
    />

    <div class="chat-main">
      <!-- Topbar -->
      <nav class="topbar">
        <div class="topbar-brand">
          <div class="topbar-logo">B</div>
          <div>
            <div class="topbar-title">SPBE Asisten</div>
            <div class="topbar-subtitle">Badan Siber dan Sandi Negara</div>
          </div>
        </div>
        <div class="topbar-nav">
          <router-link to="/home" class="topbar-nav-link">Beranda</router-link>
          <router-link to="/" class="topbar-nav-link active">Chat</router-link>
          <router-link to="/documents" class="topbar-nav-link">Dokumen</router-link>
          <div class="status-dot" :class="connectionStatus">
            {{ connectionStatus === 'connected' ? 'Terhubung' : connectionStatus === 'disconnected' ? 'Terputus' : 'Menghubungkan...' }}
          </div>
        </div>
      </nav>

      <!-- Messages -->
      <div class="messages-area" ref="messagesContainer" @scroll="onMessagesScroll">
        <!-- Welcome screen -->
        <div v-if="messages.length === 0" class="welcome-screen">
          <div class="welcome-logo">B</div>
          <h2 class="welcome-title">SPBE Asisten</h2>
          <p class="welcome-desc">Tanyakan tentang peraturan SPBE, audit keamanan BSSN, dan dokumen terkait.</p>
          <div class="suggestions">
            <button
              v-for="q in sampleQuestions"
              :key="q"
              @click="sendSampleQuestion(q)"
              class="suggestion-btn"
            >{{ q }}</button>
          </div>
        </div>

        <MessageBubble
          v-for="(msg, idx) in messages"
          :key="idx"
          :message="msg"
        />
      </div>

      <Transition name="fade">
        <ScrollToTop v-if="showScrollTop" @click="scrollToTop" />
      </Transition>

      <!-- Input -->
      <ChatInput
        ref="chatInputRef"
        v-model="inputMessage"
        :is-loading="isLoading"
        :use-rag="useRag"
        @update:use-rag="useRag = $event"
        @send="sendMessage"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import ChatSidebar from '@/components/chat/ChatSidebar.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import ScrollToTop from '@/components/chat/ScrollToTop.vue'
import {
  checkHealth as checkApiHealth,
  deleteSession as deleteSessionService,
  getDefaultModel,
  getModels,
  getSession,
  getSessionHistory,
  getSessions,
  setDefaultModel,
  streamChat,
  updateSessionTitle
} from '@/services/chatService'

// State
const sidebarCollapsed = ref(false)
const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const isLoading = ref(false)
const connectionStatus = ref('connecting')
const models = ref([])
const selectedModel = ref('qwen2.5:3b')
const useRag = ref(true)
const showScrollTop = ref(false)

// Refs
const messagesContainer = ref(null)
const chatInputRef = ref(null)

// Sample questions
const sampleQuestions = [
  'Apa itu SPBE?',
  'Apa saja domain dalam SPBE?',
  'Bagaimana prosedur audit keamanan?',
  'Jelaskan tentang Perpres 95 Tahun 2018'
]

const DEFAULT_SESSION_TITLE = 'New Conversation'
const MAX_SESSION_TITLE_WORDS = 8
const MAX_SESSION_TITLE_LENGTH = 64
let hasBackfilledDefaultTitles = false

// Initialize
onMounted(async () => {
  await Promise.all([
    fetchModels(),
    fetchSessions(),
    checkServerHealth()
  ])
})

async function fetchModels() {
  try {
    models.value = await getModels()
    const modelData = await getDefaultModel()
    selectedModel.value = modelData.model
  } catch (error) {
    console.error('Failed to fetch models:', error)
  }
}

async function fetchSessions() {
  try {
    const fetchedSessions = await getSessions()
    sessions.value = fetchedSessions

    if (!hasBackfilledDefaultTitles) {
      hasBackfilledDefaultTitles = true
      void backfillDefaultSessionTitles(fetchedSessions)
    }
  } catch (error) {
    console.error('Failed to fetch sessions:', error)
  }
}

function isPlaceholderSessionTitle(title) {
  return !title || title.trim().toLowerCase() === DEFAULT_SESSION_TITLE.toLowerCase()
}

function generateSessionTitleFromMessage(message) {
  const cleaned = (message || '').replace(/\s+/g, ' ').trim()
  if (!cleaned) return DEFAULT_SESSION_TITLE

  const mainSentence = cleaned.split(/[?.!]/).find((part) => part.trim())?.trim() || cleaned
  const limitedWords = mainSentence.split(' ').slice(0, MAX_SESSION_TITLE_WORDS).join(' ')

  if (limitedWords.length > MAX_SESSION_TITLE_LENGTH) {
    return `${limitedWords.slice(0, MAX_SESSION_TITLE_LENGTH - 3).trimEnd()}...`
  }

  return limitedWords || DEFAULT_SESSION_TITLE
}

async function backfillDefaultSessionTitles(sessionList) {
  const sessionsToBackfill = sessionList.filter((session) => isPlaceholderSessionTitle(session.title))
  if (sessionsToBackfill.length === 0) return

  const updates = await Promise.all(
    sessionsToBackfill.map(async (session) => {
      try {
        const history = await getSessionHistory(session.id)
        const firstUserMessage = history.find((message) => message.role === 'user' && message.content?.trim())
        if (!firstUserMessage) return null

        const generatedTitle = generateSessionTitleFromMessage(firstUserMessage.content)
        if (isPlaceholderSessionTitle(generatedTitle)) return null

        await updateSessionTitle(session.id, generatedTitle)
        return { id: session.id, title: generatedTitle }
      } catch (error) {
        console.error(`Failed to backfill title for session ${session.id}:`, error)
        return null
      }
    })
  )

  const titleBySessionId = new Map(
    updates.filter(Boolean).map((session) => [session.id, session.title])
  )
  if (titleBySessionId.size === 0) return

  sessions.value = sessions.value.map((session) => (
    titleBySessionId.has(session.id)
      ? { ...session, title: titleBySessionId.get(session.id) }
      : session
  ))
}

async function checkServerHealth() {
  try {
    await checkApiHealth()
    connectionStatus.value = 'connected'
  } catch (error) {
    connectionStatus.value = 'disconnected'
    setTimeout(checkServerHealth, 5000)
  }
}

async function createNewChat() {
  currentSessionId.value = null
  messages.value = []
  await nextTick()
  chatInputRef.value?.focusInput()
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

async function loadSession(sessionId) {
  try {
    const [session, history] = await Promise.all([
      getSession(sessionId),
      getSessionHistory(sessionId)
    ])
    currentSessionId.value = session.id
    if (session.model) selectedModel.value = session.model
    messages.value = history.map((message) => {
      let timestamp = null
      if (message.timestamp) {
        const d = new Date(message.timestamp)
        if (!isNaN(d.getTime())) {
          timestamp = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
        }
      }
      return {
        role: message.role,
        content: message.content,
        sources: message.sources || [],
        timestamp
      }
    })
    await nextTick()
    scrollToBottom()
  } catch (error) {
    console.error('Failed to load session:', error)
  }
}

async function deleteSession(sessionId) {
  if (!confirm('Hapus percakapan ini?')) return
  try {
    await deleteSessionService(sessionId)
    sessions.value = sessions.value.filter((s) => s.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
      messages.value = []
    }
  } catch (error) {
    console.error('Failed to delete session:', error)
  }
}

async function handleRenameSession({ id, title }) {
  try {
    await updateSessionTitle(id, title)
    const session = sessions.value.find(s => s.id === id)
    if (session) session.title = title
  } catch (err) {
    console.error('Failed to rename session', err)
  }
}

async function onModelChange() {
  try {
    await setDefaultModel(selectedModel.value)
  } catch (error) {
    console.error('Failed to set default model:', error)
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || isLoading.value) return

  const userMessage = inputMessage.value.trim()
  const isStartingNewSession = !currentSessionId.value
  const generatedTitle = generateSessionTitleFromMessage(userMessage)
  inputMessage.value = ''
  chatInputRef.value?.resetInputHeight()

  const nowUser = new Date()
  const userHhmm = `${String(nowUser.getHours()).padStart(2, '0')}:${String(nowUser.getMinutes()).padStart(2, '0')}`
  messages.value.push({ role: 'user', content: userMessage, timestamp: userHhmm })

  const loadingIdx = messages.value.length
  messages.value.push({ role: 'assistant', loading: true, loadingText: 'Mencari dokumen relevan...' })

  await nextTick()
  scrollToBottom()

  isLoading.value = true

  let lastScroll = 0
  const throttledScroll = () => {
    const now = Date.now()
    if (now - lastScroll > 150) { lastScroll = now; scrollToBottom() }
  }

  try {
    let streamedContent = ''
    let pendingValidation = null

    await streamChat(
      {
        message: userMessage,
        session_id: currentSessionId.value,
        model: selectedModel.value,
        use_rag: useRag.value,
        top_k: 5,
        max_tokens: 2048
      },
      {
        onRetrieval: async (data) => {
          messages.value[loadingIdx] = {
            role: 'assistant',
            loading: true,
            loadingText: `Ditemukan ${data.count} dokumen, menyusun jawaban...`
          }
        },
        onToken: async (data) => {
          streamedContent += data.t
          messages.value[loadingIdx] = { role: 'assistant', content: streamedContent, streaming: true }
          throttledScroll()
        },
        onComplete: async (data) => {
          const nowAi = new Date()
          const aiHhmm = `${String(nowAi.getHours()).padStart(2, '0')}:${String(nowAi.getMinutes()).padStart(2, '0')}`
          messages.value[loadingIdx] = {
            role: 'assistant',
            content: data.answer,
            sources: data.sources,
            timing: data.timing,
            validation: data.validation || pendingValidation,
            timestamp: aiHhmm
          }
          pendingValidation = null
          if (data.session_id) {
            currentSessionId.value = data.session_id

            if (isStartingNewSession && !isPlaceholderSessionTitle(generatedTitle)) {
              try {
                await updateSessionTitle(data.session_id, generatedTitle)
              } catch (error) {
                console.error('Failed to set session title:', error)
              }
            }

            await fetchSessions()
          }
        },
        onSession: async (data) => {
          if (data.session_id && data.title) {
            const existing = sessions.value.find((s) => s.id === data.session_id)
            if (existing) existing.title = data.title
            else await fetchSessions()
          }
        },
        onValidation: async (data) => { pendingValidation = data },
        onError: async (data) => {
          messages.value[loadingIdx] = {
            role: 'assistant',
            content: `Error: ${data.error}. Pastikan server backend berjalan.`
          }
        }
      }
    )
  } catch (error) {
    console.error('Chat error:', error)
    messages.value[loadingIdx] = {
      role: 'assistant',
      content: `Error: ${error.message}. Pastikan server backend berjalan.`
    }
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function sendSampleQuestion(question) {
  inputMessage.value = question
  sendMessage()
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function onMessagesScroll() {
  showScrollTop.value = (messagesContainer.value?.scrollTop ?? 0) > 300
}

function scrollToTop() {
  messagesContainer.value?.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--color-cream);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* Messages area */
.messages-area {
  flex: 1;
  overflow-y: auto;
  background: var(--color-cream);
  padding: 24px 0 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}

/* Welcome screen */
.welcome-screen {
  max-width: 520px;
  margin: 60px auto 0;
  padding: 0 28px;
  text-align: center;
}

.welcome-logo {
  width: 52px;
  height: 52px;
  background: var(--color-gold);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 22px;
  color: var(--color-navy);
  margin: 0 auto 16px;
}

.welcome-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--color-navy);
  margin: 0 0 8px;
}

.welcome-desc {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--color-text-muted);
  line-height: 1.6;
  margin: 0 0 28px;
  font-style: italic;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-btn {
  background: white;
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-gold);
  padding: 10px 14px;
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--color-navy);
  text-align: left;
  cursor: pointer;
  border-radius: 0 3px 3px 0;
  transition: border-left-color 0.15s, background 0.15s, box-shadow 0.15s;
}

.suggestion-btn:hover {
  border-left-color: var(--color-navy);
  background: #f5f8fd;
  box-shadow: 0 2px 8px rgba(26, 58, 107, 0.06);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
