<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <button @click="createNewChat" class="new-chat-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span v-if="!sidebarCollapsed">New Chat</span>
        </button>
        <button @click="sidebarCollapsed = !sidebarCollapsed" class="collapse-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 12h18M3 6h18M3 18h18"></path>
          </svg>
        </button>
      </div>

      <div class="chat-history" v-if="!sidebarCollapsed">
        <div class="history-section">
          <div class="section-title">Recent</div>
          <div 
            v-for="session in sessions" 
            :key="session.id"
            class="chat-item"
            :class="{ active: currentSessionId === session.id }"
            @click="loadSession(session.id)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <span class="chat-title">{{ session.title }}</span>
            <button @click.stop="deleteSession(session.id)" class="delete-btn">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
          <div v-if="sessions.length === 0" class="no-chats">
            No conversations yet
          </div>
        </div>
      </div>

      <div class="sidebar-footer" v-if="!sidebarCollapsed">
        <router-link to="/documents" class="docs-link">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <line x1="9" y1="15" x2="15" y2="15"/>
          </svg>
          <span>Kelola Dokumen</span>
        </router-link>
        <div class="model-selector">
          <label>Model:</label>
          <select v-model="selectedModel" @change="onModelChange">
            <option v-for="m in models" :key="m.name" :value="m.name">
              {{ m.name }} ({{ m.size }})
            </option>
          </select>
        </div>
      </div>
    </aside>

    <!-- Main Chat Area -->
    <main class="chat-main">
      <!-- Header -->
      <header class="chat-header">
        <div class="header-left">
          <h1>SPBE RAG Assistant</h1>
          <span class="model-badge">{{ selectedModel }}</span>
        </div>
        <div class="header-right">
          <div class="status-indicator" :class="connectionStatus">
            <span class="status-dot"></span>
            <span>{{ connectionStatus === 'connected' ? 'Connected' : 'Connecting...' }}</span>
          </div>
        </div>
      </header>

      <!-- Messages Area -->
      <div class="messages-container" ref="messagesContainer">
        <!-- Welcome Screen -->
        <div v-if="messages.length === 0" class="welcome-screen">
          <div class="welcome-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
              <path d="M2 17l10 5 10-5"></path>
              <path d="M2 12l10 5 10-5"></path>
            </svg>
          </div>
          <h2>SPBE RAG Assistant</h2>
          <p>Tanya tentang peraturan SPBE, audit keamanan, dan dokumen terkait.</p>
          
          <div class="suggestions">
            <button 
              v-for="q in sampleQuestions" 
              :key="q"
              @click="sendSampleQuestion(q)"
              class="suggestion-btn"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <!-- Messages -->
        <div v-for="(msg, idx) in messages" :key="idx" class="message" :class="msg.role">
          <div class="message-avatar">
            <span v-if="msg.role === 'user'">U</span>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
              <path d="M2 17l10 5 10-5"></path>
              <path d="M2 12l10 5 10-5"></path>
            </svg>
          </div>
          <div class="message-content">
            <!-- Loading (retrieval phase) -->
            <div v-if="msg.loading" class="loading-indicator">
              <div class="typing-dots">
                <span></span><span></span><span></span>
              </div>
              <span class="loading-text">{{ msg.loadingText || 'Searching documents...' }}</span>
            </div>
            
            <!-- Content (streaming or complete) -->
            <div v-else>
              <div class="message-text" v-html="formatMessage(msg.content)"></div>
              
              <!-- Streaming cursor -->
              <span v-if="msg.streaming" class="streaming-cursor"></span>
              
              <!-- Sources (only shown after streaming completes) -->
              <div v-if="msg.sources && msg.sources.length > 0 && !msg.streaming" class="sources">
                <div class="sources-title">Sources:</div>
                <div class="source-list">
                  <div v-for="src in msg.sources" :key="src.id" class="source-item">
                    <span class="source-id">[{{ src.id }}]</span>
                    <span class="source-name">{{ src.document }}</span>
                    <span v-if="src.section" class="source-section">{{ src.section }}</span>
                  </div>
                </div>
              </div>

              <!-- Timing (only shown after streaming completes) -->
              <div v-if="msg.timing && !msg.streaming" class="message-timing">
                {{ Math.round(msg.timing.total_ms) }}ms
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="input-container">
        <form @submit.prevent="sendMessage" class="input-form">
          <div class="input-wrapper">
            <textarea
              v-model="inputMessage"
              placeholder="Ketik pertanyaan Anda..."
              @keydown.enter.exact.prevent="sendMessage"
              @input="autoResize"
              ref="inputField"
              rows="1"
              :disabled="isLoading"
            ></textarea>
            <button 
              type="submit" 
              :disabled="!inputMessage.trim() || isLoading"
              class="send-btn"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
          <div class="input-footer">
            <label class="rag-toggle">
              <input type="checkbox" v-model="useRag" />
              <span>Use RAG</span>
            </label>
            <span class="footer-text">Press Enter to send</span>
          </div>
        </form>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'

// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

// Refs
const messagesContainer = ref(null)
const inputField = ref(null)

// Sample questions
const sampleQuestions = [
  'Apa itu SPBE?',
  'Apa saja domain dalam SPBE?',
  'Bagaimana prosedur audit keamanan?',
  'Jelaskan tentang Perpres 95 Tahun 2018'
]

// Initialize
onMounted(async () => {
  await Promise.all([
    fetchModels(),
    fetchSessions(),
    checkHealth()
  ])
})

// Fetch available models
async function fetchModels() {
  try {
    const response = await fetch(`${API_URL}/api/models`)
    if (response.ok) {
      models.value = await response.json()
      // Get default model
      const defaultRes = await fetch(`${API_URL}/api/models/default`)
      if (defaultRes.ok) {
        const data = await defaultRes.json()
        selectedModel.value = data.model
      }
    }
  } catch (error) {
    console.error('Failed to fetch models:', error)
  }
}

// Fetch chat sessions
async function fetchSessions() {
  try {
    const response = await fetch(`${API_URL}/api/sessions`)
    if (response.ok) {
      sessions.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to fetch sessions:', error)
  }
}

// Check server health
async function checkHealth() {
  try {
    const response = await fetch(`${API_URL}/api/health`)
    if (response.ok) {
      connectionStatus.value = 'connected'
    } else {
      connectionStatus.value = 'disconnected'
    }
  } catch (error) {
    connectionStatus.value = 'disconnected'
    setTimeout(checkHealth, 5000)
  }
}

// Create new chat
async function createNewChat() {
  currentSessionId.value = null
  messages.value = []
  await nextTick()
  inputField.value?.focus()
}

// Load session
async function loadSession(sessionId) {
  try {
    const response = await fetch(`${API_URL}/api/sessions/${sessionId}`)
    if (response.ok) {
      const session = await response.json()
      currentSessionId.value = session.id
      selectedModel.value = session.model
      messages.value = session.messages.map(m => ({
        role: m.role,
        content: m.content,
        sources: m.sources,
        timing: m.timing
      }))
      await nextTick()
      scrollToBottom()
    }
  } catch (error) {
    console.error('Failed to load session:', error)
  }
}

// Delete session
async function deleteSession(sessionId) {
  if (!confirm('Delete this conversation?')) return
  
  try {
    const response = await fetch(`${API_URL}/api/sessions/${sessionId}`, {
      method: 'DELETE'
    })
    if (response.ok) {
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
        messages.value = []
      }
    }
  } catch (error) {
    console.error('Failed to delete session:', error)
  }
}

// Model change
async function onModelChange() {
  try {
    await fetch(`${API_URL}/api/models/default?model=${encodeURIComponent(selectedModel.value)}`, {
      method: 'POST'
    })
  } catch (error) {
    console.error('Failed to set default model:', error)
  }
}

// Send message with SSE streaming
async function sendMessage() {
  if (!inputMessage.value.trim() || isLoading.value) return
  
  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  
  // Reset textarea height
  if (inputField.value) {
    inputField.value.style.height = 'auto'
  }
  
  // Add user message
  messages.value.push({
    role: 'user',
    content: userMessage
  })
  
  // Add loading message
  const loadingIdx = messages.value.length
  messages.value.push({
    role: 'assistant',
    loading: true,
    loadingText: 'Searching documents...'
  })
  
  await nextTick()
  scrollToBottom()
  
  isLoading.value = true
  
  // Throttle scroll during streaming (every 150ms max)
  let lastScroll = 0
  const throttledScroll = () => {
    const now = Date.now()
    if (now - lastScroll > 150) {
      lastScroll = now
      scrollToBottom()
    }
  }
  
  try {
    const response = await fetch(`${API_URL}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMessage,
        session_id: currentSessionId.value,
        model: selectedModel.value,
        use_rag: useRag.value,
        top_k: 5,
        max_tokens: 2048
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`)
    }
    
    // Read SSE stream
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let streamedContent = ''
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      
      // Process complete SSE events (separated by double newline)
      const events = buffer.split('\n\n')
      buffer = events.pop() // Keep incomplete event in buffer
      
      for (const eventBlock of events) {
        if (!eventBlock.trim()) continue
        
        // Parse SSE event: "event: <type>\ndata: <json>"
        let eventType = 'message'
        let eventData = ''
        
        for (const line of eventBlock.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6)
          }
        }
        
        if (!eventData) continue
        
        try {
          const data = JSON.parse(eventData)
          
          if (eventType === 'retrieval') {
            // Documents found, update loading text
            messages.value[loadingIdx] = {
              role: 'assistant',
              loading: true,
              loadingText: `Found ${data.count} documents, generating answer...`
            }
          
          } else if (eventType === 'token') {
            // Append token to content
            streamedContent += data.t
            messages.value[loadingIdx] = {
              role: 'assistant',
              content: streamedContent,
              streaming: true
            }
            throttledScroll()
          
          } else if (eventType === 'complete') {
            // Final post-processed answer with sources
            messages.value[loadingIdx] = {
              role: 'assistant',
              content: data.answer,
              sources: data.sources,
              timing: data.timing
            }
            
            // Update session ID from server
            if (data.session_id) {
              currentSessionId.value = data.session_id
            }
          
          } else if (eventType === 'session') {
            // Session info update (LLM-generated title)
            if (data.session_id && data.title) {
              // Update existing session in list or add new one
              const existing = sessions.value.find(s => s.id === data.session_id)
              if (existing) {
                existing.title = data.title
              } else {
                // Refresh full session list to get the new session
                await fetchSessions()
              }
            }
          
          } else if (eventType === 'error') {
            messages.value[loadingIdx] = {
              role: 'assistant',
              content: `Error: ${data.error}. Make sure the backend server is running.`
            }
          }
        } catch (parseErr) {
          console.warn('SSE parse error:', parseErr, eventData)
        }
      }
    }
    
  } catch (error) {
    console.error('Chat error:', error)
    messages.value[loadingIdx] = {
      role: 'assistant',
      content: `Error: ${error.message}. Make sure the backend server is running.`
    }
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

// Send sample question
function sendSampleQuestion(question) {
  inputMessage.value = question
  sendMessage()
}

// Format message content with markdown support
function formatMessage(text) {
  if (!text) return ''
  
  let formatted = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  
  // Headings (must be before line breaks)
  formatted = formatted.replace(/^#### (.*?)$/gm, '<h4 class="md-h4">$1</h4>')
  formatted = formatted.replace(/^### (.*?)$/gm, '<h3 class="md-h3">$1</h3>')
  formatted = formatted.replace(/^## (.*?)$/gm, '<h2 class="md-h2">$1</h2>')
  formatted = formatted.replace(/^# (.*?)$/gm, '<h1 class="md-h1">$1</h1>')
  
  // Bold (** or __)
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  formatted = formatted.replace(/__(.*?)__/g, '<strong>$1</strong>')
  
  // Italic (* or _)
  formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  
  // Code blocks
  formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
  formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>')
  
  // Horizontal rule
  formatted = formatted.replace(/^---$/gm, '<hr class="md-hr">')
  
  // Line breaks (but not inside headers)
  formatted = formatted.replace(/\n/g, '<br>')
  
  // Fix double br after headings
  formatted = formatted.replace(/<\/h(\d)><br>/g, '</h$1>')
  formatted = formatted.replace(/<hr class="md-hr"><br>/g, '<hr class="md-hr">')
  
  // Citations
  formatted = formatted.replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>')
  
  return formatted
}

// Auto-resize textarea
function autoResize(event) {
  const el = event.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

// Scroll to bottom
function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --sidebar-width: 260px;
  --sidebar-collapsed: 60px;
  --bg-primary: #212121;
  --bg-secondary: #171717;
  --bg-tertiary: #2f2f2f;
  --text-primary: #ececec;
  --text-secondary: #b4b4b4;
  --accent: #10a37f;
  --accent-hover: #1a7f64;
  --border-color: #3f3f3f;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: var(--sidebar-width);
  background-color: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  border-right: 1px solid var(--border-color);
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed);
}

.sidebar-header {
  padding: 12px;
  display: flex;
  gap: 8px;
}

.new-chat-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  background-color: transparent;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.2s;
}

.new-chat-btn:hover {
  background-color: var(--bg-tertiary);
}

.collapse-btn {
  padding: 12px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 8px;
}

.collapse-btn:hover {
  background-color: var(--bg-tertiary);
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

.section-title {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 8px 0;
  font-weight: 500;
}

.chat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 2px;
}

.chat-item:hover {
  background-color: var(--bg-tertiary);
}

.chat-item.active {
  background-color: var(--bg-tertiary);
}

.chat-title {
  flex: 1;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.delete-btn {
  opacity: 0;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.chat-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ef4444;
}

.no-chats {
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 20px 0;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border-color);
}

.docs-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  text-decoration: none;
  font-size: 13px;
  transition: all 0.2s;
}

.docs-link:hover {
  background-color: #6366f1;
  border-color: #6366f1;
}

.docs-link svg {
  color: #6366f1;
}

.docs-link:hover svg {
  color: white;
}

.model-selector {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-selector label {
  font-size: 12px;
  color: var(--text-secondary);
}

.model-selector select {
  padding: 8px 12px;
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
}

/* Main Chat Area */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-primary);
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h1 {
  font-size: 16px;
  font-weight: 600;
}

.model-badge {
  font-size: 12px;
  padding: 4px 8px;
  background-color: var(--bg-tertiary);
  border-radius: 4px;
  color: var(--text-secondary);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #ef4444;
}

.status-indicator.connected .status-dot {
  background-color: #22c55e;
}

/* Messages */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
}

.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 40px;
}

.welcome-icon {
  margin-bottom: 20px;
  color: var(--accent);
}

.welcome-screen h2 {
  font-size: 24px;
  margin-bottom: 8px;
}

.welcome-screen p {
  color: var(--text-secondary);
  margin-bottom: 30px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  max-width: 600px;
}

.suggestion-btn {
  padding: 10px 16px;
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.suggestion-btn:hover {
  background-color: var(--border-color);
}

.message {
  display: flex;
  gap: 16px;
  padding: 20px 80px;
  max-width: 100%;
}

.message.user {
  background-color: var(--bg-primary);
}

.message.assistant {
  background-color: var(--bg-secondary);
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
  font-weight: 600;
}

.message.user .message-avatar {
  background-color: #5c6bc0;
}

.message.assistant .message-avatar {
  background-color: var(--accent);
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-text {
  line-height: 1.7;
  font-size: 15px;
}

.message-text code {
  background-color: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
}

.message-text pre {
  background-color: var(--bg-tertiary);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}

.message-text pre code {
  background: none;
  padding: 0;
}

.citation {
  display: inline-block;
  background-color: var(--accent);
  color: white;
  font-size: 11px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 500;
  margin: 0 1px;
}

/* Markdown headings */
.md-h1, .md-h2, .md-h3, .md-h4 {
  margin: 16px 0 8px 0;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.md-h1 { font-size: 1.5em; }
.md-h2 { font-size: 1.3em; }
.md-h3 { font-size: 1.15em; color: var(--accent); }
.md-h4 { font-size: 1em; }

.md-hr {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 12px 0;
}

.sources {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.sources-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
  font-weight: 500;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.source-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.source-id {
  color: var(--accent);
  font-weight: 500;
}

.source-name {
  color: var(--text-primary);
}

.source-section {
  font-style: italic;
}

.message-timing {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
}

.typing-dots {
  display: flex;
  gap: 4px;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  background-color: var(--text-secondary);
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}

.loading-text {
  color: var(--text-secondary);
  font-size: 14px;
}

/* Streaming cursor - blinking caret while LLM generates */
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: var(--text-primary, #e0e0e0);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink-cursor 0.8s infinite;
}

@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Input Area */
.input-container {
  padding: 20px 80px;
  background-color: var(--bg-primary);
}

.input-form {
  max-width: 768px;
  margin: 0 auto;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background-color: var(--bg-tertiary);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  padding: 8px 12px;
}

.input-wrapper:focus-within {
  border-color: var(--accent);
}

.input-wrapper textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  max-height: 200px;
  padding: 8px 0;
}

.input-wrapper textarea::placeholder {
  color: var(--text-secondary);
}

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background-color: var(--accent);
  border: none;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.send-btn:disabled {
  background-color: var(--bg-tertiary);
  color: var(--text-secondary);
  cursor: not-allowed;
}

.send-btn:not(:disabled):hover {
  background-color: var(--accent-hover);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.rag-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.rag-toggle input {
  accent-color: var(--accent);
}

/* Responsive */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    z-index: 100;
    height: 100%;
    transform: translateX(-100%);
  }
  
  .sidebar:not(.collapsed) {
    transform: translateX(0);
  }
  
  .message {
    padding: 16px 20px;
  }
  
  .input-container {
    padding: 16px 20px;
  }
}
</style>
