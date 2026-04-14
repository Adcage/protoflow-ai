<template>
  <div id="appGeneratorPage">
    <div class="top-nav">
      <div class="left">
        <a-button type="text" @click="handleBack">
          <template #icon><left-outlined /></template>
        </a-button>
        <span class="app-name">{{ app?.appName || '新应用' }}</span>
      </div>
      <div class="right">
        <a-space>
          <span class="status-tag" v-if="app?.deployKey">
            <a-badge status="success" text="已部署" />
          </span>
          <a-button type="primary" :loading="deployLoading" @click="doDeploy" class="deploy-btn">
            <template #icon><cloud-upload-outlined /></template>
            部署
          </a-button>
        </a-space>
      </div>
    </div>

    <div class="main-content">
      <!-- 左侧对话区 -->
      <div class="chat-panel" :style="{ width: `${chatPanelWidth}px` }">
        <div class="session-panel">
          <div class="session-panel-header">
            <span>会话记录</span>
            <a-button type="link" size="small" :loading="sessionLoading" @click="handleCreateSession">新建会话</a-button>
          </div>
          <div class="session-list">
            <div
              v-for="(session, index) in sessions"
              :key="session.id || index"
              :class="['session-item', normalizeId(session.id) === currentSessionId ? 'active' : '']"
              @click="handleSwitchSession(session.id)"
            >
              <div class="session-title">{{ session.title || `会话 ${index + 1}` }}</div>
              <div class="session-time">{{ formatSessionTime(session.lastMessageTime) }}</div>
            </div>
          </div>
        </div>
        <div class="message-list" ref="messageListRef">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message-item', msg.role === 'user' ? 'user-msg' : 'ai-msg']"
          >
            <a-avatar :src="msg.role === 'user' ? loginUserStore.loginUser.userAvatar : '/ai-avatar.png'" />
            <div class="message-body">
              <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <div v-if="generating" class="generating-indicator">
            <loading-outlined /> AI 正在思考并生成代码...
          </div>
        </div>

        <div class="input-area">
          <div class="input-wrapper">
            <a-textarea
              v-model:value="inputText"
              placeholder="描述具体的需求，例如：修改配色为深色模式..."
              :auto-size="{ minRows: 2, maxRows: 6 }"
              @pressEnter="handleEnter"
            />
            <div class="input-footer">
              <a-space>
                <a-button type="text" size="small"><template #icon><paper-clip-outlined /></template>上传</a-button>
                <a-button type="text" size="small"><template #icon><thunderbolt-outlined /></template>优化</a-button>
              </a-space>
              <a-button 
                type="primary" 
                shape="circle" 
                size="small" 
                :disabled="generating || !inputText" 
                @click="doChat"
              >
                <template #icon><arrow-up-outlined /></template>
              </a-button>
            </div>
          </div>
        </div>
      </div>

      <div class="panel-splitter" @mousedown="startResize" />

      <!-- 右侧预览区 -->
      <div class="preview-panel">
        <div class="preview-header">
          <a-radio-group v-model:value="previewType" size="small" button-style="solid">
            <a-radio-button value="desktop">桌面端</a-radio-button>
            <a-radio-button value="mobile">移动端</a-radio-button>
          </a-radio-group>
          <a-button size="small" @click="refreshIframe">
            <template #icon><reload-outlined /></template>
          </a-button>
        </div>
        <div :class="['preview-body', previewType]">
          <iframe 
            v-if="iframeUrl" 
            :src="iframeUrl" 
            frameborder="0" 
            class="preview-iframe"
            ref="iframeRef"
          ></iframe>
          <div v-else class="preview-empty">
            <div class="empty-content">
              <div class="empty-icon">预览</div>
              <p>应用生成中，完成后将在此展示效果</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { 
  LeftOutlined, 
  CloudUploadOutlined, 
  ReloadOutlined, 
  PaperClipOutlined, 
  ThunderboltOutlined, 
  ArrowUpOutlined,
  LoadingOutlined
} from '@ant-design/icons-vue'
import { createChatSession, deployApp, getAppVoById, listChatHistoryByPage, listChatSession } from '@/api/appController'
import { useLoginUserStore } from '@/stores/LoginUser'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()
const appId = String(route.params.id ?? '')

const app = ref<API.AppVO>()
const messages = ref<{ role: 'user' | 'ai', content: string }[]>([])
const sessions = ref<API.ChatSessionVO[]>([])
const currentSessionId = ref<string>()
const inputText = ref('')
const generating = ref(false)
const deployLoading = ref(false)
const sessionLoading = ref(false)
const sessionInitializing = ref(false)
const previewType = ref('desktop')
const iframeUrl = ref('')
const messageListRef = ref<HTMLElement>()
const entryPathStorageKey = `app_generate_entry_${appId}`
const chatPanelWidth = ref(450)
const resizing = ref(false)
const resizeStartX = ref(0)
const resizeStartWidth = ref(450)

const normalizeId = (id?: string | number | null) => {
  if (id === undefined || id === null) {
    return ''
  }
  return String(id)
}

const ensureValidAppId = () => {
  if (!appId) {
    message.error('应用 ID 无效，请返回列表重新进入')
    return false
  }
  return true
}

const loadSessions = async () => {
  if (!ensureValidAppId()) {
    return
  }
  sessionLoading.value = true
  try {
    const res = await listChatSession({ appId: appId as any })
    if (res.data?.code === 0) {
      sessions.value = res.data.data || []
      return
    }
    message.error('加载会话失败，' + (res.data?.message || '请稍后重试'))
  } finally {
    sessionLoading.value = false
  }
}

const createSession = async () => {
  if (!ensureValidAppId()) {
    return undefined
  }
  const res = await createChatSession({ appId: appId as any })
  if (res.data?.code === 0 && res.data.data) {
    const sessionId = normalizeId(res.data.data)
    await loadSessions()
    return sessionId
  }
  message.error('创建会话失败，' + (res.data?.message || '请稍后重试'))
  return undefined
}

const loadRemoteHistory = async (sessionId: string) => {
  if (!ensureValidAppId()) {
    return
  }
  const res = await listChatHistoryByPage({
    appId: appId as any,
    sessionId: sessionId as any,
    pageNum: 1,
    pageSize: 200,
  })
  if (res.data?.code === 0) {
    const historyList = res.data.data?.records || []
    messages.value = historyList.map((item) => ({
      role: item.messageType === 'user' ? 'user' : 'ai',
      content: item.message || '',
    }))
    scrollToBottom()
  }
}

/**
 * 加载应用信息
 */
const loadApp = async () => {
  if (!ensureValidAppId()) {
    return
  }
  const res = await getAppVoById({ id: appId as any })
  if (res.data?.code === 0) {
    app.value = res.data.data

    await loadSessions()
    if (sessions.value.length > 0 && sessions.value[0].id) {
      currentSessionId.value = normalizeId(sessions.value[0].id)
      await loadRemoteHistory(currentSessionId.value)
      updatePreview()
    } else {
      const newSessionId = await createSession()
      if (newSessionId) {
        currentSessionId.value = newSessionId
      }
      if (app.value?.initPrompt && currentSessionId.value) {
        messages.value.push({ role: 'user', content: app.value.initPrompt })
        startSSE(app.value.initPrompt, currentSessionId.value)
      }
    }
    return
  }
  message.error('加载应用失败，' + (res.data?.message || '请稍后重试'))
}

/**
 * SSE 对话逻辑
 */
const startSSE = (userMsg: string, sessionId: string) => {
  generating.value = true
  const aiMsgIndex = messages.value.length
  messages.value.push({ role: 'ai', content: '' })

  const baseUrl = import.meta.env.VITE_API_BASE_URL
  const eventSource = new EventSource(
    `${baseUrl}/app/chat/gen/code/stream?appId=${appId}&sessionId=${sessionId}&message=${encodeURIComponent(userMsg)}`,
    { withCredentials: true }
  )

  eventSource.addEventListener('meta', (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data)
      if (data.sessionId) {
        currentSessionId.value = normalizeId(data.sessionId)
      }
    } catch (e) {
      console.error('SSE Meta Parse Error', e)
    }
  })

  const stopGenerating = () => {
    eventSource.close()
    if (generating.value) {
      generating.value = false
      loadSessions()
      updatePreview()
    }
  }

  eventSource.onmessage = (event) => {
    const rawData = event.data
    if (rawData === '[DONE]') {
      stopGenerating()
      return
    }
    
    try {
      const data = JSON.parse(rawData)
      if (data.d === '[DONE]') {
        stopGenerating()
        return
      }
      messages.value[aiMsgIndex].content += (data.d || '')
      scrollToBottom()
    } catch {
      if (rawData.includes('[DONE]')) {
        stopGenerating()
      }
    }
  }

  eventSource.onerror = (err) => {
    console.error('SSE Error', err)
    stopGenerating()
  }
}

const ensureSessionReady = async () => {
  if (currentSessionId.value) {
    return currentSessionId.value
  }
  if (sessionInitializing.value) {
    return undefined
  }
  sessionInitializing.value = true
  try {
    const sessionId = await createSession()
    if (sessionId) {
      currentSessionId.value = sessionId
    }
    return sessionId
  } finally {
    sessionInitializing.value = false
  }
}

const doChat = async () => {
  if (generating.value || !inputText.value) return
  const sessionId = await ensureSessionReady()
  if (!sessionId) {
    message.warning('会话初始化中，请稍后再试')
    return
  }
  const msg = inputText.value
  messages.value.push({ role: 'user', content: msg })
  inputText.value = ''
  startSSE(msg, sessionId)
}

const handleEnter = (e: KeyboardEvent) => {
  if (!e.shiftKey) {
    e.preventDefault()
    doChat()
  }
}

/**
 * 更新预览
 */
const updatePreview = () => {
  const codeGenType = app.value?.codeGenType || 'REACT'
  const deployUrlPrefix = import.meta.env.VITE_APP_DEPLOY_URL_PREFIX
  iframeUrl.value = `${deployUrlPrefix}/${codeGenType}_${appId}/index.html?t=${Date.now()}`
}

const refreshIframe = () => {
  if (iframeUrl.value) {
    const url = new URL(iframeUrl.value)
    url.searchParams.set('t', Date.now().toString())
    iframeUrl.value = url.toString()
  }
}

const handleCreateSession = async () => {
  if (generating.value) {
    message.warning('正在生成代码，请稍后再新建会话')
    return
  }
  const newSessionId = await createSession()
  if (newSessionId) {
    currentSessionId.value = newSessionId
    messages.value = []
    updatePreview()
  }
}

const handleSwitchSession = async (sessionId?: string | number) => {
  const normalizedSessionId = normalizeId(sessionId)
  if (!normalizedSessionId || generating.value || normalizedSessionId === currentSessionId.value) {
    return
  }
  currentSessionId.value = normalizedSessionId
  await loadRemoteHistory(normalizedSessionId)
}

const formatSessionTime = (time?: string) => {
  if (!time) {
    return '暂无消息'
  }
  const date = new Date(time)
  if (Number.isNaN(date.getTime())) {
    return '暂无消息'
  }
  return date.toLocaleString()
}

/**
 * 部署应用
 */
const doDeploy = async () => {
  deployLoading.value = true
  try {
    const res = await deployApp({ appId: appId as any })
    if (res.data?.code === 0) {
      message.success('部署成功！地址：' + res.data.data)
      loadApp()
    } else {
      message.error('部署失败，' + res.data?.message)
    }
  } finally {
    deployLoading.value = false
  }
}

const renderMarkdown = (text: string) => {
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

onMounted(() => {
  const backPath = (window.history.state?.back as string | undefined) || ''
  const forwardPath = (window.history.state?.forward as string | undefined) || ''
  if (backPath && !backPath.includes('/app/generate/')) {
    sessionStorage.setItem(entryPathStorageKey, backPath)
  }

  const navigationEntries = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]
  const navigationType = navigationEntries[0]?.type || ''
  const entryPath = sessionStorage.getItem(entryPathStorageKey) || ''
  if (navigationType === 'back_forward' && forwardPath.includes('/app/generate/') && entryPath) {
    router.replace(entryPath)
    return
  }

  loadApp()
})

const handleBack = async () => {
  const targetPath = sessionStorage.getItem(entryPathStorageKey) || '/app/my'
  await router.replace(targetPath)
}

const resizePanel = (event: MouseEvent) => {
  if (!resizing.value) {
    return
  }
  const deltaX = event.clientX - resizeStartX.value
  const nextWidth = resizeStartWidth.value + deltaX
  const minWidth = 320
  const maxWidth = Math.floor(window.innerWidth * 0.7)
  chatPanelWidth.value = Math.max(minWidth, Math.min(nextWidth, maxWidth))
}

const stopResize = () => {
  resizing.value = false
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', resizePanel)
  window.removeEventListener('mouseup', stopResize)
}

const startResize = (event: MouseEvent) => {
  resizing.value = true
  resizeStartX.value = event.clientX
  resizeStartWidth.value = chatPanelWidth.value
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', resizePanel)
  window.addEventListener('mouseup', stopResize)
}

onUnmounted(() => {
  stopResize()
})
</script>

<style scoped>
#appGeneratorPage {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fdfdfd;
}

.top-nav {
  height: 56px;
  padding: 0 20px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
}

.app-name {
  font-weight: 600;
  font-size: 16px;
  margin-left: 8px;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 对话面板 */
.chat-panel {
  border-right: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  background: #fff;
  min-width: 320px;
  max-width: 70vw;
  flex-shrink: 0;
}

.panel-splitter {
  width: 8px;
  cursor: col-resize;
  background: transparent;
  transition: background 0.2s;
  flex-shrink: 0;
}

.panel-splitter:hover {
  background: #f0f0f0;
}

.session-panel {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.session-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: #595959;
}

.session-list {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.session-item {
  min-width: 140px;
  max-width: 180px;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.session-item:hover {
  border-color: #d9d9d9;
}

.session-item.active {
  border-color: #1a1a1a;
  background: #fafafa;
}

.session-title {
  font-size: 13px;
  color: #1f1f1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  scroll-behavior: smooth;
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.user-msg {
  flex-direction: row-reverse;
}

.message-body {
  max-width: 80%;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.user-msg .message-content {
  background: #f5f5f5;
  color: #1a1a1a;
}

.ai-msg .message-content {
  background: #fff;
  border: 1px solid #f0f0f0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.generating-indicator {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: -12px;
  margin-left: 44px;
}

.input-area {
  padding: 20px;
  border-top: 1px solid #f0f0f0;
}

.input-wrapper {
  border: 1px solid #e8e8e8;
  border-radius: 16px;
  padding: 8px;
  transition: all 0.3s;
}

.input-wrapper:focus-within {
  border-color: #1a1a1a;
  box-shadow: 0 0 0 2px rgba(0,0,0,0.02);
}

.input-wrapper :deep(textarea) {
  border: none !important;
  box-shadow: none !important;
  padding: 8px 12px;
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

/* 预览面板 */
.preview-panel {
  flex: 1;
  background: #f7f8fa;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.preview-body {
  flex: 1;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.05);
  overflow: hidden;
  position: relative;
  transition: all 0.3s;
  height: 0; /* 强制子元素计算高度 */
}

.preview-body.mobile {
  max-width: 375px;
  margin: 0 auto;
  height: 667px;
  flex: none;
}

.preview-iframe {
  width: 100%;
  height: 100%;
}

.preview-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bfbfbf;
}

.empty-content {
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.deploy-btn {
  border-radius: 20px;
  background: #1a1a1a;
  border-color: #1a1a1a;
}
</style>
