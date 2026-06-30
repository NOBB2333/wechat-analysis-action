<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <router-link to="/" class="text-slate-400 hover:text-slate-600 transition-colors">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </router-link>
        <h1 class="text-xl font-semibold text-slate-900">{{ sessionId }} - 数据统计</h1>
      </div>
      <div class="flex items-center gap-2">
        <input v-model="startDate" type="date" class="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500" />
        <span class="text-slate-400">~</span>
        <input v-model="endDate" type="date" class="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500" />
        <button @click="loadStats" class="text-sm bg-primary-600 text-white px-4 py-1.5 rounded-lg hover:bg-primary-700 transition-colors">刷新</button>
        <router-link :to="{ name: 'chat', params: { platform, sessionId } }" class="text-sm bg-slate-100 text-slate-700 px-4 py-1.5 rounded-lg hover:bg-slate-200 transition-colors">聊天</router-link>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
    </div>

    <template v-else-if="stats">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-white rounded-xl border border-slate-200 p-4">
          <div class="text-sm text-slate-500 mb-1">总消息数</div>
          <div class="text-2xl font-bold text-slate-900">{{ stats.total_messages.toLocaleString() }}</div>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 p-4">
          <div class="text-sm text-slate-500 mb-1">参与人数</div>
          <div class="text-2xl font-bold text-slate-900">{{ stats.unique_senders }}</div>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 p-4">
          <div class="text-sm text-slate-500 mb-1">时间范围</div>
          <div class="text-sm font-medium text-slate-900">{{ stats.time_range?.start?.split('T')[0] || '-' }}</div>
          <div class="text-xs text-slate-400">至 {{ stats.time_range?.end?.split('T')[0] || '-' }}</div>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 p-4">
          <div class="text-sm text-slate-500 mb-1">日均消息</div>
          <div class="text-2xl font-bold text-slate-900">{{ dailyAvg }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 class="text-sm font-semibold text-slate-900 mb-4">消息数量趋势</h3>
          <div ref="timelineChart" class="h-64"></div>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 class="text-sm font-semibold text-slate-900 mb-4">活跃时段分布</h3>
          <div ref="hourlyChart" class="h-64"></div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 class="text-sm font-semibold text-slate-900 mb-4">发言排行</h3>
          <div class="space-y-3">
            <div v-for="(item, i) in stats.top_senders?.slice(0, 10)" :key="item.name" class="flex items-center gap-3">
              <span :class="[
                'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0',
                i < 3 ? 'bg-gradient-to-br from-amber-400 to-orange-500' : 'bg-slate-300'
              ]">{{ i + 1 }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium text-slate-900 truncate">{{ item.name }}</span>
                  <span class="text-xs text-slate-500 shrink-0">{{ item.count }} 条</span>
                </div>
                <div class="mt-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    class="h-full bg-gradient-to-r from-primary-400 to-primary-600 rounded-full"
                    :style="{ width: (item.count / maxSenderCount * 100) + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-2xl border border-slate-200 p-5">
          <h3 class="text-sm font-semibold text-slate-900 mb-4">消息类型分布</h3>
          <div ref="typeChart" class="h-64"></div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { chatApi, type Stats } from '../api'
import Highcharts from 'highcharts'
import HighchartsVue from 'highcharts-vue'

const route = useRoute()
const platform = route.params.platform as string
const sessionId = route.params.sessionId as string

const stats = ref<Stats | null>(null)
const loading = ref(true)
const startDate = ref('')
const endDate = ref('')

const timelineChart = ref<HTMLElement>()
const hourlyChart = ref<HTMLElement>()
const typeChart = ref<HTMLElement>()

const dailyAvg = computed(() => {
  if (!stats.value?.activity_timeline?.length) return '0'
  const total = stats.value.total_messages
  const days = stats.value.activity_timeline.length
  return Math.round(total / days).toString()
})

const maxSenderCount = computed(() => {
  if (!stats.value?.top_senders?.length) return 1
  return stats.value.top_senders[0].count
})

onMounted(() => loadStats())

async function loadStats() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (startDate.value) params.start_date = startDate.value
    if (endDate.value) params.end_date = endDate.value
    const { data } = await chatApi.getStats(platform, sessionId, params)
    stats.value = data
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error('Failed to load stats:', e)
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (!stats.value) return

  // Timeline chart
  if (timelineChart.value && stats.value.activity_timeline?.length) {
    Highcharts.chart(timelineChart.value, {
      chart: { type: 'areaspline', height: 256 },
      title: { text: '' },
      xAxis: {
        categories: stats.value.activity_timeline.map(d => d.date.slice(5)),
        labels: { style: { fontSize: '11px', color: '#64748b' } },
      },
      yAxis: { title: { text: '' }, labels: { style: { fontSize: '11px', color: '#64748b' } } },
      series: [{
        name: '消息数',
        data: stats.value.activity_timeline.map(d => d.count),
        color: '#3b82f6',
        fillColor: {
          linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
          stops: [[0, 'rgba(59,130,246,0.3)'], [1, 'rgba(59,130,246,0.02)']],
        },
      }],
      legend: { enabled: false },
      credits: { enabled: false },
    })
  }

  // Hourly chart
  if (hourlyChart.value && stats.value.hourly_distribution) {
    const hours = Array.from({ length: 24 }, (_, i) => i.toString())
    const data = hours.map(h => stats.value!.hourly_distribution[h] || 0)
    Highcharts.chart(hourlyChart.value, {
      chart: { type: 'column', height: 256 },
      title: { text: '' },
      xAxis: {
        categories: hours.map(h => h.padStart(2, '0') + ':00'),
        labels: { style: { fontSize: '10px', color: '#64748b' }, step: 3 },
      },
      yAxis: { title: { text: '' }, labels: { style: { fontSize: '11px', color: '#64748b' } } },
      series: [{
        name: '消息数',
        data,
        color: '#8b5cf6',
        borderRadius: 4,
      }],
      legend: { enabled: false },
      credits: { enabled: false },
    })
  }

  // Type chart
  if (typeChart.value && stats.value.msg_type_distribution) {
    const typeData = Object.entries(stats.value.msg_type_distribution).map(([k, v]) => ({
      name: k === '1' ? '文本' : k === '3' ? '图片' : k === '34' ? '语音' : k === '43' ? '视频' : `类型${k}`,
      y: v,
    }))
    Highcharts.chart(typeChart.value, {
      chart: { type: 'pie', height: 256 },
      title: { text: '' },
      series: [{
        name: '消息数',
        data: typeData,
        innerSize: '50%',
      }],
      credits: { enabled: false },
    })
  }
}
</script>
