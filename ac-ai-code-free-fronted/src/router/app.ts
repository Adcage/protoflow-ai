import type { RouteRecordRaw } from 'vue-router'
import AppGeneratorPage from '@/pages/app/AppGeneratorPage.vue'
import AppEditPage from '@/pages/app/AppEditPage.vue'
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
      hideInMenu: true
    }
  },
  {
    path: '/app/edit/:id',
    name: 'app_edit',
    component: AppEditPage,
    meta: {
      hideInMenu: true
    }
  }
] as Array<RouteRecordRaw>
