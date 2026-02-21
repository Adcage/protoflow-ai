import type { RouteRecordRaw } from 'vue-router'
import UserManagePage from '@/pages/admin/UserManagePage.vue'

export default [
  {
    path: '/admin/userManage',
    name: 'admin_user',
    component: UserManagePage,
    meta: {
      name: '用户管理'
    }
  },
  {
    path: '/admin/appManage',
    name: 'admin_app',
    component: () => import('@/pages/admin/AppAdminPage.vue'),
    meta: {
      name: '应用管理'
    }
  }
] as Array<RouteRecordRaw>
