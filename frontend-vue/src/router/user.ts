import type { RouteRecordRaw } from 'vue-router'
import UserRegisterPage from '@/pages/user/UserRegisterPage.vue'
import UserLoginPage from '@/pages/user/UserLoginPage.vue'
import UserProfilePage from '@/pages/user/UserProfilePage.vue'
import UsageStatsPage from '@/pages/user/UsageStatsPage.vue'

export default [
  {
    path: '/user/register',
    name: '注册',
    component: UserRegisterPage,
  },
  {
    path: '/user/login',
    name: '登录',
    component: UserLoginPage,
  },
  {
    path: '/user/profile',
    name: '个人中心',
    component: UserProfilePage,
  },
  {
    path: '/user/usage',
    name: '用量统计',
    component: UsageStatsPage,
  },
] as Array<RouteRecordRaw>
