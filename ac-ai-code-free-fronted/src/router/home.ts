import type { RouteRecordRaw } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'

export default [
  {
    path: '/',
    name: '主页',
    component: HomePage,
  },
] as Array<RouteRecordRaw>
