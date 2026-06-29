<template>
  <div class="test-chat-page">
    <!-- 未选择应用：应用选择区 -->
    <div v-if="!selectedAppId" class="app-selector">
      <div class="selector-content">
        <div class="selector-header">
          <h2>选择一个应用开始测试对话</h2>
          <p class="selector-desc">在测试模式下，AI 可以回答关于系统内部机制的问题</p>
        </div>
        <div class="selector-actions">
          <a-button type="primary" size="large" :loading="creatingApp" @click="handleCreateTestApp">
            <template #icon><PlusOutlined /></template>
            新建测试应用
          </a-button>
        </div>
        <div class="my-apps-section">
          <div v-if="loadingApps && myApps.length === 0" class="apps-loading"><LoadingOutlined /> 加载中...</div>
          <div v-else-if="myApps.length === 0" class="apps-empty">
            <a-empty description="暂无应用，点击上方按钮新建测试应用" />
          </div>
          <template v-else>
            <div class="apps-grid">
              <AppCard
                v-for="app in myApps"
                :key="app.id"
                :app="app"
                :show-user="false"
                :actions="['chat', 'delete']"
                :navigate-on-chat="false"
                @delete="handleDeleteApp"
                @card-click="selectApp"
              />
            </div>
            <div v-if="loadingMoreApps" class="apps-loading-more"><LoadingOutlined /> 加载中...</div>
            <div v-if="hasMoreApps && !loadingMoreApps" class="apps-scroll-sentinel"></div>
          </template>
        </div>
      </div>
    </div>

    <!-- 已选择应用：对话+预览区 -->
    <div v-else class="main-content">
      <!-- 左侧对话区 -->
      <div class="chat-panel" :style="{ width: `${chatPanelWidth}px` }">
        <div class="chat-panel-header">
          <div class="chat-panel-header-left">
            <a-button type="text" size="small" @click="handleSwitchApp">
              <template #icon><LeftOutlined /></template>
              返回
            </a-button>
            <a-tag color="orange" size="small">🧪 测试</a-tag>
          </div>
          <div class="chat-panel-header-right">
            <span class="app-info">{{ currentApp?.appName || '测试应用' }}</span>
            <a-tag v-if="currentApp?.codeGenType" color="blue" size="small">{{ formatCodeGenType(currentApp.codeGenType) }}</a-tag>
            <a-button type="primary" size="small" :loading="deployLoading" @click="doDeploy">
              <template #icon><CloudUploadOutlined /></template>
              部署
            </a-button>
          </div>
        </div>
        <ChatSessionPanel
          :sessions="sessions"
          :current-session-id="currentSessionId || ''"
          :loading="sessionLoading"
          :editing-session-id="editingSessionId"
          :editing-title="editingTitle"
          @select="handleSwitchSession"
          @create="handleCreateSession"
          @start-rename="startRename"
          @confirm-rename="confirmRename"
          @delete="confirmDeleteSession"
          @update:editing-title="editingTitle = $event"
        />
        <ChatMessageList
          ref="chatMessageListRef"
          :messages="messages"
          :generating="generating"
          :stream-warning="streamWarning"
          :user-avatar="loginUserStore.loginUser.userAvatar || ''"
          @planning-submit="handlePlanningSubmit"
          @planning-skip="handlePlanningSkip"
          @plan-confirm="handlePlanConfirm"
          @reload-session="handleReloadCurrentSession"
          @clear-selected-element="() => {}"
        />
        <ChatInputArea
          :generating="generating"
          :placeholder="'输入测试指令，按 Enter 发送...'"
          @send="doChatWithMessage"
          @enhance="doEnhanceInput"
        />
      </div>

      <div class="panel-splitter" @mousedown="startResize" />

      <!-- 右侧预览区 -->
      <PreviewPanel
        ref="previewPanelRef"
        :iframe-url="iframeUrl"
        :preview-status="previewStatus"
        :preview-warning="previewWarning"
        :app-id="selectedAppId"
        @iframe-load="() => {}"
        @element-selected="() => {}"
        @mode-change="() => {}"
        @clear-selected-element="() => {}"
      />
    </div>
    <ImagePreviewer />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  LeftOutlined,
  CloudUploadOutlined,
  PlusOutlined,
  LoadingOutlined,
} from '@ant-design/icons-vue'
import {
  addApp,
  createChatSession,
  deleteApp,
  deployApp,
  getAppVoById,
  listChatHistoryByPage,
  listChatSession,
  listMyAppVoByPage,
  renameSession,
  deleteSession,
  enhancePrompt,
} from '@/api/appController'
import { useLoginUserStore } from '@/stores/LoginUser'
import AppCard from '@/components/AppCard.vue'
import ChatSessionPanel, { type SessionItem } from '@/components/ChatSessionPanel.vue'
import ChatMessageList from '@/components/ChatMessageList.vue'
import ChatInputArea from '@/components/ChatInputArea.vue'
import PreviewPanel from '@/components/PreviewPanel.vue'
import { useAppPreview } from '@/composables/useAppPreview'
import { checkActiveGeneration } from '@/composables/useChatSession'
import { buildPlanningResumeJson } from '@/utils/planningResume'
import { parseChatHistoryAttachments } from '@/utils/chatAttachmentDisplay'
import ImagePreviewer from '@/components/ImagePreviewer.vue'
import type { AttachmentInfo } from '@/utils/chatStreamRequest'
import type { ChatMessage } from '@/types/chat'
import { buildMessageToolSummary, normalizeToolEvents, parsePlanningFromExtra, parseToolCallsFromHistory } from '@/utils/chatMessageTooling'

const router = useRouter()
const route = useRoute()
const loginUserStore = useLoginUserStore()

// 应用选择状态：由路由参数驱动
const selectedAppId = ref(route.params.appId ? String(route.params.appId) : '')
const currentApp = ref<API.AppVO>()
const myApps = ref<API.AppVO[]>([])
const loadingApps = ref(false)
const loadingMoreApps = ref(false)
const creatingApp = ref(false)
// 后端限制每页最多 20 条，这里做真分页而非一次性大 pageSize
const APP_PAGE_SIZE = 20
const appPageNum = ref(1)
const appTotal = ref(0)

// 对话状态
const messages = ref<ChatMessage[]>([])
const sessions = ref<API.ChatSessionVO[]>([])
const currentSessionId = ref<string>()
const sessionLoading = ref(false)
const sessionInitializing = ref(false)
const editingSessionId = ref('')
const editingTitle = ref('')
const deployLoading = ref(false)

// 布局状态
const chatPanelWidth = ref(450)
const resizing = ref(false)
const resizeStartX = ref(0)
const resizeStartWidth = ref(450)

// 组件引用
const chatMessageListRef = ref<InstanceType<typeof ChatMessageList>>()
const previewPanelRef = ref<InstanceType<typeof PreviewPanel>>()

// SSE composable + 预览
const {
  startSSE, stopSSE, resumeSSE, generating, streamWarning,
  iframeUrl, previewWarning, previewStatus,
  updatePreview,
} = useAppPreview(currentApp, {
  appId: selectedAppId,
  messages,
  sessions,
  loadSessions,
  onAppUpdate: (data) => {
    if (data.codeGenType && currentApp.value) {
      currentApp.value.codeGenType = data.codeGenType
    }
  },
})

const normalizeId = (id?: string | number | null) => {
  if (id === undefined || id === null) return ''
  return String(id)
}

const initAppChat = async (appId: string) => {
  selectedAppId.value = appId
  const res = await getAppVoById({ id: appId as any })
  if (res.data?.code === 0) {
    currentApp.value = res.data.data
  }
  await loadSessions()
  if (sessions.value.length > 0 && sessions.value[0].id) {
    currentSessionId.value = normalizeId(sessions.value[0].id)
    await loadRemoteHistory(currentSessionId.value)
    // 检查是否有活跃生成
    const activeGen = await checkActiveGeneration(currentSessionId.value)
    if (activeGen.active) {
      // gRPC 还在跑：立即显示 generating 指示器，展示累积文本，尝试 SSE 重连
      generating.value = true
      const msgIdx = messages.value.length
      messages.value.push({ role: 'ai', content: activeGen.text || '', status: 'running', toolStatus: '', toolCalls: [] })
      const resumed = await resumeSSE(currentSessionId.value, currentApp.value?.codeGenType, msgIdx)
      if (!resumed && currentSessionId.value) {
        generating.value = false
        await loadRemoteHistory(currentSessionId.value)
      }
    } else if (activeGen.text) {
      // gRPC 刚完成（handler 已入库），展示文本后 reload 刷新历史
      messages.value.push({ role: 'ai', content: activeGen.text, status: 'success', toolStatus: '', toolCalls: [] })
      setTimeout(() => {
        if (currentSessionId.value) loadRemoteHistory(currentSessionId.value)
      }, 500)
    }
    await updatePreview()
  } else {
    const newSessionId = await createSession()
    if (newSessionId) {
      currentSessionId.value = newSessionId
    }
  }
}

const resetChatState = () => {
  stopSSE()
  selectedAppId.value = ''
  currentApp.value = undefined
  messages.value = []
  sessions.value = []
  currentSessionId.value = undefined
  iframeUrl.value = ''
  previewStatus.value = 'idle'
}

watch(
  () => route.params.appId,
  (newAppId) => {
    if (newAppId) {
      initAppChat(String(newAppId))
    } else {
      resetChatState()
    }
  },
  { immediate: true },
)

// ======== 应用选择逻辑 ========

const loadMyApps = async (append = false) => {
  if (append) {
    loadingMoreApps.value = true
  } else {
    loadingApps.value = true
  }
  try {
    const res = await listMyAppVoByPage({
      pageNum: appPageNum.value,
      pageSize: APP_PAGE_SIZE,
      isTestApp: true,
      sortField: 'createTime',
      sortOrder: 'descend',
    })
    if (res.data?.code === 0) {
      const records = res.data.data?.records || []
      if (append) {
        myApps.value.push(...records)
      } else {
        myApps.value = records
      }
      appTotal.value = res.data.data?.totalRow || 0
    }
  } finally {
    loadingApps.value = false
    loadingMoreApps.value = false
  }
}

const loadMoreApps = () => {
  if (loadingMoreApps.value || !hasMoreApps.value) return
  appPageNum.value++
  loadMyApps(true).then(() => observeSentinel())
}

const hasMoreApps = computed(() => myApps.value.length < appTotal.value)

let appsObserver: IntersectionObserver | null = null

const setupAppsObserver = () => {
  appsObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting && hasMoreApps.value && !loadingMoreApps.value) {
        loadMoreApps()
      }
    },
    { rootMargin: '200px' },
  )
}

const observeSentinel = () => {
  if (!appsObserver) setupAppsObserver()
  nextTick(() => {
    const sentinel = document.querySelector('.apps-scroll-sentinel')
    if (sentinel) appsObserver!.observe(sentinel)
  })
}

const handleCreateTestApp = async () => {
  creatingApp.value = true
  try {
    const res = await addApp({ initPrompt: '测试应用', isTestApp: true })
    if (res.data?.code === 0 && res.data.data) {
      message.success('测试应用创建成功')
      appPageNum.value = 1
      await loadMyApps()
      selectApp({ id: res.data.data } as API.AppVO)
    } else {
      message.error('创建失败，' + (res.data?.message || '请稍后重试'))
    }
  } finally {
    creatingApp.value = false
  }
}

const selectApp = (app: API.AppVO) => {
  router.push(`/admin/test-chat/${app.id}`)
  return true
}

const handleSwitchApp = () => {
  router.push('/admin/test-chat')
}

const handleDeleteApp = async (id?: number) => {
  if (!id) return
  const res = await deleteApp({ id })
  if (res.data?.code === 0) {
    message.success('删除成功')
    if (selectedAppId.value === String(id)) {
      router.push('/admin/test-chat')
    }
    appPageNum.value = 1
    await loadMyApps()
  } else {
    message.error('删除失败，' + (res.data?.message || '请稍后重试'))
  }
}

// ======== 会话管理 ========

async function loadSessions() {
  if (!selectedAppId.value) return
  sessionLoading.value = true
  try {
    const res = await listChatSession({ appId: selectedAppId.value as any })
    if (res.data?.code === 0) {
      sessions.value = res.data.data || []
    }
  } finally {
    sessionLoading.value = false
  }
}

const createSession = async () => {
  if (!selectedAppId.value) return undefined
  const res = await createChatSession({ appId: selectedAppId.value as any })
  if (res.data?.code === 0 && res.data.data) {
    const sessionId = normalizeId(res.data.data)
    await loadSessions()
    return sessionId
  }
  return undefined
}

const loadRemoteHistory = async (sessionId: string) => {
  if (!selectedAppId.value) return
  const res = await listChatHistoryByPage({
    appId: selectedAppId.value as any,
    sessionId: sessionId as any,
    pageNum: 1,
    pageSize: 200,
  })
  if (res.data?.code === 0) {
    const historyList = res.data.data?.records || []
    let msgs: ChatMessage[] = historyList.map((item) => {
      const toolCalls = parseToolCallsFromHistory(item.extra, item.toolEvents || [])
      return {
        role: item.messageType === 'user' ? 'user' : ('ai' as const),
        content: item.message || '',
        status: item.status || '',
        toolEvents: normalizeToolEvents(item.toolEvents || []),
        toolCalls,
        toolStatus: buildMessageToolSummary({
          status: item.status || '',
          toolCalls,
        }),
        attachments: parseChatHistoryAttachments(item.extra),
        planning: parsePlanningFromExtra(toolCalls),
      }
    })
    // 将 planning_resume JSON 消息的答案注入前一条 AI 消息，然后移除
    const resumeIndices: number[] = []
    for (let i = 1; i < msgs.length; i++) {
      const msg = msgs[i]
      if (msg.role !== 'user' || !msg.content.startsWith('{') || !msg.content.includes('"planning_resume"')) continue
      try {
        const data = JSON.parse(msg.content)
        if (data.answers && typeof data.answers === 'object') {
          for (let j = i - 1; j >= 0; j--) {
            if (msgs[j].role === 'ai' && msgs[j].planning) {
              msgs[j].planning!.answers = data.answers
              break
            }
          }
          resumeIndices.push(i)
        }
      } catch { /* skip */ }
    }
    messages.value = msgs.filter((_, idx) => !resumeIndices.includes(idx))
    nextTick(() => {
      chatMessageListRef.value?.scrollToBottom()
    })
  }
}

const handleCreateSession = async () => {
  if (generating.value) {
    message.warning('正在生成内容，请稍后再新建会话')
    return
  }
  const newSessionId = await createSession()
  if (newSessionId) {
    currentSessionId.value = newSessionId
    messages.value = []
    await updatePreview()
  }
}

const handleSwitchSession = async (sessionId?: string | number) => {
  const normalizedSessionId = normalizeId(sessionId)
  if (!normalizedSessionId || generating.value || normalizedSessionId === currentSessionId.value) return
  currentSessionId.value = normalizedSessionId
  await loadRemoteHistory(normalizedSessionId)
  await updatePreview()
}

const startRename = (session: SessionItem) => {
  editingSessionId.value = normalizeId(session.id)
  editingTitle.value = session.title || ''
}

const confirmRename = async (session: SessionItem) => {
  const sid = normalizeId(session.id)
  if (editingSessionId.value !== sid) return
  const newTitle = editingTitle.value.trim()
  editingSessionId.value = ''
  if (!newTitle || newTitle === session.title) return
  try {
    const res = await renameSession({ sessionId: Number(session.id), title: newTitle })
    if (res.data?.code === 0) {
      session.title = newTitle
      message.success('重命名成功')
    }
  } catch {
    message.error('重命名失败')
  }
}

const confirmDeleteSession = (session: SessionItem) => {
  const sid = normalizeId(session.id)
  if (!sid) return
  Modal.confirm({
    title: '确认删除会话',
    content: `确定要删除「${session.title || '未命名会话'}」吗？`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        const res = await deleteSession({ id: Number(session.id) })
        if (res.data?.code === 0) {
          message.success('会话已删除')
          if (currentSessionId.value === sid) {
            const remaining = sessions.value.filter((s) => normalizeId(s.id) !== sid)
            if (remaining.length > 0 && remaining[0].id) {
              currentSessionId.value = normalizeId(remaining[0].id)
              await loadRemoteHistory(currentSessionId.value)
            } else {
              currentSessionId.value = undefined
              messages.value = []
              const newSessionId = await createSession()
              if (newSessionId) currentSessionId.value = newSessionId
            }
            await updatePreview()
          }
          await loadSessions()
        }
      } catch {
        message.error('删除失败')
      }
    },
  })
}

// ======== 对话逻辑 ========

const ensureSessionReady = async () => {
  if (currentSessionId.value) return currentSessionId.value
  if (sessionInitializing.value) return undefined
  sessionInitializing.value = true
  try {
    const sessionId = await createSession()
    if (sessionId) currentSessionId.value = sessionId
    return sessionId
  } finally {
    sessionInitializing.value = false
  }
}

const doChatWithMessage = async (rawMessage: string, attachments?: AttachmentInfo[]) => {
  const attachmentCount = attachments?.length || 0
  if (generating.value || (!rawMessage && attachmentCount === 0)) return
  const sessionId = await ensureSessionReady()
  if (!sessionId) {
    message.warning('会话初始化中，请稍后再试')
    return
  }
  messages.value.push({ role: 'user', content: rawMessage, status: 'success', toolEvents: [], attachments })
  iframeUrl.value = ''
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(rawMessage, sessionId, currentApp.value?.codeGenType, undefined, attachments)
}

const handleReloadCurrentSession = async () => {
  if (!currentSessionId.value) return
  await loadRemoteHistory(currentSessionId.value)
  streamWarning.value = ''
}

const doEnhanceInput = async (promptText: string) => {
  const prompt = promptText.trim()
  if (!prompt) return
  try {
    const res = await enhancePrompt({ prompt })
    if (res.data?.code === 0) {
      const enhanced = res.data?.data
      if (enhanced && enhanced.trim()) {
        message.success('提示词优化完成，请查看输入框')
      }
    }
  } catch {
    message.error('优化失败')
  }
}

// Planning 事件处理
async function handlePlanningSubmit(answers: Record<string, string>) {
  const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/
  // 优先从结构化 planning 字段查找最新 clarification
  let latest: { questionSetId?: string; questions: { id: string; question: string }[] } | null = null
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role !== 'ai') continue
    if (msg.planning && msg.planning.questions.length > 0) {
      latest = { questionSetId: msg.planning.questionSetId, questions: msg.planning.questions }
      break
    }
    const match = msg.content.match(PLANNING_TAG_RE)
    if (match && match[1] === 'clarification') {
      try {
        const data = JSON.parse(match[2])
        latest = { questions: data.questions || [] }
        break
      } catch {
        // skip
      }
    }
  }
  if (!latest) return
  const displayAnswers: { question: string; answer: string }[] = []
  const resumeAnswers: Record<string, string> = {}
  for (const q of latest.questions) {
    const a = answers[q.id]
    if (a && a !== '（未回答）') {
      displayAnswers.push({ question: q.question, answer: a })
      resumeAnswers[q.id] = a
    }
  }
  const jsonPrompt = buildPlanningResumeJson({
    questionSetId: latest.questionSetId,
    answers: resumeAnswers,
  })
  const sessionId = currentSessionId.value
  if (!sessionId) return
  // 不生成用户消息气泡，将答案注入 AI 消息的 planning.answers
  const aiMsg = messages.value.findLast(m => m.role === 'ai' && m.planning)
  if (aiMsg) aiMsg.planning!.answers = resumeAnswers
  iframeUrl.value = ''
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(jsonPrompt, sessionId, currentApp.value?.codeGenType, jsonPrompt)
}

async function handlePlanConfirm(index: number) {
  const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/
  const msg = messages.value[index]
  if (!msg) return
  const match = msg.content.match(PLANNING_TAG_RE)
  let title = ''
  if (match && match[1] === 'plan_confirmation') {
    try { title = JSON.parse(match[2]).title || '' } catch { /* skip */ }
  }
  const prompt = `确认实施计划「${title}」，请按计划开始生成。`
  const sessionId = currentSessionId.value
  if (!sessionId) return
  messages.value.push({ role: 'user', content: prompt, status: 'success', toolEvents: [] })
  iframeUrl.value = ''
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(prompt, sessionId, currentApp.value?.codeGenType)
}

function handlePlanningSkip(_index: number) {}

// ======== 部署 ========

const doDeploy = async () => {
  if (!selectedAppId.value) return
  deployLoading.value = true
  try {
    const res = await deployApp({ appId: selectedAppId.value as any })
    if (res.data?.code === 0) {
      message.success('部署成功！地址：' + res.data.data)
    } else {
      message.error('部署失败，' + res.data?.message)
    }
  } finally {
    deployLoading.value = false
  }
}

// ======== 面板调整 ========

const resizePanel = (event: MouseEvent) => {
  if (!resizing.value) return
  const deltaX = event.clientX - resizeStartX.value
  const nextWidth = resizeStartWidth.value + deltaX
  chatPanelWidth.value = Math.max(320, Math.min(nextWidth, Math.floor(window.innerWidth * 0.7)))
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

// ======== 工具函数 ========

const formatCodeGenType = (codeGenType?: string) => {
  if (codeGenType === 'single_file') return '单文件模式'
  if (codeGenType === 'multi-file') return '多文件模式'
  if (codeGenType === 'vue_project') return 'Vue 项目模式'
  return codeGenType || '未知模式'
}

// ======== 生命周期 ========

onMounted(() => {
  loadMyApps().then(() => observeSentinel())
})

onUnmounted(() => {
  stopSSE()
  stopResize()
  appsObserver?.disconnect()
})
</script>

<style scoped>
.test-chat-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(180deg, rgba(253, 249, 245, 0.98), rgba(245, 239, 232, 0.94));
}

/* 应用选择区 */
.app-selector {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 32px 24px;
  overflow-y: auto;
}

.selector-content {
  max-width: 1200px;
  width: 100%;
}

.selector-header {
  margin-bottom: 32px;
}

.selector-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 8px 0;
}

.selector-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.selector-actions {
  margin-bottom: 24px;
}

.apps-loading,
.apps-empty {
  text-align: center;
  padding: 32px;
  color: var(--color-text-tertiary);
}

.apps-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.apps-load-more,
.apps-loading-more {
  text-align: center;
  padding: 16px 0;
  color: var(--color-text-tertiary);
}

.apps-scroll-sentinel {
  height: 1px;
}

/* 对话+预览区 */
.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  gap: 12px;
  padding: 18px;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92);
  min-width: 320px;
  max-width: 70vw;
  flex-shrink: 0;
  border: 1px solid rgba(220, 207, 196, 0.92);
  border-radius: 22px;
  overflow: hidden;
  box-shadow: var(--color-panel-shadow);
}

.chat-panel-header {
  height: 44px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(220, 207, 196, 0.92);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(252, 250, 247, 0.92));
}

.chat-panel-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-panel-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-panel-header .app-info {
  font-size: 13px;
  color: var(--color-text-secondary);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-splitter {
  width: 10px;
  cursor: col-resize;
  background: transparent;
  transition: background 0.2s;
  flex-shrink: 0;
  border-radius: 999px;
  margin: 10px 0;
}

.panel-splitter:hover {
  background: rgba(200, 90, 62, 0.12);
}

@media (max-width: 1024px) {
  .main-content {
    flex-direction: column;
  }

  .chat-panel {
    max-width: 100%;
    width: 100% !important;
  }

  .panel-splitter {
    display: none;
  }
}
</style>
