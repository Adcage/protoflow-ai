<template>
  <a-layout-header class="global-header">
    <div class="header-content">
      <router-link to="/" class="logo-link">
        <img alt="原象 Morpha" class="logo" src="/brand/logo-light.svg" />
        <span class="site-title">原象</span>
      </router-link>

      <nav class="header-nav">
        <router-link
          v-for="item in menuItems"
          :key="item.key"
          :to="item.key"
          class="nav-link"
          :active-class="'nav-link-active'"
        >
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="header-right">
        <nav class="header-right-nav">
          <router-link to="/pricing" class="nav-link-subtle">价格</router-link>
          <router-link to="/docs" class="nav-link-subtle">文档</router-link>
        </nav>

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
                <a-menu-item key="dashboard" @click="router.push('/user/usage')">
                  <BarChart3 :size="16" style="margin-right: 8px" />
                  仪表盘
                </a-menu-item>
                <a-menu-item key="myapps" @click="router.push('/app/my')">
                  <FolderOpen :size="16" style="margin-right: 8px" />
                  我的作品
                </a-menu-item>
                <a-menu-item key="settings" @click="router.push('/user/settings')">
                  <UserCog :size="16" style="margin-right: 8px" />
                  账号设置
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
        v-for="item in menuItems"
        :key="item.key"
        :to="item.key"
        class="mobile-nav-link"
        @click="mobileMenuOpen = false"
      >
        <component :is="item.icon" :size="18" />
        <span>{{ item.label }}</span>
      </router-link>
      <router-link to="/pricing" class="mobile-nav-link" @click="mobileMenuOpen = false">
        <span>价格</span>
      </router-link>
      <router-link to="/docs" class="mobile-nav-link" @click="mobileMenuOpen = false">
        <span>文档</span>
      </router-link>
    </div>
  </a-layout-header>
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useLoginUserStore } from '@/stores/LoginUser.ts'
import { Compass, FolderOpen, Settings, BarChart3, UserCog, LogOut, Menu } from '@lucide/vue'
import UserAvatar from '@/components/UserAvatar.vue'

const router = useRouter()
const mobileMenuOpen = ref(false)

const loginUserStore = useLoginUserStore()
loginUserStore.fetchLoginUser()

const menuItems = [
  { key: '/explore', icon: Compass, label: '探索广场' },
]

const handleLogout = () => {
  loginUserStore.logout()
}
</script>

<style scoped>
.global-header {
  background: rgba(28, 45, 61, 0.92) !important;
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--color-border-dark);
  padding: 0;
  position: sticky;
  top: 0;
  z-index: 1000;
  height: 64px;
  line-height: 64px;
  box-shadow: none !important;
}

.header-content {
  display: flex;
  align-items: center;
  padding: 0 var(--space-page-x);
  height: 64px;
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
  filter: brightness(0) invert(1);
}

.site-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-on-dark);
  letter-spacing: -0.3px;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: var(--space-xl);
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px var(--space-md);
  color: var(--color-text-on-dark-secondary);
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  text-decoration: none;
  line-height: 1;
  cursor: pointer;
  position: relative;
}

.nav-link:hover {
  color: var(--color-text-on-dark);
  background: rgba(255, 255, 255, 0.06);
}

.nav-link-active {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.05);
}

.nav-link-active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 18px;
  height: 2px;
  background: var(--color-cta);
  border-radius: 1px;
}

.nav-link-active:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.06);
}

.header-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  margin-left: auto;
  gap: var(--space-lg);
}

.header-right-nav {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.nav-link-subtle {
  color: var(--color-text-on-dark);
  font-size: 14px;
  font-weight: 400;
  opacity: 0.6;
  text-decoration: none;
  padding: 4px var(--space-sm);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.nav-link-subtle:hover {
  opacity: 0.9;
  background: rgba(255, 255, 255, 0.06);
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
  background: rgba(255, 255, 255, 0.06);
}

.user-name {
  color: var(--color-text-on-dark);
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
  color: var(--color-text-on-dark);
  cursor: pointer;
  padding: var(--space-sm);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
  margin-left: auto;
}

.mobile-menu-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.mobile-nav {
  display: none;
  flex-direction: column;
  padding: var(--space-sm) var(--space-page-x);
  background: rgba(28, 45, 61, 0.96);
  border-bottom: 1px solid var(--color-border-dark);
}

.mobile-nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-sm);
  color: var(--color-text-on-dark-secondary);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: all var(--transition-fast);
  cursor: pointer;
}

.mobile-nav-link:hover {
  color: var(--color-text-on-dark);
  background: rgba(255, 255, 255, 0.06);
}

@media (max-width: 768px) {
  .header-content {
    padding: 0 var(--space-page-x-sm);
  }

  .header-nav {
    display: none;
  }

  .header-right-nav {
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
    padding-inline: var(--space-page-x-sm);
  }

  .site-title {
    display: none;
  }
}
</style>
