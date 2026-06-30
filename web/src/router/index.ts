import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
    },
    {
      path: '/chat/:platform/:sessionId',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
    },
    {
      path: '/stats/:platform/:sessionId',
      name: 'stats',
      component: () => import('../views/StatsView.vue'),
    },
  ],
})

export default router
