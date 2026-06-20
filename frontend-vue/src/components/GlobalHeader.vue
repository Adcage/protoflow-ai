<template>
  <a-layout-header class="global-header">
    <div class="header-content">
      <router-link to="/" class="logo-link">
        <img alt="AC AI Code" class="logo" src="/logo.png" />
        <span class="site-title">AC AI Code</span>
      </router-link>

      <nav class="header-nav">
        <router-link
          v-for="item in visibleMenuItems"
          :key="item.key"
          :to="item.key"
          class="nav-link"
          :exact-active-class="item.key === '/' ? 'nav-link-active' : undefined"
          :active-class="item.key !== '/' ? 'nav-link-active' : undefined"
        >
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="header-right">
        <div v-if="loginUserStore.loginUser.id" class="user-area">
          <a-dropdown>
            <div class="user-trigger">
              <UserAvatar :user="loginUserStore.loginUser" :size="32" />
              <span class="user-name">{{ loginUserStore?.loginUser?.userName }}</span>
            </div>
            <template #overlay>
              <a-menu>
                <a-menu-item v-if="loginUserStore.loginUser.userRole === 'admin'" key="admin" @click="router.push('/admin')">
                  <Settings :size="16" style="margin-right: 8px" />
                  管理后台
                </a-menu-item>
                <a-menu-item key="profile" @click="router.push('/user/profile')">
                  <User :size="16" style="margin-right: 8px" />
                  个人中心
                </a-menu-item>
                <a-menu-item key="usage" @click="router.push('/user/usage')">
                  <BarChart3 :size="16" style="margin-right: 8px" />
                  用量统计
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
        <a-button v-else type="primary" @click="router.push('/user/login')" class="login-btn"> 登录 </a-button>
      </div>

      <button class="mobile-menu-btn" @click="mobileMenuOpen = !mobileMenuOpen">
        <Menu :size="24" />
      </button>
    </div>

    <div v-if="mobileMenuOpen" class="mobile-nav">
      <router-link
        v-for="item in visibleMenuItems"
        :key="item.key"
        :to="item.key"
        class="mobile-nav-link"
        @click="mobileMenuOpen = false"
      >
        <component :is="item.icon" :size="18" />
        <span>{{ item.label }}</span>
      </router-link>
    </div>
  </a-layout-header>
</template>

<script lang="ts" setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useLoginUserStore } from '@/stores/LoginUser.ts'
import { Home, FolderOpen, Settings, User, BarChart3, LogOut, Menu } from '@lucide/vue'
import UserAvatar from '@/components/UserAvatar.vue'

const router = useRouter()
const mobileMenuOpen = ref(false)

const loginUserStore = useLoginUserStore()
loginUserStore.fetchLoginUser()

const menuItems = [
  { key: '/', icon: Home, label: '主页' },
  { key: '/app/my', icon: FolderOpen, label: '我的作品' },
]

const visibleMenuItems = computed(() => menuItems)

const handleLogout = () => {
  loginUserStore.logout()
}
</script>

<style scoped>
.global-header {
  background: var(--color-surface);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border);
  padding: 0;
  position: sticky;
  top: 0;
  z-index: 1000;
  height: 64px;
  line-height: 64px;
}

.header-content {
  display: flex;
  align-items: center;
  padding: 0 var(--space-lg);
  height: 64px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.logo-link {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  text-decoration: none;
  flex-shrink: 0;
}

.logo {
  height: 32px;
  width: auto;
}

.site-title {
  font-family: var(--font-heading);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.5px;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin-left: var(--space-2xl);
  flex: 1;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px var(--space-md);
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  text-decoration: none;
  line-height: 1;
  cursor: pointer;
}

.nav-link:hover {
  color: var(--color-text);
  background: var(--color-surface-elevated);
}

.nav-link-active {
  color: var(--color-cta);
  background: rgba(34, 197, 94, 0.1);
}

.nav-link-active:hover {
  color: var(--color-cta);
  background: rgba(34, 197, 94, 0.15);
}

.header-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  margin-left: auto;
}

.user-area {
  cursor: pointer;
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

.login-btn {
  font-weight: 600;
}

.mobile-menu-btn {
  display: none;
  background: none;
  border: none;
  color: var(--color-text);
  cursor: pointer;
  padding: var(--space-sm);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
  margin-left: auto;
}

.mobile-menu-btn:hover {
  background: var(--color-surface-elevated);
}

.mobile-nav {
  display: none;
  flex-direction: column;
  padding: var(--space-sm) var(--space-lg);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.mobile-nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-sm);
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: all var(--transition-fast);
  cursor: pointer;
}

.mobile-nav-link:hover {
  color: var(--color-text);
  background: var(--color-surface-elevated);
}

@media (max-width: 768px) {
  .header-nav {
    display: none;
  }

  .user-name {
    display: none;
  }

  .mobile-menu-btn {
    display: flex;
    align-items: center;
  }

  .mobile-nav {
    display: flex;
  }

  .site-title {
    display: none;
  }
}
</style>
