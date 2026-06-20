<template>
  <div class="login-page">
    <div class="brand-side">
      <div class="brand-content">
        <div class="brand-logo">
          <img alt="AC AI Code" src="/logo.png" class="logo-img" />
          <span class="brand-name">AC AI Code</span>
        </div>
        <p class="brand-tagline">AI 驱动的代码生成平台</p>
        <div class="brand-features">
          <div class="feature-item">
            <Sparkles :size="20" class="feature-icon" />
            <div>
              <div class="feature-title">智能生成</div>
              <div class="feature-desc">一句话创建应用</div>
            </div>
          </div>
          <div class="feature-item">
            <Zap :size="20" class="feature-icon" />
            <div>
              <div class="feature-title">实时预览</div>
              <div class="feature-desc">边生成边查看</div>
            </div>
          </div>
          <div class="feature-item">
            <Rocket :size="20" class="feature-icon" />
            <div>
              <div class="feature-title">一键部署</div>
              <div class="feature-desc">即刻发布上线</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="form-side">
      <div class="form-card">
        <h1 class="form-title">登录</h1>
        <p class="form-subtitle">欢迎回来，请登录你的账号</p>

        <a-form
          :model="formState"
          autocomplete="off"
          layout="vertical"
          @finish="handleSubmit"
          @finishFailed="onFinishFailed"
        >
          <a-form-item
            label="账号"
            :rules="[
              { required: true, message: '请输入账号' },
              { min: 2, message: '长度不能小于2位' },
              { max: 200, message: '账号长度过长' },
            ]"
            name="userAccount"
          >
            <a-input v-model:value="formState.userAccount" placeholder="请输入账号" size="large" />
          </a-form-item>

          <a-form-item
            label="密码"
            :rules="[
              { required: true, message: '请输入密码' },
              { min: 8, message: '长度不能小于8位' },
              { max: 500, message: '长度过长' },
            ]"
            name="userPassword"
          >
            <a-input-password v-model:value="formState.userPassword" placeholder="请输入密码" size="large" />
          </a-form-item>

          <a-form-item>
            <button class="cta-btn" type="submit">登录</button>
          </a-form-item>
        </a-form>

        <div class="switch-link">
          没有账号？
          <RouterLink to="/user/register">点击注册</RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { reactive } from 'vue'
import { userLogin } from '@/api/userController.ts'
import { useLoginUserStore } from '@/stores/LoginUser.ts'
import { message } from 'ant-design-vue'
import router from '@/router'
import { useRoute } from 'vue-router'
import { Sparkles, Zap, Rocket } from '@lucide/vue'

const formState = reactive<API.UserLoginRequest>({
  userAccount: '',
  userPassword: '',
})
const LoginUserStore = useLoginUserStore()
const route = useRoute()

const handleSubmit = async (values: API.UserLoginRequest) => {
  const res = await userLogin(values)
  if (res.data.code === 0 && res.data.data) {
    LoginUserStore.setLoginUser(res.data.data)
    message.success('登录成功')
    const redirect = route.query.redirect as string
    if (redirect) {
      await router.replace(redirect)
    } else if (res.data.data.userRole === 'admin') {
      await router.replace('/admin')
    } else {
      await router.replace('/')
    }
  } else {
    message.error(res.data.message || '登录失败')
  }
}

const onFinishFailed = (errorInfo: unknown) => {
  console.log('Failed:', errorInfo)
}
</script>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
  background: var(--color-background);
}

.brand-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-background) 0%, var(--color-surface) 100%);
  padding: var(--space-3xl);
  position: relative;
  overflow: hidden;
}

.brand-side::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at 30% 50%, rgba(34, 197, 94, 0.06) 0%, transparent 50%);
  pointer-events: none;
}

.brand-content {
  position: relative;
  z-index: 1;
  max-width: 400px;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.logo-img {
  height: 48px;
  width: auto;
}

.brand-name {
  font-family: var(--font-heading);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -1px;
}

.brand-tagline {
  font-size: 18px;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3xl);
  line-height: 1.6;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.feature-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all var(--transition-normal);
}

.feature-item:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(34, 197, 94, 0.2);
}

.feature-icon {
  color: var(--color-cta);
  flex-shrink: 0;
}

.feature-title {
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 15px;
  color: var(--color-text);
}

.feature-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.form-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-2xl);
}

.form-card {
  width: 100%;
  max-width: 420px;
  background: var(--color-surface);
  border-radius: var(--radius-xl);
  padding: var(--space-2xl);
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--color-border);
}

.form-title {
  font-family: var(--font-heading);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--space-xs);
}

.form-subtitle {
  font-size: 14px;
  color: var(--color-text-muted);
  margin-bottom: var(--space-xl);
}

.cta-btn {
  width: 100%;
  padding: 12px 24px;
  background: var(--color-cta);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: 16px;
  font-weight: 600;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.cta-btn:hover {
  background: var(--color-cta-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
}

.cta-btn:active {
  transform: translateY(0);
}

.switch-link {
  text-align: center;
  font-size: 14px;
  color: var(--color-text-muted);
  margin-top: var(--space-lg);
}

.switch-link a {
  color: var(--color-cta);
  font-weight: 500;
  cursor: pointer;
}

.switch-link a:hover {
  color: var(--color-cta-hover);
}

@media (max-width: 768px) {
  .login-page {
    flex-direction: column;
  }

  .brand-side {
    padding: var(--space-xl) var(--space-md);
    min-height: auto;
  }

  .brand-logo {
    justify-content: center;
  }

  .brand-tagline {
    text-align: center;
    margin-bottom: var(--space-xl);
  }

  .brand-features {
    display: none;
  }

  .form-side {
    padding: var(--space-lg) var(--space-md);
  }

  .form-card {
    padding: var(--space-xl);
  }
}
</style>
