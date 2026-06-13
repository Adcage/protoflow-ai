import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'

// 自动导入当前目录下所有路由文件
const modules = import.meta.glob('./*.ts', { eager: true })

// 收集所有路由
const routeModules: RouteRecordRaw[] = []
Object.entries(modules).forEach(([key, value]) => {
  // 排除当前文件自身
  if (key !== './index.ts') {
    // 修复：添加类型断言
    const moduleRoutes = (value as { default?: RouteRecordRaw | RouteRecordRaw[] }).default || value
    if (Array.isArray(moduleRoutes)) {
      routeModules.push(...moduleRoutes)
    } else {
      routeModules.push(moduleRoutes as RouteRecordRaw)
    }
  }
})
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: routeModules,
})

export default router
