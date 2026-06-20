import type { RouteRecordRaw } from 'vue-router'

export default {
  path: '/',
  component: () => import('@/layouts/BasicLayout.vue'),
  children: [
    {
      path: '',
      name: '主页',
      component: () => import('@/pages/HomePage.vue'),
    },
    {
      path: 'app/my',
      name: 'my_apps',
      component: () => import('@/pages/app/MyAppListPage.vue'),
    },
    {
      path: 'app/generate/:id',
      name: 'app_generate',
      component: () => import('@/pages/app/AppGeneratorPage.vue'),
      meta: {
        hideInMenu: true,
      },
    },
    {
      path: 'app/edit/:id',
      redirect: '/app/my',
    },
    {
      path: 'user/register',
      name: '注册',
      component: () => import('@/pages/user/UserRegisterPage.vue'),
    },
    {
      path: 'user/login',
      name: '登录',
      component: () => import('@/pages/user/UserLoginPage.vue'),
    },
    {
      path: 'user/profile',
      name: '个人中心',
      component: () => import('@/pages/user/UserProfilePage.vue'),
    },
    {
      path: 'user/usage',
      name: '用量统计',
      component: () => import('@/pages/user/UsageStatsPage.vue'),
    },
    {
      path: 'model/config',
      name: 'model_config',
      component: () => import('@/pages/model/ModelConfigPage.vue'),
      meta: {
        name: '模型配置',
      },
    },
  ],
} as RouteRecordRaw
