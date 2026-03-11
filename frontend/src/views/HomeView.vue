<template>
  <div class="home-view px-4 py-8">
    <div class="text-center mb-8">
      <h1 class="text-4xl font-bold text-gray-900 mb-4">
        SPBE RAG Assistant
      </h1>
      <p class="text-xl text-gray-600 mb-2">
        Sistem Retrieval-Augmented Generation untuk Peraturan SPBE dan Audit BSSN
      </p>
      <p class="text-sm text-gray-500">
        Powered by AI - Qwen 2.5 7B - Hybrid Search - Qdrant
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
      <div class="card bg-white p-6 rounded-lg shadow hover:shadow-lg transition cursor-pointer" @click="$router.push('/')">
        <h2 class="text-2xl font-semibold text-gray-900 mb-2">Chat</h2>
        <p class="text-gray-600">
          Tanyakan pertanyaan tentang peraturan SPBE dan hasil audit keamanan BSSN
        </p>
      </div>

      <div class="card bg-white p-6 rounded-lg shadow hover:shadow-lg transition cursor-pointer" @click="$router.push('/documents')">
        <h2 class="text-2xl font-semibold text-gray-900 mb-2">Documents</h2>
        <p class="text-gray-600">
          Kelola dokumen peraturan dan audit yang digunakan oleh sistem
        </p>
      </div>
    </div>

    <div class="mt-12 max-w-4xl mx-auto">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Status Sistem</h3>
      <div class="bg-white p-4 rounded-lg shadow">
        <div v-if="health" class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-600">Status:</span>
            <span :class="health.status === 'ready' ? 'text-green-600' : 'text-yellow-600'" class="font-semibold">
              {{ health.status }}
            </span>
          </div>
        </div>
        <div v-else-if="loading" class="text-gray-500">Loading...</div>
        <div v-else class="text-red-500">Server tidak tersedia</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const health = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const response = await fetch(`${API_URL}/api/health`)
    health.value = await response.json()
  } catch (error) {
    console.error('Health check failed:', error)
  } finally {
    loading.value = false
  }
})
</script>
