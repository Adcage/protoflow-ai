# Pinia 状态管理

## 定义 Store

使用 `defineStore` 定义 Store，支持 Option 和 Setup 两种风格：

```javascript
// Option 风格
import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    name: '',
    token: '',
    userInfo: null,
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
    displayName: (state) => state.userInfo?.name || '未登录',
  },
  actions: {
    async login(credentials) {
      const res = await api.login(credentials)
      this.token = res.data.token
      this.userInfo = res.data.userInfo
    },
    logout() {
      this.token = ''
      this.userInfo = null
    },
  },
})
```

```javascript
// Setup 风格（推荐）
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref('')
  const userInfo = ref(null)

  const isLoggedIn = computed(() => !!token.value)
  const displayName = computed(() => userInfo.value?.name || '未登录')

  async function login(credentials) {
    const res = await api.login(credentials)
    token.value = res.data.token
    userInfo.value = res.data.userInfo
  }

  function logout() {
    token.value = ''
    userInfo.value = null
  }

  return { token, userInfo, isLoggedIn, displayName, login, logout }
})
```

## 在组件中使用

```vue
<script setup>
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const userStore = useUserStore()

// 解构响应式数据（必须用 storeToRefs）
const { token, userInfo, isLoggedIn } = storeToRefs(userStore)

// actions 直接解构
const { login, logout } = userStore
</script>

<template>
  <div v-if="isLoggedIn">
    <p>欢迎, {{ userInfo.name }}</p>
    <button @click="logout">退出</button>
  </div>
</template>
```

## 修改 State

```javascript
// 直接修改
userStore.token = 'new-token'

// $patch 批量修改
userStore.$patch({
  token: 'new-token',
  userInfo: { name: '张三' },
})

// $patch 函数式（适合修改数组等）
userStore.$patch((state) => {
  state.userInfo.name = '李四'
})

// $reset 重置到初始状态（仅 Option 风格支持）
userStore.$reset()
```

## Store 之间互相调用

```javascript
export const useCartStore = defineStore('cart', () => {
  const items = ref([])

  function checkout() {
    // 在一个 Store 中调用另一个 Store
    const userStore = useUserStore()
    if (!userStore.isLoggedIn) {
      throw new Error('请先登录')
    }
    // ... 结算逻辑
  }

  return { items, checkout }
})
```
