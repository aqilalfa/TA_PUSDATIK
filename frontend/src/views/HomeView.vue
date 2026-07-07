<template>
  <div class="home-view">
    <AppHeader active="home" />

    <nav class="anchor-nav" aria-label="Navigasi bagian Beranda">
      <a v-for="item in navItems" :key="item.href" :href="item.href">{{ item.label }}</a>
    </nav>

    <main class="landing-shell">
      <section id="beranda" class="hero-section landing-section">
        <div class="hero-copy">
          <div class="hero-eyebrow">Asisten Hukum SPBE · Sistem Internal Pemerintah</div>
          <h1>Gerbang konsultasi hukum untuk tata kelola SPBE yang tertib, cepat, dan berbasis rujukan.</h1>
          <p class="hero-desc">
            Asisten Hukum SPBE membantu pengguna internal menelusuri regulasi, memahami konteks kebijakan,
            dan memeriksa sumber jawaban sebelum mengambil keputusan administratif atau teknis.
          </p>
          <div class="hero-actions" aria-label="Aksi utama Beranda">
            <router-link to="/chat" class="primary-action">Mulai Konsultasi</router-link>
            <router-link v-if="canManageDocuments" to="/documents" class="secondary-action">Kelola Dokumen Rujukan</router-link>
            <a v-else href="#rujukan" class="secondary-action">Lihat Ruang Lingkup</a>
          </div>
          <div class="trust-row" aria-label="Ringkasan kepercayaan layanan">
            <span>Berbasis dokumen internal</span>
            <span>Jawaban disertai rujukan</span>
            <span>Riwayat untuk akuntabilitas</span>
          </div>
        </div>

        <div class="hero-panel" aria-label="Preview layanan Asisten Hukum SPBE">
          <div class="panel-header">
            <div>
              <span class="panel-kicker">Preview Konsultasi</span>
              <strong>Asisten Hukum SPBE</strong>
            </div>
            <span class="status-pill" :class="serviceStatusClass">{{ serviceStatusText }}</span>
          </div>

          <div class="preview-body">
            <div class="preview-question">Apa dasar hukum penerapan SPBE di instansi pemerintah?</div>
            <div class="preview-answer">
              <strong>Jawaban ringkas berbasis rujukan</strong>
              <p>
                Sistem membantu menyusun jawaban awal dengan menelusuri dokumen SPBE yang tersedia,
                lalu menampilkan sumber agar pengguna dapat melakukan verifikasi mandiri.
              </p>
              <div class="source-strip">
                <span>Rujukan</span>
                <span>Pasal/Kebijakan</span>
                <span>Konteks</span>
              </div>
            </div>
          </div>

          <div class="stats-grid" aria-label="Status ringkas layanan">
            <div class="stat-card">
              <span>Dokumen</span>
              <strong>{{ stats.docCount }}</strong>
            </div>
            <div class="stat-card">
              <span>Konteks</span>
              <strong>{{ stats.chunkCount }}</strong>
            </div>
            <div class="stat-card">
              <span>Sesi</span>
              <strong>{{ stats.sessionCount }}</strong>
            </div>
          </div>
        </div>
      </section>

      <section id="ruang-kerja" class="landing-section workspace-section">
        <div class="section-intro compact">
          <span class="section-heading">Ruang Kerja</span>
          <h2>Alur utama dibuat singkat: ajukan konsultasi, periksa rujukan, dan kelola dokumen sumber.</h2>
        </div>
        <div class="workspace-grid">
          <router-link
            v-for="action in workspaceActions"
            :key="action.title"
            :to="action.to"
            class="workspace-card"
            :class="{ disabled: action.adminOnly && !canManageDocuments }"
            :aria-disabled="action.adminOnly && !canManageDocuments ? 'true' : undefined"
            @click="action.adminOnly && !canManageDocuments && $event.preventDefault()"
          >
            <span class="workspace-code">{{ action.code }}</span>
            <div>
              <span class="workspace-kicker">{{ action.scope }}</span>
              <h3>{{ action.title }}</h3>
              <p>{{ action.desc }}</p>
            </div>
          </router-link>
        </div>
      </section>

      <section id="cara-kerja" class="landing-section workflow-section">
        <div class="section-intro">
          <span class="section-heading">Cara Kerja</span>
          <h2>Alur konsultasi dibuat sederhana agar pengguna fokus pada substansi regulasi.</h2>
        </div>
        <ol class="workflow-list">
          <li v-for="step in workflowSteps" :key="step.title" class="workflow-item">
            <span class="step-index">{{ step.no }}</span>
            <div>
              <h3>{{ step.title }}</h3>
              <p>{{ step.desc }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section id="rujukan" class="landing-section reference-section">
        <div class="reference-panel">
          <span class="section-heading">Rujukan & Domain</span>
          <h2>Fokus pada regulasi dan tata kelola Sistem Pemerintahan Berbasis Elektronik.</h2>
          <p>
            Asisten membantu telaah awal terhadap dokumen yang telah tersedia dalam sistem. Pengguna tetap
            perlu memeriksa sumber asli, konteks instansi, serta ketentuan terbaru yang berlaku.
          </p>
          <ul class="law-list">
            <li>Perpres No. 95 Tahun 2018 tentang Sistem Pemerintahan Berbasis Elektronik</li>
            <li>Perpres No. 132 Tahun 2022 tentang Arsitektur SPBE Nasional</li>
            <li>Permen PANRB No. 59 Tahun 2020 tentang Pemantauan dan Evaluasi SPBE</li>
            <li>Pedoman penyusunan arsitektur dan tata kelola SPBE instansi pemerintah</li>
          </ul>
        </div>
        <div class="domain-grid">
          <article v-for="domain in domains" :key="domain.title" class="domain-card">
            <h3>{{ domain.title }}</h3>
            <p>{{ domain.desc }}</p>
          </article>
        </div>
      </section>

      <section id="batasan" class="landing-section governance-section">
        <div class="section-intro compact">
          <span class="section-heading">Batasan Penggunaan</span>
          <h2>Mendukung telaah internal, bukan pengganti penilaian hukum final.</h2>
        </div>
        <div class="governance-grid">
          <article v-for="note in governanceNotes" :key="note.title" class="governance-card">
            <span class="governance-code">{{ note.code }}</span>
            <div>
              <h3>{{ note.title }}</h3>
              <p>{{ note.desc }}</p>
            </div>
          </article>
        </div>
      </section>

      <section class="landing-section final-cta" aria-label="Ajakan mulai konsultasi">
        <div>
          <span class="section-heading">Mulai Gunakan</span>
          <h2>Masuk ke ruang konsultasi dan ajukan pertanyaan SPBE dengan rujukan yang dapat diperiksa.</h2>
        </div>
        <router-link to="/chat" class="primary-action">Mulai Konsultasi Sekarang</router-link>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import { checkHealth } from '@/services/chatService'
import { listDocuments } from '@/services/documentService'
import { getCurrentUserProfile, isAdminUser } from '@/services/auth'
import api from '@/services/api'

const currentUser = ref(getCurrentUserProfile())
const canManageDocuments = computed(() => isAdminUser(currentUser.value))

const health = ref(null)
const loading = ref(true)
const stats = ref({ docCount: '…', chunkCount: '…', sessionCount: '…' })

const navItems = [
  { href: '#beranda', label: 'Beranda' },
  { href: '#ruang-kerja', label: 'Ruang Kerja' },
  { href: '#cara-kerja', label: 'Alur' },
  { href: '#rujukan', label: 'Rujukan' },
  { href: '#batasan', label: 'Batasan' },
]

const workspaceActions = [
  { code: '01', scope: 'Konsultasi', title: 'Mulai konsultasi regulasi', to: '/chat', desc: 'Ajukan pertanyaan SPBE dan tinjau jawaban yang dikaitkan dengan rujukan.' },
  { code: '02', scope: 'Dokumen', title: 'Kelola dokumen rujukan', to: '/documents', adminOnly: true, desc: 'Unggah, pratinjau, dan indeks dokumen hukum yang menjadi dasar pencarian.' },
  { code: '03', scope: 'Verifikasi', title: 'Periksa sumber jawaban', to: '/chat', desc: 'Gunakan daftar rujukan dan konteks untuk mengecek dasar jawaban sebelum dipakai.' },
  { code: '04', scope: 'Riwayat', title: 'Lanjutkan riwayat konsultasi', to: '/chat', desc: 'Buka kembali sesi konsultasi untuk menelusuri klarifikasi dan tindak lanjut.' },
]

const workflowSteps = [
  { no: '1', title: 'Ajukan pertanyaan', desc: 'Pengguna menulis isu hukum, kebijakan, atau tata kelola SPBE yang ingin ditelaah.' },
  { no: '2', title: 'Sistem mencari konteks', desc: 'Aplikasi menelusuri dokumen yang tersedia dan memilih konteks relevan melalui layanan yang sudah berjalan.' },
  { no: '3', title: 'Jawaban disusun', desc: 'Asisten menyajikan jawaban awal dalam bahasa formal dan terstruktur untuk kebutuhan kerja internal.' },
  { no: '4', title: 'Sumber diperiksa', desc: 'Pengguna meninjau rujukan sebelum membuat keputusan, eskalasi, atau dokumen resmi.' },
]

const domains = [
  { title: 'Kebijakan SPBE', desc: 'Dasar hukum, mandat, prinsip, dan ruang lingkup penerapan SPBE.' },
  { title: 'Tata Kelola', desc: 'Peran, proses, koordinasi, arsitektur, dan manajemen layanan digital.' },
  { title: 'Keamanan Informasi', desc: 'Aspek pengamanan, audit, risiko, dan kontrol yang relevan dengan layanan pemerintahan digital.' },
  { title: 'Evaluasi & Kepatuhan', desc: 'Pemantauan, penilaian, indikator, dan kebutuhan dokumentasi pendukung.' },
]

const securityNotes = undefined // removed - replaced by governanceNotes

const governanceNotes = [
  { code: 'I', title: 'Jawaban adalah telaah awal', desc: 'Jawaban sistem digunakan sebagai bantuan awal. Sumber asli dan konteks instansi tetap menjadi dasar pemeriksaan.' },
  { code: 'II', title: 'Sumber wajib diverifikasi', desc: 'Setiap jawaban disertai rujukan yang dapat dibuka. Pengguna bertanggung jawab memverifikasi sebelum mengambil keputusan.' },
  { code: 'III', title: 'Akses mengikuti peran pengguna', desc: 'Konsultasi tersedia untuk semua pengguna terdaftar. Kelola dokumen hanya tersedia untuk administrator.' },
  { code: 'IV', title: 'Data tidak digunakan untuk pelatihan publik', desc: 'Sistem ditujukan untuk keperluan internal. Tidak ada data yang dikirim ke model publik atau pihak luar.' },
]

const faqs = undefined // removed - content merged into governanceNotes

const serviceStatusText = computed(() => {
  if (loading.value) return 'Memeriksa'
  if (health.value?.status === 'healthy') return 'Aktif'
  return 'Perlu Dicek'
})

const serviceStatusClass = computed(() => {
  if (loading.value) return 'checking'
  if (health.value?.status === 'healthy') return 'healthy'
  return 'warning'
})

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
  min-height: 100dvh;
  background: linear-gradient(180deg, var(--color-surface-page) 0%, var(--color-surface-page-muted) 54%, var(--color-cream) 100%);
  color: #10233f;
}

.anchor-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  justify-content: center;
  gap: 6px;
  padding: 10px 20px;
  border-bottom: 1px solid rgba(26, 58, 107, 0.12);
  background: var(--color-white);
  box-shadow: 0 10px 28px rgba(18, 45, 87, 0.08);
}

.anchor-nav a {
  border-radius: 999px;
  color: #38577c;
  font: 700 11px var(--font-ui);
  letter-spacing: 0.25px;
  padding: 8px 12px;
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.anchor-nav a:hover {
  background: var(--color-surface-soft-blue);
  color: var(--color-navy);
  transform: translateY(-1px);
}

.anchor-nav a:focus-visible,
.primary-action:focus-visible,
.secondary-action:focus-visible,
.faq-item summary:focus-visible {
  outline: 3px solid rgba(201, 168, 76, 0.42);
  outline-offset: 3px;
}

.landing-shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 34px 24px 64px;
}

.landing-section {
  scroll-margin-top: 78px;
}

.landing-section + .landing-section {
  margin-top: 36px;
}

.hero-section {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.85fr);
  gap: 34px;
  align-items: center;
  overflow: hidden;
  padding: clamp(28px, 5vw, 54px);
  border: 1px solid rgba(26, 58, 107, 0.14);
  border-radius: 32px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96) 0%, rgba(238, 245, 255, 0.94) 58%, rgba(255, 252, 242, 0.95) 100%);
  box-shadow: 0 28px 70px rgba(12, 43, 84, 0.13);
}



.hero-copy,
.hero-panel,
.section-intro,
.reference-panel,
.final-cta > * {
  position: relative;
  z-index: 1;
}

.hero-eyebrow,
.section-heading {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  gap: 8px;
  color: var(--color-navy);
  font: 700 12px var(--font-ui);
  letter-spacing: 0.15px;
  text-transform: none;
}

.hero-eyebrow {
  margin-bottom: 18px;
  padding: 8px 13px;
  border: 1px solid rgba(201, 168, 76, 0.32);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
}

.section-heading::before,
.hero-eyebrow::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-gold);
  box-shadow: 0 0 0 4px rgba(201, 168, 76, 0.16);
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  max-width: 790px;
  color: var(--color-text-strong);
  font: 700 clamp(34px, 4.5vw, 58px)/1.03 var(--font-display);
  letter-spacing: -1.1px;
  text-wrap: balance;
}

h2 {
  max-width: 820px;
  color: var(--color-text-heading);
  font: 700 clamp(24px, 3vw, 36px)/1.18 var(--font-display);
  letter-spacing: -0.5px;
  text-wrap: balance;
}

h3 {
  color: var(--color-navy-dark);
  font: 700 16px/1.35 var(--font-ui);
}

.hero-desc,
.section-intro p,
.reference-panel p {
  max-width: 700px;
  color: var(--color-text-blue-muted);
  font: 400 16px/1.75 var(--font-ui);
}

.hero-desc {
  margin-top: 20px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.primary-action,
.secondary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 46px;
  padding: 0 22px;
  border-radius: 14px;
  font: 700 13px var(--font-ui);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.primary-action {
  background: linear-gradient(135deg, var(--color-navy) 0%, var(--color-action-blue) 100%);
  color: white;
  box-shadow: 0 16px 30px rgba(11, 74, 191, 0.25);
}

.secondary-action {
  border: 1px solid #cbd9ec;
  color: var(--color-action-blue-dark);
  background: rgba(255, 255, 255, 0.84);
}

.primary-action:hover,
.secondary-action:hover {
  transform: translateY(-2px);
}

.secondary-action:hover {
  border-color: rgba(201, 168, 76, 0.65);
}

.trust-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.trust-row span,
.source-strip span {
  border: 1px solid #dce6f3;
  border-radius: 999px;
  background: white;
  color: var(--color-text-blue-muted);
  font: 700 11px var(--font-ui);
  padding: 7px 10px;
}

.hero-panel,
.benefit-card,
.feature-card,
.reference-panel,
.domain-card,
.security-card,
.faq-item,
.final-cta {
  border: 1px solid rgba(26, 58, 107, 0.13);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 18px 40px rgba(12, 43, 84, 0.08);
}

.hero-panel {
  overflow: hidden;
  border-radius: 28px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding: 20px;
  border-bottom: 1px solid #edf2f8;
  background: linear-gradient(135deg, #ffffff, #f8fbff);
}

.panel-kicker {
  display: block;
  color: #7a8ba3;
  font: 700 10px var(--font-ui);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.panel-header strong {
  display: block;
  margin-top: 4px;
  color: var(--color-text-strong);
  font: 700 16px var(--font-ui);
}

.status-pill {
  align-self: flex-start;
  border-radius: 999px;
  font: 800 11px var(--font-ui);
  padding: 6px 10px;
}

.status-pill.healthy {
  background: var(--color-status-ok-bg);
  color: var(--color-status-ok-text);
}

.status-pill.checking,
.status-pill.warning {
  background: var(--color-status-warn-bg);
  color: var(--color-status-warn-text);
}

.preview-body {
  padding: 22px;
  background: linear-gradient(#f8fbff, #ffffff);
}

.preview-question {
  max-width: 82%;
  margin-left: auto;
  border-radius: 18px 18px 4px 18px;
  background: var(--color-surface-chat-blue);
  color: var(--color-text-strong);
  font: 700 13px/1.55 var(--font-ui);
  padding: 13px 15px;
}

.preview-answer {
  max-width: 94%;
  margin-top: 16px;
  border: 1px solid #dce6f3;
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 248, 223, 0.48), rgba(255, 255, 255, 0.96) 34%),
    white;
  color: var(--color-text-panel);
  font: 13px/1.65 var(--font-ui);
  padding: 17px;
  box-shadow: inset 0 0 0 1px rgba(201, 168, 76, 0.16);
}

.preview-answer strong {
  color: var(--color-action-blue-dark);
}

.preview-answer p {
  margin-top: 8px;
}

.source-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 13px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid #edf2f8;
}

.stat-card {
  padding: 16px;
  text-align: center;
}

.stat-card + .stat-card {
  border-left: 1px solid #edf2f8;
}

.stat-card span {
  display: block;
  color: #70829a;
  font: 700 10px var(--font-ui);
  letter-spacing: 0.8px;
  text-transform: uppercase;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  color: var(--color-text-strong);
  font: 700 22px var(--font-display);
}

.section-intro {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
}

.section-intro.compact {
  max-width: 850px;
}

.benefit-grid,
.feature-grid,
.domain-grid,
.security-grid {
  display: grid;
  gap: 16px;
}



.domain-card {
  border-radius: 22px;
  padding: 22px;
}



.domain-card h3 {
  margin-top: 14px;
}

.domain-card p,
.workflow-item p {
  margin-top: 9px;
  color: var(--color-text-panel-muted);
  font: 13px/1.65 var(--font-ui);
}



.workflow-section {
  border-radius: 28px;
  padding: 30px;
  background: linear-gradient(135deg, var(--color-navy-dark), #153f7d);
  box-shadow: 0 26px 60px rgba(18, 45, 87, 0.2);
}

.workflow-section .section-heading,
.workflow-section h2 {
  color: white;
}

.workflow-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  list-style: none;
}

.workflow-item {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.08);
  padding: 18px;
}

.step-index {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--color-gold);
  color: var(--color-navy-dark);
  font: 800 13px var(--font-ui);
}

.workflow-item h3 {
  margin-top: 14px;
  color: white;
}

.workflow-item p {
  color: rgba(255, 255, 255, 0.72);
}

.reference-section {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 18px;
}

.reference-panel {
  border-radius: 26px;
  padding: 28px;
}

.reference-panel h2,
.reference-panel p {
  margin-top: 12px;
}

.law-list {
  display: grid;
  gap: 11px;
  margin-top: 18px;
  padding-left: 18px;
  color: var(--color-text-regulation);
  font: 13px/1.65 var(--font-ui);
}

.domain-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.domain-card {
  min-height: 156px;
}

.security-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.security-card {
  display: flex;
  gap: 14px;
}

.security-card > span {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--color-gold-soft);
  color: var(--color-gold-ink);
  font-size: 12px;
}

.security-card h3 {
  margin-top: 0;
}

.faq-list {
  display: grid;
  gap: 10px;
}

.faq-item {
  border-radius: 18px;
  padding: 0;
}

.faq-item summary {
  cursor: pointer;
  color: var(--color-text-strong);
  font: 800 14px var(--font-ui);
  padding: 18px 20px;
}

.faq-item p {
  border-top: 1px solid #edf2f8;
  padding: 0 20px 18px;
}

/* === Workspace section === */
.workspace-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.workspace-card {
  display: flex;
  gap: 18px;
  align-items: flex-start;
  border: 1px solid rgba(26, 58, 107, 0.14);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 34px rgba(12, 43, 84, 0.06);
  padding: 22px;
  text-decoration: none;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}

.workspace-card:hover {
  transform: translateY(-2px);
  border-color: rgba(26, 58, 107, 0.28);
  box-shadow: 0 18px 40px rgba(12, 43, 84, 0.1);
}

.workspace-card.disabled {
  opacity: 0.45;
  cursor: default;
  pointer-events: none;
}

.workspace-code {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(201, 168, 76, 0.4);
  border-radius: 50%;
  background: #fff8df;
  color: var(--color-navy-dark);
  font: 800 10px var(--font-ui);
  letter-spacing: 0.3px;
}

.workspace-kicker {
  display: block;
  color: var(--color-gold-ink);
  font: 800 10px var(--font-ui);
  letter-spacing: 0.8px;
  margin-bottom: 5px;
}

.workspace-card h3 {
  margin-top: 0;
}

.workspace-card p {
  margin-top: 6px;
  color: var(--color-text-panel-muted);
  font: 13px/1.6 var(--font-ui);
}

/* === Governance / Batasan section === */
.governance-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.governance-card {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  border: 1px solid rgba(26, 58, 107, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 24px rgba(12, 43, 84, 0.05);
  padding: 20px;
}

.governance-code {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(26, 58, 107, 0.2);
  border-radius: 4px;
  background: var(--color-surface-page);
  color: var(--color-navy);
  font: 700 10px var(--font-ui);
  letter-spacing: 0.5px;
}

.governance-card h3 {
  margin-top: 0;
}

.governance-card p {
  margin-top: 6px;
  color: var(--color-text-panel-muted);
  font: 13px/1.6 var(--font-ui);
}

.final-cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-radius: 28px;
  padding: 30px;
  background: linear-gradient(135deg, #ffffff, #eef5ff);
}

.final-cta h2 {
  margin-top: 10px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}

@media (max-width: 1080px) {
  .anchor-nav {
    overflow-x: auto;
    justify-content: flex-start;
  }

  .hero-section,
  .reference-section {
    grid-template-columns: 1fr;
  }

  .workflow-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .workspace-grid,
  .governance-grid {
    grid-template-columns: 1fr;
  }

  .domain-grid {
    grid-template-columns: 1fr;
  }

  .final-cta {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .anchor-nav {
    top: 0;
    padding: 8px 12px;
  }

  .landing-shell {
    padding: 18px 12px 36px;
  }

  .hero-section,
  .workflow-section,
  .reference-panel,
  .final-cta {
    border-radius: 22px;
    padding: 22px;
  }

  .hero-section {
    gap: 22px;
  }

  .preview-question,
  .preview-answer {
    max-width: 100%;
  }

  .stats-grid,
  .workflow-list {
    grid-template-columns: 1fr;
  }

  .stat-card + .stat-card {
    border-top: 1px solid #edf2f8;
    border-left: 0;
  }

  .primary-action,
  .secondary-action {
    width: 100%;
  }
}
</style>
