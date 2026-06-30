import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export interface Platform {
  name: string
  display_name: string
  detected: boolean
  data_dir: string
}

export interface Session {
  username: string
  display_name: string
  session_type: number
  summary: string
  last_time: string
  unread: number
  msg_count: number
}

export interface Message {
  time_text: string
  sender: string
  sender_id: string
  text: string
  msg_type: number
  msg_type_label: string
  hour?: number
}

export interface Contact {
  user_id: string
  nickname: string
  remark: string
}

export interface Stats {
  total_messages: number
  unique_senders: number
  sender_stats: Record<string, number>
  hourly_distribution: Record<string, number>
  msg_type_distribution: Record<string, number>
  time_range: { start?: string; end?: string }
  top_senders: { name: string; count: number }[]
  activity_timeline: { date: string; count: number }[]
}

export const chatApi = {
  getPlatforms: () => api.get<Platform[]>('/platforms'),
  getSessions: (platform: string, limit = 100) =>
    api.get<Session[]>(`/${platform}/sessions`, { params: { limit } }),
  getMessages: (platform: string, sessionId: string, params?: {
    start_date?: string
    end_date?: string
    limit?: number
  }) => api.get<Message[]>(`/${platform}/messages/${encodeURIComponent(sessionId)}`, { params }),
  getContacts: (platform: string) =>
    api.get<Contact[]>(`/${platform}/contacts`),
  getStats: (platform: string, sessionId: string, params?: {
    start_date?: string
    end_date?: string
  }) => api.get<Stats>(`/${platform}/stats/${encodeURIComponent(sessionId)}`, { params }),
  getGroups: (platform: string) =>
    api.get<Session[]>(`/${platform}/groups`),
}

export default api
