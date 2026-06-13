import type { RouteRecordRaw } from 'vue-router'
import AppGeneratorPage from '@/pages/app/AppGeneratorPage.vue'
import MyAppListPage from '@/pages/app/MyAppListPage.vue'

export default [
  {
    path: '/app/my',
    name: 'my_apps',
    component: MyAppListPage,
  },
  {
    path: '/app/generate/:id',
    name: 'app_generate',
    component: AppGeneratorPage,
    meta: {
      hideInMenu: true,
    },
  },
  {
    path: '/app/edit/:id',
    redirect: '/app/my',
  },
] as Array<RouteRecordRaw>
