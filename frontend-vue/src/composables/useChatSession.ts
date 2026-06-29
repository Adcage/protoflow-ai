import { ref, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import myAxios from '@/request'
import {
  createChatSession,
  listChatHistoryByPage,
  listChatSession,
  renameSession,
  deleteSession,
} from '@/api/appController'
import { isPlanningResumeJson } from '@/utils/planningResume'
import type { AttachmentInfo } from '@/utils/chatStreamRequest'
import type { ChatMessage } from '@/types/chat'
import {
  buildMessageToolSummary,
  normalizeToolEvents,
  parsePlanningFromExtra,
  parseToolCallsFromHistory,
} from '@/utils/chatMessageTooling'

const parseAttachments = (extra?: string | null): AttachmentInfo[] | undefined => {
  if (!extra) return undefined
  try {
    const parsed = JSON.parse(extra)
    const atts = parsed.attachments
    if (!atts || !Array.isArray(atts) || atts.length === 0) return undefined
    return atts as AttachmentInfo[]
  } catch {
    return undefined
  }
}

const toChatMessage = (item: API.ChatHistoryVO): ChatMessage => {
  const toolCalls = parseToolCallsFromHistory(item.extra, item.toolEvents || [])
  return {
    role: item.messageType === 'user' ? 'user' : 'ai',
    content: item.message || '',
    status: item.status || '',
    toolEvents: normalizeToolEvents(item.toolEvents || []),
    toolCalls,
    toolStatus: buildMessageToolSummary({
      status: item.status || '',
      toolCalls,
    }),
    planning: parsePlanningFromExtra(toolCalls),
    attachments: parseAttachments(item.extra),
  }
}

/** 后处理：将 planning_resume JSON 消息中的答案注入前一条 AI 消息的 planning.answers，然后移除这些消息。 */
function injectPlanningAnswers(msgs: ChatMessage[]): ChatMessage[] {
  const resumeIndices: number[] = []
  for (let i = 1; i < msgs.length; i++) {
    const msg = msgs[i]
    if (msg.role !== 'user') continue
    if (!msg.content.startsWith('{') || !msg.content.includes('"planning_resume"')) continue
    try {
      const data = JSON.parse(msg.content)
      const answers = data.answers
      if (!answers || typeof answers !== 'object') continue
      // 注入前一条 AI 消息
      for (let j = i - 1; j >= 0; j--) {
        if (msgs[j].role === 'ai' && msgs[j].planning) {
          msgs[j].planning!.answers = answers
          break
        }
      }
      resumeIndices.push(i)
    } catch { /* skip */ }
  }
  return msgs.filter((_, idx) => !resumeIndices.includes(idx))
}

export interface ActiveGenerationStatus {
  active: boolean
  agentRunId?: number
  text?: string
}

/** 检查当前 session 是否有活跃的生成任务 */
export const checkActiveGeneration = async (sessionId: string): Promise<ActiveGenerationStatus> => {
  try {
    const res = await myAxios.get('/app/chat/gen/active', { params: { sessionId } })
    if (res.data?.code === 0) {
      const data = res.data.data
      if (data?.active) {
        return { active: true, agentRunId: data.agentRunId, text: data.text || '' }
      }
      // active=false 但 text 不为空 → gRPC 刚完成，handler 已入库
      if (data?.text) {
        return { active: false, text: data.text }
      }
    }
  } catch { /* 忽略错误 */ }
  return { active: false }
}

export function useChatSession(appId: string) {
  const sessions = ref<API.ChatSessionVO[]>([])
  const currentSessionId = ref<string>()
  const sessionLoading = ref(false)
  const sessionInitializing = ref(false)
  const messages = ref<ChatMessage[]>([])
  const currentHistoryPage = ref(1)

  const ensureValidAppId = () => {
    if (!appId) {
      message.error('应用 ID 无效，请返回列表重新进入')
      return false
    }
    return true
  }

  const loadSessions = async () => {
    if (!ensureValidAppId()) return
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
    if (!ensureValidAppId()) return undefined
    const res = await createChatSession({ appId: appId as any })
    if (res.data?.code === 0 && res.data.data) {
      const sessionId = String(res.data.data)
      await loadSessions()
      return sessionId
    }
    message.error('创建会话失败，' + (res.data?.message || '请稍后重试'))
    return undefined
  }

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

  const loadRemoteHistory = async (sessionId: string) => {
    if (!ensureValidAppId()) return
    const countRes = await listChatHistoryByPage({
      appId: appId as any,
      sessionId: sessionId as any,
      pageNum: 1,
      pageSize: 1,
    })
    if (countRes.data?.code === 0) {
      const total = countRes.data.data?.totalRow ?? 0
      const pageSize = 50
      const lastPage = total > 0 ? Math.ceil(total / pageSize) : 1
      const loadRes = await listChatHistoryByPage({
        appId: appId as any,
        sessionId: sessionId as any,
        pageNum: lastPage,
        pageSize,
      })
      if (loadRes.data?.code === 0) {
        const historyList = loadRes.data.data?.records || []
        messages.value = injectPlanningAnswers(historyList.map(toChatMessage))
        currentHistoryPage.value = lastPage
      }
    }
  }

  const loadEarlierHistory = async () => {
    if (!currentSessionId.value || currentHistoryPage.value <= 1) return
    const prevPage = currentHistoryPage.value - 1
    const res = await listChatHistoryByPage({
      appId: appId as any,
      sessionId: currentSessionId.value as any,
      pageNum: prevPage,
      pageSize: 50,
    })
    if (res.data?.code === 0) {
      const olderRecords = res.data.data?.records || []
      const olderMessages = olderRecords.map(toChatMessage)
      messages.value = [...olderMessages, ...messages.value]
      currentHistoryPage.value = prevPage
    }
  }

  const handleReloadCurrentSession = async () => {
    if (!currentSessionId.value) return
    await loadRemoteHistory(currentSessionId.value)
  }

  const handleCreateSession = async () => {
    const newSessionId = await createSession()
    if (newSessionId) {
      currentSessionId.value = newSessionId
      messages.value = []
      currentHistoryPage.value = 1
    }
  }

  const handleSwitchSession = async (sessionId?: string | number) => {
    const normalized = String(sessionId ?? '')
    if (!normalized || normalized === currentSessionId.value) return
    currentSessionId.value = normalized
    messages.value = []
    await loadRemoteHistory(normalized)
  }

  const renameChatSession = async (session: API.ChatSessionVO, newTitle: string) => {
    if (!newTitle || newTitle === session.title) return
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

  const deleteChatSession = async (session: API.ChatSessionVO) => {
    const sid = String(session.id ?? '')
    if (!sid) return
    try {
      const res = await deleteSession({ id: session.id as number })
      if (res.data?.code === 0) {
        message.success('会话已删除')
        if (currentSessionId.value === sid) {
          const remaining = sessions.value.filter((s) => String(s.id) !== sid)
          if (remaining.length > 0 && remaining[0].id) {
            currentSessionId.value = String(remaining[0].id)
            await loadRemoteHistory(currentSessionId.value)
          } else {
            currentSessionId.value = undefined
            messages.value = []
            const newId = await createSession()
            if (newId) currentSessionId.value = newId
          }
        }
        await loadSessions()
      } else {
        message.error('删除失败，' + (res.data?.message || '请稍后重试'))
      }
    } catch {
      message.error('删除失败')
    }
  }

  return {
    sessions,
    currentSessionId,
    sessionLoading,
    sessionInitializing,
    messages,
    currentHistoryPage,
    loadSessions,
    createSession,
    ensureSessionReady,
    loadRemoteHistory,
    loadEarlierHistory,
    handleReloadCurrentSession,
    handleCreateSession,
    handleSwitchSession,
    renameChatSession,
    deleteChatSession,
  }
}
