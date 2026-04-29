<template>
  <div class="home-view">
    <!-- Topbar (using global .topbar classes) -->
    <nav class="topbar">
      <div class="topbar-brand">
        <div class="topbar-logo">B</div>
        <div>
          <div class="topbar-title">SPBE Asisten</div>
          <div class="topbar-subtitle">Badan Siber dan Sandi Negara</div>
        </div>
      </div>
      <div class="topbar-nav">
        <router-link to="/home" class="topbar-nav-link active">Beranda</router-link>
        <router-link to="/" class="topbar-nav-link">Chat</router-link>
        <router-link to="/documents" class="topbar-nav-link">Dokumen</router-link>
      </div>
    </nav>

    <!-- Hero section -->
    <div class="hero">
      <div class="hero-inner">
        <div class="hero-eyebrow">Sistem RAG · BSSN</div>
        <h1 class="hero-title">Tanya Jawab Regulasi <span>SPBE</span></h1>
        <p class="hero-subtitle">berbasis kecerdasan buatan &amp; dokumen resmi</p>
        <p class="hero-desc">
          Cari, tanya, dan pahami peraturan SPBE secara cepat dan akurat. Setiap jawaban dilengkapi sitasi langsung dari dokumen resmi — Permenpan RB, Surat Edaran, dan Hasil Audit BSSN.
        </p>
        <router-link to="/" class="hero-cta">Mulai Bertanya →</router-link>
        <div class="hero-stats">
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.docCount }}</span>
            <span class="hero-stat-label">Dokumen Terindekas</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.chunkCount }}</span>
            <span class="hero-stat-label">Chunk Tersedia</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.sessionCount }}</span>
            <span class="hero-stat-label">Total Sesi</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Cards section -->
    <div class="cards-section">
      <div class="section-heading">Menu Utama</div>
      <div class="cards-grid">
        <div class="home-card" @click="$router.push('/')">
          <div class="card-icon">💬</div>
          <h3 class="card-title">Mulai Bertanya</h3>
          <p class="card-desc">Ajukan pertanyaan tentang regulasi SPBE, hasil audit BSSN, atau kebijakan terkait. Jawaban disertai sitasi dokumen resmi.</p>
          <div class="card-arrow">BUKA CHAT →</div>
        </div>
        <div class="home-card" @click="$router.push('/documents')">
          <div class="card-icon">📄</div>
          <h3 class="card-title">Kelola Dokumen</h3>
          <p class="card-desc">Unggah, pratinjau, dan indeks dokumen PDF baru ke sistem. Kelola dokumen yang tersedia sebagai sumber jawaban AI.</p>
          <div class="card-arrow">KELOLA →</div>
        </div>
      </div>
    </div>

    <!-- Status panel -->
    <div class="status-section">
      <div class="section-heading">Status Sistem</div>
      <div class="status-panel">
        <div class="status-panel-header">
          <span class="status-panel-title">Kondisi Layanan</span>
        </div>
        <div class="status-items">
          <div class="status-row">
            <span class="status-row-label">🖥 Backend API</span>
            <span v-if="loading" class="badge badge-warn">Memeriksa...</span>
            <span v-else-if="health && health.status === 'healthy'" class="badge badge-ok">Aktif</span>
            <span v-else class="badge badge-warn">Tidak Tersedia</span>
          </div>
          <div class="status-row">
            <span class="status-row-label">🧠 Model LLM</span>
            <span v-if="health && health.services?.llm_model === 'present'" class="badge badge-ok">qwen3.5:4b</span>
            <span v-else class="badge badge-warn">Tidak Tersedia</span>
          </div>
          <div class="status-row">
            <span class="status-row-label">🔍 Qdrant Vector DB</span>
            <span v-if="health && health.services?.qdrant === 'healthy'" class="badge badge-ok">Terhubung</span>
            <span v-else class="badge badge-warn">—</span>
          </div>
          <div class="status-row">
            <span class="status-row-label">🗄 Database</span>
            <span v-if="health && health.services?.database === 'healthy'" class="badge badge-ok">SQLite</span>
            <span v-else class="badge badge-warn">—</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { checkHealth } from '@/services/chatService'
import { listDocuments } from '@/services/documentService'
import api from '@/services/api'

const health = ref(null)
const loading = ref(true)
const stats = ref({ docCount: '…', chunkCount: '…', sessionCount: '…' })

onMounted(async () => {
  try {
    const [healthData, docs, sessionsResp] = await Promise.allSettled([
      checkHealth(),
      listDocuments(),
      api.get('/api/sessions/'),
    ])
    if (healthData.status === 'fulfilled') health.value = healthData.value
    if (docs.status === 'fulfilled') {
      const list = docs.value ?? []
      stats.value.docCount = list.length
      stats.value.chunkCount = list.reduce((sum, d) => sum + (d.chunk_count ?? 0), 0).toLocaleString('id-ID')
    }
    if (sessionsResp.status === 'fulfilled') {
      stats.value.sessionCount = (sessionsResp.value?.data ?? []).length
    }
  } catch (error) {
    console.error('Home init failed:', error)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.home-view {
  min-height: 100vh;
  background: var(--color-cream);
}

/* ── Hero ─────────────────────────────────────────────── */
.hero {
  background: linear-gradient(160deg, #1a3a6b 0%, #0f2444 55%, #0a1a33 100%);
  padding: 64px 32px 56px;
  position: relative;
  overflow: hidden;
}

.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 79px,
      rgba(201, 168, 76, 0.03) 79px,
      rgba(201, 168, 76, 0.03) 80px
    ),
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 79px,
      rgba(201, 168, 76, 0.03) 79px,
      rgba(201, 168, 76, 0.03) 80px
    );
  pointer-events: none;
}

.hero-inner {
  max-width: 820px;
  margin: 0 auto;
  position: relative;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(201, 168, 76, 0.12);
  border: 1px solid rgba(201, 168, 76, 0.3);
  color: var(--color-gold);
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 5px 12px;
  border-radius: 2px;
  margin-bottom: 20px;
  font-family: var(--font-ui);
}

.hero-eyebrow::before {
  content: '';
  width: 5px;
  height: 5px;
  background: var(--color-gold);
  border-radius: 50%;
  flex-shrink: 0;
}

.hero-title {
  font-family: var(--font-display);
  font-size: 44px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.5px;
  margin: 0 0 6px;
  line-height: 1.1;
}

.hero-title span {
  color: var(--color-gold);
}

.hero-subtitle {
  font-family: var(--font-display);
  font-size: 18px;
  font-style: italic;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 28px;
}

.hero-desc {
  font-family: var(--font-body);
  font-size: 15px;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.7;
  max-width: 560px;
  margin: 0 0 32px;
}

.hero-cta {
  display: inline-flex;
  background: var(--color-gold);
  color: var(--color-navy);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 12px 24px;
  border-radius: 2px;
  text-decoration: none;
  transition: background 0.2s, transform 0.15s;
  font-family: var(--font-ui);
}

.hero-cta:hover {
  background: var(--color-gold-hover, #b8922e);
  transform: translateY(-1px);
}

.hero-stats {
  display: flex;
  gap: 32px;
  margin-top: 40px;
  padding-top: 32px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.hero-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hero-stat-num {
  display: block;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-gold);
  line-height: 1;
}

.hero-stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.5px;
  font-family: var(--font-ui);
}

/* ── Cards ────────────────────────────────────────────── */
.cards-section {
  max-width: 820px;
  margin: 0 auto;
  padding: 40px 32px;
}

.cards-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.home-card {
  background: #ffffff;
  border: 1px solid var(--color-border, #e2e0db);
  border-radius: 3px;
  padding: 24px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
  display: flex;
  flex-direction: column;
  gap: 10px;
  position: relative;
  overflow: hidden;
}

.home-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-navy);
  opacity: 0;
  transition: opacity 0.2s;
}

.home-card:hover {
  border-color: var(--color-navy);
  box-shadow: 0 4px 20px rgba(26, 58, 107, 0.1);
  transform: translateY(-2px);
}

.home-card:hover::before {
  opacity: 1;
}

.card-icon {
  width: 40px;
  height: 40px;
  background: #eef2f9;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.card-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-navy);
  margin: 0;
}

.card-desc {
  font-family: var(--font-body);
  font-size: 13px;
  color: #666666;
  line-height: 1.6;
  margin: 0;
}

.card-arrow {
  font-size: 10px;
  color: var(--color-gold);
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-top: auto;
  font-family: var(--font-ui);
}

/* ── Status ───────────────────────────────────────────── */
.status-section {
  max-width: 820px;
  margin: 0 auto;
  padding: 0 32px 48px;
}

.status-panel {
  background: #ffffff;
  border: 1px solid var(--color-border, #e2e0db);
  border-radius: 3px;
  overflow: hidden;
}

.status-panel-header {
  background: #faf9f7;
  border-bottom: 1px solid var(--color-border, #e2e0db);
  padding: 12px 20px;
}

.status-panel-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-navy);
  letter-spacing: 0.5px;
  font-family: var(--font-ui);
  text-transform: uppercase;
}

.status-items {
  padding: 4px 0;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 20px;
  border-bottom: 1px solid var(--color-border-light, #f0ede8);
}

.status-row:last-child {
  border-bottom: none;
}

.status-row-label {
  font-size: 12px;
  color: #555555;
  font-family: var(--font-ui);
}
</style>
