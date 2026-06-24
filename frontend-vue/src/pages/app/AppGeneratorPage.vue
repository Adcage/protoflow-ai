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
          <a-tag v-if="app?.coverTaskStatus" :color="coverTaskStatusColor(app.coverTaskStatus)">
            {{ formatCoverTaskStatus(app.coverTaskStatus, app.coverRetryCount) }}
          </a-tag>
          <a-tag v-if="app?.codeGenType" color="blue">{{ formatCodeGenType(app.codeGenType) }}</a-tag>
          <a-button :loading="downloadLoading" :disabled="!canDownload" @click="doDownload" class="download-btn">
            <template #icon><download-outlined /></template>
            下载代码
          </a-button>
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
          :selected-element="selectedElement"
          @planning-submit="handlePlanningSubmit"
          @planning-skip="handlePlanningSkip"
          @plan-confirm="handlePlanConfirm"
          @reload-session="handleReloadCurrentSession"
          @clear-selected-element="clearSelectedElement"
        />
        <ChatInputArea
          ref="chatInputAreaRef"
          :generating="generating"
          :enhancing="enhancingInput"
          :placeholder="inputPlaceholder"
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
        :app-id="appId"
        :selected-element="selectedElement"
        @iframe-load="handleIframeLoad"
        @element-selected="onElementSelected"
        @mode-change="onPreviewModeChange"
        @clear-selected-element="clearSelectedElement"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  LeftOutlined,
  CloudUploadOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import {
  createChatSession,
  deployApp,
  getAppVoById,
  listChatHistoryByPage,
  listChatSession,
  renameSession,
  deleteSession,
  enhancePrompt,
} from '@/api/appController'
import { useLoginUserStore } from '@/stores/LoginUser'
import type { ElementInfo } from '@/utils/visualEditor'
import ChatSessionPanel from '@/components/ChatSessionPanel.vue'
import ChatMessageList from '@/components/ChatMessageList.vue'
import type { ChatMessage, ToolEvent } from '@/components/ChatMessageList.vue'
import ChatInputArea from '@/components/ChatInputArea.vue'
import PreviewPanel from '@/components/PreviewPanel.vue'
import { useSSEChat } from '@/composables/useSSEChat'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()
const appId = String(route.params.id ?? '')

const app = ref<API.AppVO>()

const messages = ref<ChatMessage[]>([])
const sessions = ref<API.ChatSessionVO[]>([])
const currentSessionId = ref<string>()
const enhancingInput = ref(false)
const deployLoading = ref(false)
const downloadLoading = ref(false)
const sessionLoading = ref(false)
const sessionInitializing = ref(false)
const iframeUrl = ref('')
const previewWarning = ref('')
const previewStatus = ref<'idle' | 'generating' | 'checking' | 'ready' | 'failed'>('idle')
const chatPanelWidth = ref(450)
const resizing = ref(false)
const resizeStartX = ref(0)
const resizeStartWidth = ref(450)
const selectedElement = ref<ElementInfo | null>(null)
const editMode = ref(false)
const editingSessionId = ref<string>('')
const editingTitle = ref('')

// 组件引用
const chatMessageListRef = ref<InstanceType<typeof ChatMessageList>>()
const chatInputAreaRef = ref<InstanceType<typeof ChatInputArea>>()
const previewPanelRef = ref<InstanceType<typeof PreviewPanel>>()

const isOwner = computed(() => {
  const loginUserId = loginUserStore.loginUser?.id
  return !!(loginUserId && app.value?.userId && String(loginUserId) === String(app.value.userId))
})

const canDownload = computed(() => isOwner.value)

const inputPlaceholder = computed(() => {
  if (selectedElement.value) {
    return '已选择页面元素，请描述要修改的内容...'
  }
  return '描述具体的需求，例如：修改配色为深色模式...'
})

const normalizeId = (id?: string | number | null) => {
  if (id === undefined || id === null) return ''
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
      status: item.status || '',
      toolEvents: normalizeToolEvents(item.toolEvents || []),
    }))
    nextTick(() => {
      if (chatMessageListRef.value) {
        chatMessageListRef.value.scrollToBottom()
      }
    })
  }
}

const normalizeToolEvents = (events?: API.ToolEventVO[]) => {
  if (!events || events.length === 0) {
    return []
  }
  return events
    .filter((item) => (item.type === 'request' || item.type === 'executed') && !!item.text)
    .map((item) => ({
      type: item.type as 'request' | 'executed',
      text: item.text as string,
    }))
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
      await updatePreview()
    } else {
      const newSessionId = await createSession()
      if (newSessionId) {
        currentSessionId.value = newSessionId
      }
      if (app.value?.initPrompt && currentSessionId.value) {
        messages.value.push({ role: 'user', content: app.value.initPrompt, status: 'success', toolEvents: [] })
        startSSE(app.value.initPrompt, currentSessionId.value)
      }
    }
    return
  }
  message.error('加载应用失败，' + (res.data?.message || '请稍后重试'))
}


/**
 * SSE startSSE 由 useSSEChat composable 提供
 */

const handleReloadCurrentSession = async () => {
  if (!currentSessionId.value) {
    return
  }
  await loadRemoteHistory(currentSessionId.value)
  streamWarning.value = ''
}

const buildSelectedElementPrompt = (userInput: string) => {
  if (!selectedElement.value) {
    return userInput
  }
  const target = selectedElement.value
  const text = target.textContent || '（无可见文本）'
  const selector = target.selector || '（无可用选择器）'
  const pagePath = target.pagePath || '/'
  return [
    '选中元素信息：',
    `- 页面路径：${pagePath}`,
    `- 标签：${target.tagName}`,
    `- 选择器：${selector}`,
    `- 当前内容：${text}`,
    '',
    `修改需求：${userInput}`,
  ].join('\n')
}

// appendStreamChunk, appendToolEvent, parseAskUserArgs, handleWorkflowEvent,
// parsePathFromArguments, formatToolText → 已移到 useSSEChat composable

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

const doChatWithMessage = async (rawMessage: string) => {
  if (hasActivePlanning()) return
  if (generating.value || !rawMessage) return
  const sessionId = await ensureSessionReady()
  if (!sessionId) {
    message.warning('会话初始化中，请稍后再试')
    return
  }
  const promptMessage = buildSelectedElementPrompt(rawMessage)
  messages.value.push({ role: 'user', content: rawMessage, status: 'success', toolEvents: [] })
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(promptMessage, sessionId, app.value?.codeGenType)
}

function hasActivePlanning(): boolean {
  return messages.value.some((msg, idx) => {
    if (msg.role !== 'ai') return false
    // 优先使用结构化 planning 字段
    if (msg.planning && msg.planning.questions && msg.planning.questions.length > 0) {
      const nextUserMsg = messages.value.slice(idx + 1).find((m) => m.role === 'user')
      return !nextUserMsg
    }
    // 兼容旧 <planning> 标签
    const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/
    const match = msg.content.match(PLANNING_TAG_RE)
    if (!match) return false
    if (match[1] === 'clarification') {
      const nextUserMsg = messages.value.slice(idx + 1).find((m) => m.role === 'user')
      return !nextUserMsg
    }
    return false
  })
}

// appendStreamChunk, appendToolEvent, parseAskUserArgs, handleWorkflowEvent,
// parsePathFromArguments, formatToolText → 已移到 useSSEChat composable
// doChat, handleEnter → 已移到 doChatWithMessage 和 ChatInputArea

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
  const answersList: string[] = []
  for (const q of latest.questions) {
    const a = answers[q.id]
    if (a && a !== '（未回答）') {
      answersList.push(`${q.question}：答：${a}`)
    }
  }
  const prompt = answersList.length > 0
    ? `需求补充：${answersList.join('；')}\n\n请继续生成。`
    : '跳过补充需求，请继续生成。'
  const sessionId = currentSessionId.value
  if (!sessionId) return
  messages.value.push({ role: 'user', content: prompt, status: 'success', toolEvents: [] })
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(prompt, sessionId, app.value?.codeGenType)
}

async function handlePlanConfirm(index: number) {
  const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/
  const msg = messages.value[index]
  if (!msg) return
  const match = msg.content.match(PLANNING_TAG_RE)
  let title = ''
  if (match && match[1] === 'plan_confirmation') {
    try {
      const data = JSON.parse(match[2])
      title = data.title || ''
    } catch { /* skip */ }
  }
  const prompt = `确认实施计划「${title}」，请按计划开始生成。`
  const sessionId = currentSessionId.value
  if (!sessionId) return
  messages.value.push({ role: 'user', content: prompt, status: 'success', toolEvents: [] })
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(prompt, sessionId, app.value?.codeGenType)
}

function handlePlanningSkip(_index: number) {
  // ChatInputArea 中的 inputText 由组件自行管理
}

const doEnhanceInput = async (promptText: string) => {
  const prompt = promptText.trim()
  if (!prompt) return
  if (looksLikeRiskRejection(prompt)) {
    message.error('当前输入包含安全拦截信息，请重新输入需求描述')
    return
  }
  enhancingInput.value = true
  try {
    const res = await enhancePrompt({ prompt })
    if (res.data?.code === 0) {
      const enhanced = res.data?.data
      if (enhanced && enhanced.trim() && !looksLikeRiskRejection(enhanced)) {
        // 设置 ChatInputArea 的 inputText
        if (chatInputAreaRef.value) {
          chatInputAreaRef.value.inputText = enhanced
        }
        message.success('提示词优化完成')
      } else if (enhanced && looksLikeRiskRejection(enhanced)) {
        message.error('提示词被内容安全策略拦截，请修改后重试')
      } else {
        message.warning('AI 未返回有效的优化结果，请重试或直接发送')
      }
    } else {
      message.error('优化失败，' + (res.data?.message ?? '未知错误'))
    }
  } catch (e: unknown) {
    message.error('优化失败，' + (e instanceof Error ? e.message : String(e)))
  } finally {
    enhancingInput.value = false
  }
}

// handleEnter → 已移到 ChatInputArea

/**
 * 更新预览
 */
const updatePreview = async (refresh = false) => {
  previewWarning.value = ''
  selectedElement.value = null

  const previewUrl = app.value?.previewUrl
  if (!previewUrl) {
    if (iframeUrl.value) {
      previewStatus.value = 'ready'
      previewWarning.value = '预览地址暂不可用，显示的是上一次的预览结果'
    } else {
      iframeUrl.value = ''
      previewStatus.value = 'idle'
    }
    return
  }

  const nextUrl = refresh ? `${previewUrl}${previewUrl.includes('?') ? '&' : '?'}t=${Date.now()}` : previewUrl

  if (!refresh && iframeUrl.value) {
    const currentBase = iframeUrl.value.split('?')[0]
    const nextBase = nextUrl.split('?')[0]
    if (currentBase === nextBase && previewStatus.value === 'ready') {
      return
    }
  }

  previewStatus.value = 'checking'
  const resourceAvailable = await checkPreviewResource(nextUrl)
  if (resourceAvailable) {
    previewStatus.value = 'ready'
    iframeUrl.value = nextUrl
    return
  }

  if (iframeUrl.value) {
    previewStatus.value = 'ready'
    previewWarning.value = '预览资源检查失败，显示的是上一次的预览结果'
  } else {
    iframeUrl.value = ''
    previewStatus.value = 'idle'
  }
}

// SSE composable — 在 updatePreview 和 loadSessions 声明之后初始化，避免 TDZ
// generating 必须取 composable 返回的 ref：startSSE 内部置 true/false，
// 页面本地的 generating 之前是死 ref（恒 false），导致"AI 正在生成"指示与输入禁用失效。
const { generating, startSSE, stopSSE, streamWarning } = useSSEChat({
  appId,
  messages,
  onPreviewUpdate: () => updatePreview(true),
  onSessionsUpdate: loadSessions,
  onAppUpdate: (data) => {
    if (data.codeGenType && app.value) {
      app.value.codeGenType = data.codeGenType
    }
  },
})


const hasPreviewCandidate = () => {
  const latestAiMessage = [...messages.value].reverse().find((item) => item.role === 'ai')
  if (!latestAiMessage || latestAiMessage.status === 'failed' || looksLikeGenerationFailure(latestAiMessage.content)) {
    return false
  }
  return latestAiMessage.status === 'success' || hasFileWriteSignal(latestAiMessage)
}

const hasLatestGenerationFailure = () => {
  const latestAiMessage = [...messages.value].reverse().find((item) => item.role === 'ai')
  return (
    !!latestAiMessage && (latestAiMessage.status === 'failed' || looksLikeGenerationFailure(latestAiMessage.content))
  )
}

const hasFileWriteSignal = (messageItem: ChatMessage) => {
  if (
    messageItem.toolEvents?.some((eventItem) => eventItem.type === 'executed' && eventItem.text.includes('写入文件'))
  ) {
    return true
  }
  return messageItem.content.includes('[工具完成]') || messageItem.content.includes('已写入文件')
}

const looksLikeRiskRejection = (content: string) => {
  const lowerContent = content.toLowerCase()
  return (
    lowerContent.includes('the request was rejected') ||
    lowerContent.includes('considered high risk') ||
    lowerContent.includes('内容安全') ||
    lowerContent.includes('内容违规')
  )
}

const looksLikeGenerationFailure = (content: string) => {
  const lowerContent = content.toLowerCase()
  return (
    lowerContent.includes('the request was rejected') ||
    lowerContent.includes('high risk') ||
    content.includes('[错误]') ||
    content.includes('生成失败：') ||
    content.includes('构建失败：') ||
    content.includes('HTML代码不能为空')
  )
}

const checkPreviewResource = async (url: string) => {
  try {
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
    })
    if (!response.ok) {
      return false
    }
    const text = await response.text()
    return !(text.includes('Whitelabel Error Page') || text.includes('No static resource'))
  } catch {
    return false
  }
}

const extractLatestFailureReason = () => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const item = messages.value[i]
    if (item.role !== 'ai' || !item.content) {
      continue
    }
    const lines = item.content
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .reverse()
    const failureLine = lines.find((line) => {
      return (
        line.startsWith('生成失败：') ||
        line.startsWith('构建失败：') ||
        line.toLowerCase().includes('the request was rejected') ||
        line.toLowerCase().includes('high risk') ||
        line.includes('argument type mismatch')
      )
    })
    if (failureLine) {
      return failureLine
    }
  }
  return ''
}

const isTimeoutFailureReason = (reason: string) => {
  const lowerReason = reason.toLowerCase()
  return lowerReason.includes('timeout') || lowerReason.includes('timed out') || lowerReason.includes('read timed out')
}

// handleIframeLoad, clearSelectedElement, toggleEditMode, refreshIframe
// → 已移到 PreviewPanel 组件，以下为事件适配函数

const onElementSelected = (element: ElementInfo) => {
  selectedElement.value = element
}

const onPreviewModeChange = (enabled: boolean) => {
  editMode.value = enabled
  if (!enabled) {
    selectedElement.value = null
  }
}

const clearSelectedElement = () => {
  selectedElement.value = null
  if (previewPanelRef.value?.visualEditor) {
    previewPanelRef.value.visualEditor.clearSelection()
  }
}

const handleCreateSession = async () => {
  if (generating.value) {
    message.warning('正在生成代码，请稍后再新建会话')
    return
  }
  const newSessionId = await createSession()
  if (newSessionId) {
    clearSelectedElement()
    currentSessionId.value = newSessionId
    messages.value = []
    await updatePreview()
  }
}

const handleSwitchSession = async (sessionId?: string | number) => {
  const normalizedSessionId = normalizeId(sessionId)
  if (!normalizedSessionId || generating.value || normalizedSessionId === currentSessionId.value) {
    return
  }
  clearSelectedElement()
  currentSessionId.value = normalizedSessionId
  await loadRemoteHistory(normalizedSessionId)
  await updatePreview()
}

const startRename = (session: API.ChatSessionVO) => {
  editingSessionId.value = normalizeId(session.id)
  editingTitle.value = session.title || ''
  nextTick(() => {
    const input = document.querySelector('.session-edit-input') as HTMLInputElement
    if (input) {
      input.focus()
      input.select()
    }
  })
}

const confirmRename = async (session: API.ChatSessionVO) => {
  const sid = normalizeId(session.id)
  if (editingSessionId.value !== sid) {
    return
  }
  const newTitle = editingTitle.value.trim()
  editingSessionId.value = ''
  if (!newTitle || newTitle === session.title) {
    return
  }
  try {
    const res = await renameSession({ sessionId: session.id as number, title: newTitle })
    if (res.data?.code === 0) {
      session.title = newTitle
      message.success('重命名成功')
    } else {
      message.error('重命名失败，' + (res.data?.message || '请稍后重试'))
    }
  } catch {
    message.error('重命名失败')
  }
}

const confirmDeleteSession = (session: API.ChatSessionVO) => {
  const sid = normalizeId(session.id)
  if (!sid) {
    return
  }
  Modal.confirm({
    title: '确认删除会话',
    content: `确定要删除「${session.title || '未命名会话'}」吗？删除后不可恢复。`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        const res = await deleteSession({ id: session.id as number })
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
              if (newSessionId) {
                currentSessionId.value = newSessionId
              }
            }
            await updatePreview()
          }
          await loadSessions()
        } else {
          message.error('删除失败，' + (res.data?.message || '请稍后重试'))
        }
      } catch {
        message.error('删除失败')
      }
    },
  })
}

// formatSessionTime → 已移到 ChatSessionPanel
// formatVersionTime, loadVersions → 已移到 PreviewPanel

/**
 * 部署应用
 */
const doDeploy = async () => {
  deployLoading.value = true
  try {
    const res = await deployApp({ appId: appId as any })
    if (res.data?.code === 0) {
      message.success('部署成功！地址：' + res.data.data)
      await loadApp()
      pollCoverAfterDeploy()
    } else {
      message.error('部署失败，' + res.data?.message)
    }
  } finally {
    deployLoading.value = false
  }
}

const doDownload = async () => {
  if (!ensureValidAppId()) {
    return
  }
  if (!canDownload.value) {
    message.warning('仅应用创建者可以下载源码')
    return
  }
  downloadLoading.value = true
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
    const response = await fetch(`${baseUrl}/app/download/${appId}`, {
      method: 'GET',
      credentials: 'include',
    })
    if (!response.ok) {
      message.error('下载失败，请稍后重试')
      return
    }
    const contentDisposition = response.headers.get('Content-Disposition') || ''
    const fileNameMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
    const fileName = fileNameMatch?.[1] ? decodeURIComponent(fileNameMatch[1]) : `app-${appId}.zip`
    const blob = await response.blob()
    const blobUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(blobUrl)
    message.success('源码下载已开始')
  } catch (error: any) {
    message.error('下载失败，' + (error?.message || '未知错误'))
  } finally {
    downloadLoading.value = false
  }
}

const formatCodeGenType = (codeGenType?: string) => {
  if (codeGenType === 'single_file') {
    return '单文件模式'
  }
  if (codeGenType === 'multi-file') {
    return '多文件模式'
  }
  if (codeGenType === 'vue_project') {
    return 'Vue 项目模式'
  }
  return codeGenType || '未知模式'
}

const formatCoverTaskStatus = (status?: string, retryCount?: number) => {
  if (status === 'PENDING') {
    return '封面任务待执行'
  }
  if (status === 'RUNNING') {
    return `封面生成中（第 ${retryCount || 1} 次）`
  }
  if (status === 'SUCCESS') {
    return '封面已更新'
  }
  if (status === 'SKIPPED') {
    return '已保留原封面'
  }
  if (status === 'FAILED') {
    return `封面生成失败（重试 ${retryCount || 0} 次）`
  }
  return '封面状态未知'
}

const coverTaskStatusColor = (status?: string) => {
  if (status === 'PENDING') {
    return 'gold'
  }
  if (status === 'RUNNING') {
    return 'processing'
  }
  if (status === 'SUCCESS') {
    return 'success'
  }
  if (status === 'SKIPPED') {
    return 'default'
  }
  if (status === 'FAILED') {
    return 'error'
  }
  return 'default'
}

const pollCoverAfterDeploy = async () => {
  let count = 0
  const maxCount = 8
  const timer = setInterval(async () => {
    count += 1
    await loadApp()
    if (app.value?.cover || app.value?.coverTaskStatus === 'FAILED' || count >= maxCount) {
      if (app.value?.coverTaskStatus === 'FAILED' && app.value?.coverErrorMessage) {
        message.warning(`封面生成失败：${app.value.coverErrorMessage}`)
      }
      clearInterval(timer)
    }
  }, 4000)
}

// renderMarkdown, parseAiMessage, stripToolEventLines, scrollToBottom
// → 已移到 ChatMessageList 组件

const entryPathStorageKey = `app_generate_entry_${appId}`

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
  // visualEditor 已移到 PreviewPanel，由组件内部管理 dispose
  stopResize()
})
</script>

<style scoped>
#appGeneratorPage {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-background);
}

.top-nav {
  height: 56px;
  padding: 0 20px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-surface);
}

.app-name {
  font-weight: 600;
  font-size: 16px;
  margin-left: 8px;
  color: var(--color-text);
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 对话面板 */
.chat-panel {
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
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
  background: var(--color-border);
}

.status-tag {
  display: inline-flex;
  align-items: center;
}

.download-btn {
  border-radius: 6px;
}

.deploy-btn {
  border-radius: 6px;
}
</style>
