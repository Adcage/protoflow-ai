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
          :has-more="currentHistoryPage > 1"
          @planning-submit="handlePlanningSubmit"
          @planning-skip="handlePlanningSkip"
          @plan-confirm="handlePlanConfirm"
          @reload-session="handleReloadCurrentSession"
          @clear-selected-element="clearSelectedElement"
          @load-earlier="loadEarlierHistory"
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
    <ImagePreviewer />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { LeftOutlined, CloudUploadOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import { deployApp, getAppVoById, enhancePrompt } from '@/api/appController'
import { useLoginUserStore } from '@/stores/LoginUser'
import type { ElementInfo } from '@/utils/visualEditor'
import { useChatSession } from '@/composables/useChatSession'
import {
  formatCodeGenType, formatCoverTaskStatus, coverTaskStatusColor,
  looksLikeRiskRejection, buildSelectedElementPrompt,
  extractLatestFailureReason, isTimeoutFailureReason, sanitizeAiServiceError,
} from '@/utils/appGenerator'
import ChatSessionPanel, { type SessionItem } from '@/components/ChatSessionPanel.vue'
import ChatMessageList from '@/components/ChatMessageList.vue'
import ChatInputArea from '@/components/ChatInputArea.vue'
import PreviewPanel from '@/components/PreviewPanel.vue'
import ImagePreviewer from '@/components/ImagePreviewer.vue'
import { useAppPreview } from '@/composables/useAppPreview'
import { checkActiveGeneration } from '@/composables/useChatSession'
import { buildPlanningResumeJson } from '@/utils/planningResume'
import type { AttachmentInfo } from '@/utils/chatStreamRequest'

const route = useRoute()
const router = useRouter()
const loginUserStore = useLoginUserStore()
const appId = String(route.params.id ?? '')

// --- session & history (extracted composable) ---
const {
  sessions, currentSessionId, sessionLoading, messages, currentHistoryPage,
  loadSessions, loadRemoteHistory, loadEarlierHistory,
  handleCreateSession, handleSwitchSession,
  renameChatSession, deleteChatSession, ensureSessionReady, createSession,
} = useChatSession(appId)

const app = ref<API.AppVO>()
const enhancingInput = ref(false)
const deployLoading = ref(false)
const downloadLoading = ref(false)
const chatPanelWidth = ref(450)
const resizing = ref(false)
const resizeStartX = ref(0)
const resizeStartWidth = ref(450)
const selectedElement = ref<ElementInfo | null>(null)
const editMode = ref(false)
const editingSessionId = ref<string>('')
const editingTitle = ref('')

const chatMessageListRef = ref<InstanceType<typeof ChatMessageList>>()
const chatInputAreaRef = ref<InstanceType<typeof ChatInputArea>>()
const previewPanelRef = ref<InstanceType<typeof PreviewPanel>>()

const isOwner = computed(() => {
  const loginUserId = loginUserStore.loginUser?.id
  return !!(loginUserId && app.value?.userId && String(loginUserId) === String(app.value.userId))
})
const canDownload = computed(() => isOwner.value)

const inputPlaceholder = computed(() => {
  if (selectedElement.value) return '已选择页面元素，请描述要修改的内容...'
  return '描述具体的需求，例如：修改配色为深色模式...'
})

const normalizeId = (id?: string | number | null) => {
  if (id === undefined || id === null) return ''
  return String(id)
}

// --- app loading ---
const loadApp = async () => {
  if (appId) {
    const res = await getAppVoById({ id: appId as any })
    if (res.data?.code === 0) {
      app.value = res.data.data
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
          const resumed = await resumeSSE(currentSessionId.value, app.value?.codeGenType, msgIdx)
          if (!resumed && currentSessionId.value) {
            generating.value = false
            await loadRemoteHistory(currentSessionId.value)
          }
        } else if (activeGen.text) {
          // gRPC 刚完成（handler 已入库），展示文本后 reload 刷新历史
          messages.value.push({ role: 'ai', content: activeGen.text, status: 'success', toolStatus: '', toolCalls: [] })
          setTimeout(() => handleReloadCurrentSession(), 500)
        }
        await updatePreview()
      } else {
        const newSessionId = await createSession()
        if (newSessionId) currentSessionId.value = newSessionId
        if (app.value?.initPrompt && currentSessionId.value) {
          messages.value.push({ role: 'user', content: app.value.initPrompt, status: 'success', toolEvents: [] })
          startSSE(app.value.initPrompt, currentSessionId.value)
        }
        // Fork 副本无 initPrompt 但有工作区文件，需要立即显示预览
        await updatePreview()
      }
    } else {
      message.error('加载应用失败，' + (res.data?.message || '请稍后重试'))
    }
  }
}

const handleReloadCurrentSession = async () => {
  if (currentSessionId.value) {
    await loadRemoteHistory(currentSessionId.value)
    streamWarning.value = ''
  }
}

// --- chat ---
const doChatWithMessage = async (rawMessage: string, attachments?: AttachmentInfo[]) => {
  const attachmentCount = attachments?.length || 0
  if (hasActivePlanning() || generating.value || (!rawMessage && attachmentCount === 0)) return
  const sessionId = await ensureSessionReady()
  if (!sessionId) { message.warning('会话初始化中，请稍后再试'); return }
  const promptMessage = buildSelectedElementPrompt(rawMessage, selectedElement.value)
  messages.value.push({ role: 'user', content: rawMessage, status: 'success', toolEvents: [], attachments })
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(promptMessage, sessionId, app.value?.codeGenType, undefined, attachments)
}

function hasActivePlanning(): boolean {
  return messages.value.some((msg, idx) => {
    if (msg.role !== 'ai') return false
    if (msg.planning && msg.planning.questions && msg.planning.questions.length > 0) {
      return !messages.value.slice(idx + 1).find((m) => m.role === 'user')
    }
    const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/
    const match = msg.content.match(PLANNING_TAG_RE)
    if (!match) return false
    if (match[1] === 'clarification') {
      return !messages.value.slice(idx + 1).find((m) => m.role === 'user')
    }
    return false
  })
}

async function handlePlanningSubmit(answers: Record<string, string>) {
  const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/
  let latest: { questionSetId?: string; questions: { id: string; question: string }[] } | null = null
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role !== 'ai') continue
    if (msg.planning && msg.planning.questions.length > 0) {
      latest = { questionSetId: msg.planning.questionSetId, questions: msg.planning.questions }; break
    }
    const match = msg.content.match(PLANNING_TAG_RE)
    if (match && match[1] === 'clarification') {
      try { const data = JSON.parse(match[2]); latest = { questions: data.questions || [] }; break } catch { /* skip */ }
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
  let aiMsg = undefined as typeof messages.value[number] | undefined
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const candidate = messages.value[i]
    if (candidate.role === 'ai' && candidate.planning) {
      aiMsg = candidate
      break
    }
  }
  if (aiMsg) aiMsg.planning!.answers = resumeAnswers
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(jsonPrompt, sessionId, app.value?.codeGenType, jsonPrompt)
}

async function handlePlanConfirm(index: number) {
  const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/
  const msg = messages.value[index]
  if (!msg) return
  const match = msg.content.match(PLANNING_TAG_RE)
  let title = ''
  if (match && match[1] === 'plan_confirmation') {
    try { const data = JSON.parse(match[2]); title = data.title || '' } catch { /* skip */ }
  }
  const prompt = `确认实施计划「${title}」，请按计划开始生成。`
  const sessionId = currentSessionId.value
  if (!sessionId) return
  messages.value.push({ role: 'user', content: prompt, status: 'success', toolEvents: [] })
  previewWarning.value = ''
  previewStatus.value = 'generating'
  startSSE(prompt, sessionId, app.value?.codeGenType)
}

function handlePlanningSkip(_index: number) { /* ChatInputArea manages inputText */ }

const doEnhanceInput = async (promptText: string) => {
  const prompt = promptText.trim()
  if (!prompt) return
  if (looksLikeRiskRejection(prompt)) { message.error('当前输入包含安全拦截信息，请重新输入需求描述'); return }
  enhancingInput.value = true
  try {
    const res = await enhancePrompt({ prompt })
    if (res.data?.code === 0) {
      const enhanced = res.data?.data
      if (enhanced && enhanced.trim() && !looksLikeRiskRejection(enhanced)) {
        if (chatInputAreaRef.value) chatInputAreaRef.value.inputText = enhanced
        message.success('提示词优化完成')
      } else if (enhanced && looksLikeRiskRejection(enhanced)) {
        message.error('提示词被内容安全策略拦截，请修改后重试')
      } else { message.warning('AI 未返回有效的优化结果，请重试或直接发送') }
    } else { message.error('优化失败，' + sanitizeAiServiceError(res.data?.message)) }
  } catch (e: unknown) { message.error('优化失败，' + sanitizeAiServiceError(e instanceof Error ? e.message : String(e))) }
  finally { enhancingInput.value = false }
}

// --- SSE + 预览 ---
const {
  generating, startSSE, stopSSE, resumeSSE, streamWarning,
  iframeUrl, previewWarning, previewStatus,
  updatePreview,
} = useAppPreview(app, {
  appId,
  messages,
  sessions,
  loadSessions,
  onAppUpdate: (data) => {
    if (data.codeGenType && app.value) app.value.codeGenType = data.codeGenType
  },
})

// --- session handlers (delegate to composable + local UI state) ---
const startRename = (session: SessionItem) => {
  editingSessionId.value = normalizeId(session.id)
  editingTitle.value = session.title || ''
  nextTick(() => {
    const input = document.querySelector('.session-edit-input') as HTMLInputElement
    if (input) { input.focus(); input.select() }
  })
}

const confirmRename = (session: SessionItem) => {
  if (editingSessionId.value !== normalizeId(session.id)) return
  const newTitle = editingTitle.value.trim()
  editingSessionId.value = ''
  renameChatSession(session as API.ChatSessionVO, newTitle)
}

const confirmDeleteSession = (session: SessionItem) => {
  Modal.confirm({
    title: '确认删除会话',
    content: `确定要删除「${session.title || '未命名会话'}」吗？删除后不可恢复。`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => deleteChatSession(session as API.ChatSessionVO),
  })
}

// --- deploy & download ---
const doDeploy = async () => {
  deployLoading.value = true
  try {
    const res = await deployApp({ appId: appId as any })
    if (res.data?.code === 0) {
      message.success('部署成功！地址：' + res.data.data)
      await loadApp()
      pollCoverAfterDeploy()
    } else { message.error('部署失败，' + res.data?.message) }
  } finally { deployLoading.value = false }
}

const doDownload = async () => {
  if (!appId || !canDownload.value) { message.warning('仅应用创建者可以下载源码'); return }
  downloadLoading.value = true
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
    const response = await fetch(`${baseUrl}/app/download/${appId}`, { method: 'GET', credentials: 'include' })
    if (!response.ok) { message.error('下载失败，请稍后重试'); return }
    const contentDisposition = response.headers.get('Content-Disposition') || ''
    const fileNameMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
    const fileName = fileNameMatch?.[1] ? decodeURIComponent(fileNameMatch[1]) : `app-${appId}.zip`
    const blob = await response.blob()
    const blobUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl; link.download = fileName
    document.body.appendChild(link); link.click()
    document.body.removeChild(link); window.URL.revokeObjectURL(blobUrl)
    message.success('源码下载已开始')
  } catch (error: any) { message.error('下载失败，' + (error?.message || '未知错误')) }
  finally { downloadLoading.value = false }
}

const pollCoverAfterDeploy = async () => {
  let count = 0
  const timer = setInterval(async () => {
    count += 1; await loadApp()
    if (app.value?.cover || app.value?.coverTaskStatus === 'FAILED' || count >= 8) {
      if (app.value?.coverTaskStatus === 'FAILED' && app.value?.coverErrorMessage) {
        message.warning(`封面生成失败：${app.value.coverErrorMessage}`)
      }
      clearInterval(timer)
    }
  }, 4000)
}

// --- element selection ---
const onElementSelected = (element: ElementInfo) => { selectedElement.value = element }
const onPreviewModeChange = (enabled: boolean) => {
  editMode.value = enabled
  if (!enabled) selectedElement.value = null
}
const clearSelectedElement = () => {
  selectedElement.value = null
  if (previewPanelRef.value?.visualEditor) previewPanelRef.value.visualEditor.clearSelection()
}
const handleIframeLoad = () => { /* handled by PreviewPanel */ }

// --- navigation & resize ---
const entryPathStorageKey = `app_generate_entry_${appId}`

// --- 生成结束时触发预览刷新 ---
onMounted(() => {
  const backPath = (window.history.state?.back as string | undefined) || ''
  const forwardPath = (window.history.state?.forward as string | undefined) || ''
  if (backPath && !backPath.includes('/app/generate/')) sessionStorage.setItem(entryPathStorageKey, backPath)
  const navigationEntries = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]
  const navigationType = navigationEntries[0]?.type || ''
  const entryPath = sessionStorage.getItem(entryPathStorageKey) || ''
  if (navigationType === 'back_forward' && forwardPath.includes('/app/generate/') && entryPath) {
    router.replace(entryPath); return
  }
  loadApp()
})

const handleBack = async () => { await router.replace(sessionStorage.getItem(entryPathStorageKey) || '/app/my') }

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

onUnmounted(() => {
  stopSSE()
  stopResize()
})

// 同一路由切换应用时只重置状态，不停 SSE（让生成自然完成以保存历史）
watch(() => route.params.id, () => {
  if (generating.value) {
    // 直接重置 generating 状态，不 abort SSE
    generating.value = false
  }
})
</script>

<style scoped>
#appGeneratorPage {
  height: 100%;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(180deg, rgba(253, 249, 245, 0.98), rgba(245, 239, 232, 0.94));
}

.top-nav {
  height: 56px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(220, 207, 196, 0.9);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(252, 250, 247, 0.92));
  box-shadow: 0 10px 24px rgba(28, 24, 21, 0.04);
}

.app-name {
  font-weight: 600;
  font-size: 16px;
  margin-left: 8px;
  color: var(--color-text);
  font-family: var(--font-heading);
}

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

.status-tag {
  display: inline-flex;
  align-items: center;
}

.download-btn {
  border-color: var(--color-border) !important;
  color: var(--color-text-secondary) !important;
}

.download-btn:hover {
  border-color: var(--color-cta) !important;
  color: var(--color-cta) !important;
}

.deploy-btn {
  box-shadow: var(--shadow-cta) !important;
}

.deploy-btn:hover {
  box-shadow: 0 6px 16px rgba(200, 90, 62, 0.35) !important;
}

.left {
  display: flex;
  align-items: center;
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
