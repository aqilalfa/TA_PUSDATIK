<template>
  <div class="chat-layout">
    <button
      type="button"
      class="mobile-sidebar-toggle"
      :aria-expanded="mobileSidebarOpen"
      aria-controls="chat-sidebar"
      @click="openMobileSidebar"
    >
      <span class="mobile-sidebar-toggle-icon" aria-hidden="true"></span>
      <span>Riwayat</span>
    </button>

    <div
      v-if="mobileSidebarOpen"
      class="mobile-sidebar-backdrop"
      aria-hidden="true"
      @click="closeMobileSidebar"
    ></div>

    <ChatSidebar
      id="chat-sidebar"
      :class="{ 'mobile-open': mobileSidebarOpen }"
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
      <AppHeader
        active="chat"
        :status="connectionStatus"
        :show-clear-chat="Boolean(messages.length || currentSessionId)"
        @clear-chat="clearCurrentChat"
      />

      <div class="chat-workspace">
        <div class="consultation-column">
          <div class="quick-action-strip" aria-label="Aksi cepat konsultasi">
            <button v-for="action in quickActions" :key="action" type="button" @click="applyQuickAction(action)">
              {{ action }}
            </button>
          </div>

          <!-- Messages -->
          <div class="messages-area" ref="messagesContainer" @scroll="onMessagesScroll">
            <!-- Welcome screen -->
            <div v-if="messages.length === 0" class="welcome-screen">
              <div class="welcome-logo">AH</div>
              <h2 class="welcome-title">Asisten Hukum SPBE</h2>
              <p class="welcome-desc">Ajukan konsultasi regulasi, kebijakan, tata kelola digital, audit SPBE, dan dokumen hukum pemerintahan.</p>
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
              :can-regenerate="canRegenerateMessage(idx)"
              :can-edit-retry="canEditRetryMessage(idx)"
              :is-editing="editingMessageIndex === idx"
              :edit-content="editingMessageContent"
              @update:edit-content="editingMessageContent = $event"
              @cancel-edit="editingMessageIndex = null"
              @regenerate="regenerateFrom(idx)"
              @edit-retry="editRetryFrom(idx)"
              @submit-edit="(newContent) => submitEditedMessage(idx, newContent)"
            />
          </div>
        </div>
      </div>

      <Transition name="fade">
        <ScrollToTop v-if="showScrollTop" @click="scrollToTop" />
      </Transition>

      <!-- Input -->
      <ChatInput
        ref="chatInputRef"
        v-model="inputMessage"
        :is-loading="isLoading"
        @send="sendMessage"

        @stop="stopGeneration"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import AppHeader from '@/components/layout/AppHeader.vue'
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
const mobileSidebarOpen = ref(false)
const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const inputMessage = ref('')
const isLoading = ref(false)
const connectionStatus = ref('connecting')
const models = ref([])
const selectedModel = ref('qwen2.5:3b')
const showScrollTop = ref(false)

const activeAbortController = ref(null)
// Refs
const messagesContainer = ref(null)
const chatInputRef = ref(null)

// Sample questions
const sampleQuestions = [
  'Apa dasar hukum penerapan SPBE di instansi pemerintah?',
  'Apa kewajiban instansi dalam penyusunan arsitektur SPBE?',
  'Bagaimana hubungan audit SPBE dengan evaluasi SPBE?',
  'Apa saja dokumen yang perlu disiapkan untuk tata kelola SPBE?'
]

const quickActions = [
  'Lihat pasal',
  'Ringkas',
  'Bandingkan',
  'Tampilkan sumber'
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
  if (isLoading.value) stopGeneration()
  closeMobileSidebar()
  currentSessionId.value = null
  messages.value = []
  await nextTick()
  chatInputRef.value?.focusInput()
}

function toggleSidebar() {
  if (mobileSidebarOpen.value) {
    closeMobileSidebar()
    return
  }
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function openMobileSidebar() {
  mobileSidebarOpen.value = true
}

function closeMobileSidebar() {
  mobileSidebarOpen.value = false
}

async function loadSession(sessionId) {
  if (isLoading.value) stopGeneration()
  closeMobileSidebar()
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

async function clearCurrentChat() {
  if (!confirm('Hapus percakapan saat ini?')) return
  if (isLoading.value) stopGeneration()

  try {
    if (currentSessionId.value) {
      const sessionId = currentSessionId.value
      await deleteSessionService(sessionId)
      sessions.value = sessions.value.filter((s) => s.id !== sessionId)
    }
    currentSessionId.value = null
    messages.value = []
    inputMessage.value = ''
    await nextTick()
    chatInputRef.value?.resetInputHeight()
    chatInputRef.value?.focusInput()
  } catch (error) {
    console.error('Failed to clear current chat:', error)
  }
}

async function handleRenameSession({ id, title }) {
  const session = sessions.value.find(s => s.id === id)
  if (!session) {
    console.warn(`handleRenameSession: session id=${id} not found in local state`)
    return
  }
  const previousTitle = session.title
  session.title = title
  try {
    await updateSessionTitle(id, title)
  } catch (err) {
    session.title = previousTitle
    console.error(`Failed to rename session (id=${id}):`, err)
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
  inputMessage.value = ''
  chatInputRef.value?.resetInputHeight()

  await submitChatMessage(userMessage, { appendUser: true })
}

async function submitChatMessage(userMessage, options = {}) {
  if (!userMessage.trim() || isLoading.value) return

  const appendUser = options.appendUser !== false
  const assistantIndex = Number.isInteger(options.assistantIndex) ? options.assistantIndex : null
  const isStartingNewSession = !currentSessionId.value
  const generatedTitle = generateSessionTitleFromMessage(userMessage)

  if (appendUser) {
    const nowUser = new Date()
    const userHhmm = `${String(nowUser.getHours()).padStart(2, '0')}:${String(nowUser.getMinutes()).padStart(2, '0')}`
    messages.value.push({ role: 'user', content: userMessage, timestamp: userHhmm })
  }

  const loadingIdx = assistantIndex ?? messages.value.length
  messages.value.splice(loadingIdx, 0, { role: 'assistant', loading: true, loadingText: 'Sedang menyiapkan jawaban...' })

  await nextTick()
  scrollToBottom()

  isLoading.value = true

  let lastScroll = 0
  const throttledScroll = () => {
    const now = Date.now()
    if (now - lastScroll > 150) { lastScroll = now; scrollToBottom() }
  }

  let streamedContent = ''
  let pendingValidation = null
  const abortController = new AbortController()
  activeAbortController.value = abortController

  try {

    await streamChat(
      {
        message: userMessage,
        session_id: currentSessionId.value,
        model: selectedModel.value,
        top_k: 5,
        max_tokens: 2048
      },
      {
        onRetrieval: async (data) => {
          messages.value[loadingIdx] = {
            role: 'assistant',
            loading: true,
            loadingText: `Ditemukan ${data.count} sumber regulasi, sedang menyiapkan jawaban...`
          }
        },
        onToken: async (data) => {
          streamedContent += data.t
          // Langsung tampilkan konten begitu token pertama tiba — hapus loading state
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
      },
      { signal: abortController.signal }
    )
  } catch (error) {
    if (abortController.signal.aborted || error.name === 'AbortError') {
      messages.value[loadingIdx] = {
        role: 'assistant',
        content: streamedContent
          ? `${streamedContent}\n\n_Respons dihentikan oleh pengguna._`
          : 'Respons dihentikan oleh pengguna.',
        cancelled: true
      }
    } else {
      console.error('Chat error:', error)
      messages.value[loadingIdx] = {
        role: 'assistant',
        content: `Error: ${error.message}. Pastikan server backend berjalan.`
      }
    }
  } finally {
    isLoading.value = false
    if (activeAbortController.value === abortController) {
      activeAbortController.value = null
    }
    await nextTick()
    scrollToBottom()
  }
}

function stopGeneration() {
  activeAbortController.value?.abort()
}

function findPreviousUserIndex(fromIndex) {
  for (let i = fromIndex - 1; i >= 0; i -= 1) {
    if (messages.value[i]?.role === 'user') return i
  }
  return -1
}

function canRegenerateMessage(index) {
  return !isLoading.value && messages.value[index]?.role === 'assistant' && findPreviousUserIndex(index) !== -1
}

function canEditRetryMessage(index) {
  return !isLoading.value && messages.value[index]?.role === 'user'
}

async function regenerateFrom(index) {
  if (!canRegenerateMessage(index)) return
  const userIndex = findPreviousUserIndex(index)
  const prompt = messages.value[userIndex].content
  messages.value.splice(index, 1)
  await submitChatMessage(prompt, { appendUser: false, assistantIndex: index })
}

async function editRetryFrom(userIndex) {
  if (!canEditRetryMessage(userIndex)) return
  editingMessageIndex.value = userIndex
  editingMessageContent.value = messages.value[userIndex].content
}

async function submitEditedMessage(userIndex, newContent) {
  editingMessageIndex.value = null
  if (!newContent || !newContent.trim() || newContent.trim() === messages.value[userIndex].content) return

  messages.value.splice(userIndex)
  inputMessage.value = ''
  await submitChatMessage(newContent.trim(), { appendUser: true })
}

function sendSampleQuestion(question) {
  inputMessage.value = question
  sendMessage()
}

function applyQuickAction(action) {
  const prefixByAction = {
    'Lihat pasal': 'Tampilkan pasal atau bagian dokumen yang relevan untuk pertanyaan berikut: ',
    'Ringkas': 'Buat ringkasan formal dan singkat berdasarkan sumber tersedia: ',
    'Bandingkan': 'Bandingkan regulasi berikut dan jelaskan perbedaannya: ',
    'Tampilkan sumber': 'Tampilkan sumber regulasi dan rujukan yang relevan untuk pertanyaan berikut: '
  }

  inputMessage.value = `${prefixByAction[action] || ''}${inputMessage.value}`.trim()
  nextTick(() => chatInputRef.value?.focusInput())
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
  position: relative;
  display: flex;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: var(--color-surface-page);
}

.mobile-sidebar-toggle,
.mobile-sidebar-backdrop {
  display: none;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.chat-workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  padding: 14px 14px 0;
  overflow: hidden;
  background: var(--color-surface-page);
}

.consultation-column {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border-blue);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: var(--color-surface-panel);
  box-shadow: var(--shadow-panel);
}

.quick-action-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-blue-light);
  background: var(--color-surface-panel-muted);
}

.quick-action-strip button {
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-sm);
  background: var(--color-white);
  color: var(--color-action-blue-dark);
  cursor: pointer;
  font: 600 12px var(--font-ui);
  padding: 7px 10px;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.quick-action-strip button:hover {
  border-color: var(--color-action-blue);
  color: var(--color-action-blue);
  background: var(--color-surface-soft-blue);
}


/* Messages area */
.messages-area {
  flex: 1;
  overflow-y: auto;
  background: var(--color-white);
  padding: 24px 0 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}
/* Welcome screen */
.welcome-screen {
  max-width: 560px;
  margin: 56px auto 0;
  padding: 0 28px;
  text-align: left;
}

.welcome-logo {
  width: 40px;
  height: 40px;
  background: var(--color-action-blue);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: 14px;
  color: var(--color-white);
  margin: 0 0 14px;
}

.welcome-title {
  font-family: var(--font-ui);
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-strong);
  margin: 0 0 8px;
}

.welcome-desc {
  font-family: var(--font-ui);
  font-size: 14px;
  color: var(--color-text-muted);
  line-height: 1.55;
  margin: 0 0 22px;
  font-style: normal;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-btn {
  background: var(--color-white);
  border: 1px solid var(--color-border-blue);
  padding: 10px 12px;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--color-text-strong);
  text-align: left;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: border-color 0.15s, background 0.15s;
}

.suggestion-btn:hover {
  border-color: var(--color-action-blue);
  background: var(--color-surface-soft-blue);
}


@media (max-width: 1180px) {
  .chat-workspace { grid-template-columns: 1fr; overflow-y: auto; }
  .source-panel { overflow: visible; }
  .evidence-panel { min-height: auto; }
}

@media (max-width: 820px) {
  .chat-workspace { padding: 10px 10px 0; }
  .quick-action-strip { padding: 12px; }
}

@media (max-width: 720px) {
  .mobile-sidebar-toggle {
    position: fixed;
    left: 12px;
    bottom: calc(86px + env(safe-area-inset-bottom, 0px));
    z-index: var(--z-dropdown);
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 44px;
    padding: 0 14px;
    border: 1px solid rgba(11, 74, 191, 0.2);
    border-radius: var(--radius-pill);
    background: var(--color-white);
    color: var(--color-action-blue-dark);
    box-shadow: 0 10px 24px rgba(12, 43, 84, 0.16);
    cursor: pointer;
    font: 700 12px var(--font-ui);
  }

  .mobile-sidebar-toggle-icon,
  .mobile-sidebar-toggle-icon::before,
  .mobile-sidebar-toggle-icon::after {
    display: block;
    width: 14px;
    height: 2px;
    border-radius: var(--radius-pill);
    background: currentColor;
  }

  .mobile-sidebar-toggle-icon {
    position: relative;
  }

  .mobile-sidebar-toggle-icon::before,
  .mobile-sidebar-toggle-icon::after {
    content: '';
    position: absolute;
    left: 0;
  }

  .mobile-sidebar-toggle-icon::before { top: -5px; }
  .mobile-sidebar-toggle-icon::after { top: 5px; }

  .mobile-sidebar-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal-backdrop);
    display: block;
    background: rgba(7, 31, 69, 0.44);
  }

  .chat-workspace {
    padding: 8px 8px 0;
  }

  .consultation-column {
    border-radius: var(--radius-md) var(--radius-md) 0 0;
  }

  .quick-action-strip {
    flex-wrap: nowrap;
    gap: 6px;
    overflow-x: auto;
    padding: 10px 10px 9px;
    scrollbar-width: none;
  }

  .quick-action-strip::-webkit-scrollbar {
    display: none;
  }

  .quick-action-strip button {
    flex: 0 0 auto;
    min-height: 36px;
    padding: 7px 10px;
  }

  .messages-area {
    padding-top: 18px;
  }

  .welcome-screen {
    margin-top: 32px;
    padding: 0 18px;
  }
}

@media (max-width: 420px) {
  .mobile-sidebar-toggle {
    left: 10px;
    bottom: calc(78px + env(safe-area-inset-bottom, 0px));
    min-height: 42px;
    padding: 0 12px;
  }

  .chat-workspace {
    padding-inline: 6px;
  }

  .welcome-title {
    font-size: 20px;
  }
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
