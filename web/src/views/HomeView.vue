<template>
  <div>
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-slate-900 mb-2">选择平台</h1>
      <p class="text-slate-500">选择要分析的聊天平台，查看聊天记录和统计数据</p>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div
        v-for="platform in platforms"
        :key="platform.name"
        class="group relative bg-white rounded-2xl border border-slate-200 p-6 hover:shadow-xl hover:shadow-primary-500/10 hover:border-primary-200 transition-all duration-300 cursor-pointer"
        @click="selectPlatform(platform)"
      >
        <div class="flex items-center gap-4 mb-4">
          <div :class="[
            'w-14 h-14 rounded-2xl flex items-center justify-center text-2xl',
            platform.detected ? 'bg-primary-50' : 'bg-slate-100'
          ]">
            {{ platformIcons[platform.name] || '💬' }}
          </div>
          <div>
            <h3 class="text-lg font-semibold text-slate-900">{{ platform.display_name }}</h3>
            <span :class="[
              'inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full',
              platform.detected
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-slate-100 text-slate-500'
            ]">
              <span :class="['w-1.5 h-1.5 rounded-full', platform.detected ? 'bg-emerald-500' : 'bg-slate-400']"></span>
              {{ platform.detected ? '已检测到' : '未检测到' }}
            </span>
          </div>
        </div>

        <p v-if="platform.detected" class="text-sm text-slate-500 mb-4 line-clamp-2">
          数据目录: {{ platform.data_dir.split('\\').slice(-2).join('\\') }}
        </p>
        <p v-else class="text-sm text-slate-400 mb-4">
          未检测到本地数据，请先安装并登录
        </p>

        <div v-if="platform.detected" class="flex items-center gap-2 text-primary-600 text-sm font-medium group-hover:gap-3 transition-all">
          查看会话
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </div>

    <div v-if="selectedPlatform" class="mt-8">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-semibold text-slate-900">
          {{ selectedPlatform.display_name }} - 会话列表
        </h2>
        <button @click="selectedPlatform = null" class="text-sm text-slate-500 hover:text-slate-700">
          返回
        </button>
      </div>

      <div v-if="sessionsLoading" class="flex items-center justify-center py-10">
        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
      </div>

      <div v-else class="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div class="divide-y divide-slate-100">
          <div
            v-for="session in sessions"
            :key="session.username"
            class="flex items-center gap-4 px-6 py-4 hover:bg-slate-50 cursor-pointer transition-colors"
            @click="openChat(session)"
          >
            <div class="w-10 h-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white text-sm font-medium shrink-0">
              {{ (session.display_name || session.username).charAt(0) }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-medium text-slate-900 truncate">{{ session.display_name || session.username }}</span>
                <span v-if="session.msg_count" class="text-xs text-slate-400">{{ session.msg_count }} 条</span>
              </div>
              <p class="text-sm text-slate-500 truncate mt-0.5">{{ session.summary || session.username }}</p>
            </div>
            <div class="text-right shrink-0">
              <span class="text-xs text-slate-400">{{ session.last_time }}</span>
              <div v-if="session.unread" class="mt-1">
                <span class="inline-flex items-center justify-center w-5 h-5 text-xs font-medium text-white bg-red-500 rounded-full">
                  {{ session.unread > 99 ? '99+' : session.unread }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!sessions.length" class="py-10 text-center text-slate-400">
          暂无会话数据
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { chatApi, type Platform, type Session } from '../api'

const router = useRouter()
const platforms = ref<Platform[]>([])
const sessions = ref<Session[]>([])
const selectedPlatform = ref<Platform | null>(null)
const loading = ref(true)
const sessionsLoading = ref(false)

const platformIcons: Record<string, string> = {
  wechat: '💚',
  wecom: '💙',
  dingtalk: '🔵',
  feishu: '🐦',
}

onMounted(async () => {
  try {
    const { data } = await chatApi.getPlatforms()
    platforms.value = data
  } catch (e) {
    console.error('Failed to load platforms:', e)
  } finally {
    loading.value = false
  }
})

async function selectPlatform(platform: Platform) {
  if (!platform.detected) return
  selectedPlatform.value = platform
  sessionsLoading.value = true
  try {
    const { data } = await chatApi.getSessions(platform.name)
    sessions.value = data
  } catch (e) {
    console.error('Failed to load sessions:', e)
  } finally {
    sessionsLoading.value = false
  }
}

function openChat(session: Session) {
  if (!selectedPlatform.value) return
  router.push({
    name: 'chat',
    params: {
      platform: selectedPlatform.value.name,
      sessionId: session.username,
    },
  })
}
</script>
