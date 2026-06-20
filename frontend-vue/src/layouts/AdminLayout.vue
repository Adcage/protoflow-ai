<template>
  <a-layout class="admin-layout">
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      :width="220"
      :collapsed-width="64"
      breakpoint="lg"
      class="admin-sider"
      :trigger="null"
    >
      <div class="sider-header">
        <router-link to="/" class="logo-link">
          <img alt="AC AI Code" class="logo" src="/logo.png" />
          <span v-if="!collapsed" class="site-title">AC AI Code</span>
        </router-link>
      </div>

      <a-menu
        mode="inline"
        :selected-keys="selectedKeys"
        class="admin-menu"
        @click="handleMenuClick"
      >
        <a-menu-item key="/admin/test-chat">
          <template #icon><MessageSquare :size="18" /></template>
          <span>AI 测试对话</span>
        </a-menu-item>
        <a-menu-item key="/admin/userManage">
          <template #icon><Users :size="18" /></template>
          <span>用户管理</span>
        </a-menu-item>
        <a-menu-item key="/admin/appManage">
          <template #icon><LayoutGrid :size="18" /></template>
          <span>应用管理</span>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>

    <!-- 右侧主区域 -->
    <a-layout class="admin-main">
      <a-layout-header class="admin-header">
        <div class="header-left">
          <button class="collapse-btn" @click="collapsed = !collapsed">
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </button>
          <span class="current-page-title">{{ currentPageTitle }}</span>
        </div>
        <div class="header-right">
          <a-dropdown>
            <div class="user-trigger">
              <UserAvatar :user="loginUserStore.loginUser" :size="32" />
              <span class="user-name">{{ loginUserStore?.loginUser?.userName }}</span>
            </div>
            <template #overlay>
              <a-menu>
                <a-menu-item key="home" @click="router.push('/')">
                  <Home :size="16" style="margin-right: 8px" />
                  返回首页
                </a-menu-item>
                <a-menu-item key="profile" @click="router.push('/user/profile')">
                  <User :size="16" style="margin-right: 8px" />
                  个人中心
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="logout" @click="handleLogout">
                  <LogOut :size="16" style="margin-right: 8px" />
                  退出登录
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="admin-content">
        <RouterView />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script lang="ts" setup>
import { computed, ref } from 'vue'
import { useRouter, useRoute, RouterView } from 'vue-router'
import { useLoginUserStore } from '@/stores/LoginUser.ts'
import { MessageSquare, Users, LayoutGrid, Home, User, LogOut } from '@lucide/vue'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons-vue'
import UserAvatar from '@/components/UserAvatar.vue'

const router = useRouter()
const route = useRoute()
const loginUserStore = useLoginUserStore()
loginUserStore.fetchLoginUser()

const collapsed = ref(false)

const menuItems = [
  { key: '/admin/test-chat', label: 'AI 测试对话' },
  { key: '/admin/userManage', label: '用户管理' },
  { key: '/admin/appManage', label: '应用管理' },
]

const selectedKeys = computed(() => [route.path])

const currentPageTitle = computed(() => {
  const item = menuItems.find((m) => m.key === route.path)
  return item?.label || (route.meta?.name as string) || '管理后台'
})

const handleMenuClick = ({ key }: { key: string }) => {
  router.push(key)
}

const handleLogout = () => {
  loginUserStore.logout()
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
  display: flex;
}

.admin-sider {
  background: var(--color-surface) !important;
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
}

.admin-sider :deep(.ant-layout-sider-children) {
  display: flex;
  flex-direction: column;
}

.sider-header {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 var(--space-md);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.logo-link {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  text-decoration: none;
  overflow: hidden;
}

.logo {
  height: 32px;
  width: auto;
  flex-shrink: 0;
}

.site-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.5px;
  white-space: nowrap;
}

.admin-menu {
  border-right: none;
  flex: 1;
  padding-top: var(--space-sm);
}

.admin-menu :deep(.ant-menu-item) {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 8px;
  border-radius: var(--radius-sm);
  height: 40px;
  line-height: 40px;
}

.admin-menu :deep(.ant-menu-item-selected) {
  background: rgba(34, 197, 94, 0.1) !important;
}

.admin-menu :deep(.ant-menu-item:hover) {
  background: var(--color-surface-elevated) !important;
}

.admin-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.admin-header {
  height: 48px;
  line-height: 48px;
  padding: 0 var(--space-lg);
  background: var(--color-surface) !important;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  font-size: 16px;
}

.collapse-btn:hover {
  background: var(--color-surface-elevated);
  color: var(--color-text);
}

.current-page-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.header-right {
  display: flex;
  align-items: center;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 4px var(--space-sm);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
  cursor: pointer;
}

.user-trigger:hover {
  background: var(--color-surface-elevated);
}

.user-name {
  color: var(--color-text);
  font-size: 14px;
  font-weight: 500;
}

.admin-content {
  flex: 1;
  background: var(--color-background) !important;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

@media (max-width: 768px) {
  .user-name {
    display: none;
  }
}
</style>
