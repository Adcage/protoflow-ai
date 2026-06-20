import type { RouteRecordRaw } from 'vue-router'

export default {
  path: '/admin',
  name: 'admin',
  component: () => import('@/layouts/AdminLayout.vue'),
  redirect: '/admin/test-chat',
  meta: {
    name: '管理后台',
  },
  children: [
    {
      path: 'test-chat',
      name: 'admin_test_chat',
      component: () => import('@/pages/admin/TestChatPage.vue'),
      meta: {
        name: 'AI 测试对话',
      },
    },
    {
      path: 'userManage',
      name: 'admin_user',
      component: () => import('@/pages/admin/UserManagePage.vue'),
      meta: {
        name: '用户管理',
      },
    },
    {
      path: 'appManage',
      name: 'admin_app',
      component: () => import('@/pages/admin/AppAdminPage.vue'),
      meta: {
        name: '应用管理',
      },
    },
  ],
} as RouteRecordRaw
