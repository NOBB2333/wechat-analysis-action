<template>
  <div class="flex flex-col h-[calc(100vh-5rem)]">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <router-link to="/" class="text-slate-400 hover:text-slate-600 transition-colors">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </router-link>
        <h1 class="text-xl font-semibold text-slate-900">{{ sessionId }}</h1>
      </div>
      <div class="flex items-center gap-2">
        <input
          v-model="startDate"
          type="date"
          class="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
        />
        <span class="text-slate-400">~</span>
        <input
          v-model="endDate"
          type="date"
          class="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
        />
        <button
          @click="loadMessages"
          class="text-sm bg-primary-600 text-white px-4 py-1.5 rounded-lg hover:bg-primary-700 transition-colors"
        >
          查询
        </button>
        <router-link
          :to="{ name: 'stats', params: { platform, sessionId } }"
          class="text-sm bg-slate-100 text-slate-700 px-4 py-1.5 rounded-lg hover:bg-slate-200 transition-colors"
        >
          统计
        </router-link>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
      <div v-if="loading" class="flex items-center justify-center py-10">
        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
      </div>

      <div v-else-if="!messages.length" class="flex items-center justify-center py-10 text-slate-400">
        暂无消息
      </div>

      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="flex gap-3 group"
      >
        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center text-xs font-medium text-slate-600 shrink-0 mt-0.5">
          {{ (msg.sender || '?').charAt(0) }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-baseline gap-2">
            <span class="text-sm font-medium text-slate-900">{{ msg.sender }}</span>
            <span class="text-xs text-slate-400">{{ msg.time_text }}</span>
          </div>
          <p class="text-sm text-slate-700 mt-0.5 whitespace-pre-wrap break-words">{{ msg.text }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { chatApi, type Message } from '../api'

const route = useRoute()
const platform = route.params.platform as string
const sessionId = route.params.sessionId as string

const messages = ref<Message[]>([])
const loading = ref(true)
const startDate = ref('')
const endDate = ref('')

onMounted(() => loadMessages())

async function loadMessages() {
  loading.value = true
  try {
    const params: Record<string, any> = { limit: 1000 }
    if (startDate.value) params.start_date = startDate.value
    if (endDate.value) params.end_date = endDate.value
    const { data } = await chatApi.getMessages(platform, sessionId, params)
    messages.value = data.reverse()
  } catch (e) {
    console.error('Failed to load messages:', e)
  } finally {
    loading.value = false
  }
}
</script>
