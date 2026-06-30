import { ref, unref, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { ssePost } from '@/utils/sseRequest'
import { extractBusinessChunk, splitConcatenatedJsonObjects } from './sseParser'
import { buildChatStreamRequestBody, type AttachmentInfo } from '@/utils/chatStreamRequest'
import type { ChatMessage, PlanningQuestion, PlanningQuestionSet, ToolCallRecord } from '@/types/chat'
import { formatToolCallDescription } from '@/utils/chatMessageTooling'

export interface SSEChatOptions {
  appId: string | Ref<string>
  messages: Ref<ChatMessage[]>
  onPreviewUpdate: () => void
  onSessionsUpdate?: () => void
  onAppUpdate?: (data: { codeGenType?: string }) => void
}

/**
 * SSE 流式对话 composable
 * 封装基于 fetch 的 POST SSE 连接管理、消息流解析、工具调用事件处理
 */
export function useSSEChat(options: SSEChatOptions) {
  const { appId, messages, onPreviewUpdate, onSessionsUpdate, onAppUpdate } = options

  const generating = ref(false)
  const streamWarning = ref('')
  let currentAbortController: AbortController | null = null
  let previewUpdateTimer: ReturnType<typeof setTimeout> | null = null



  const finalizeGeneration = (aiMsgIndex: number, streamCompleted: boolean, delayPreviewRefresh = false) => {
    currentAbortController = null
    if (streamCompleted) {
      streamWarning.value = ''
    }
    if (!generating.value) {
      return
    }
    generating.value = false
    onSessionsUpdate?.()
    const finish = () => {
      if (messages.value[aiMsgIndex]) {
        messages.value[aiMsgIndex].status = streamCompleted ? 'success' : 'failed'
      }
      onPreviewUpdate()
    }
    if (delayPreviewRefresh) {
      setTimeout(finish, 500)
      return
    }
    finish()
  }

  const parseSseEvent = (frame: string): { event: string; data: string } => {
    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of frame.split('\n')) {
      if (!line || line.startsWith(':')) continue
      if (line.startsWith('event:')) {
        eventName = line.slice('event:'.length).trim() || 'message'
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trimStart())
      }
    }
    return {
      event: eventName,
      data: dataLines.join('\n'),
    }
  }

  const readSseStream = async (
    response: Response,
    onFrame: (eventName: string, data: string) => boolean | void,
  ) => {
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('SSE 响应流为空')
    }
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        if (buffer.trim()) {
          const parsed = parseSseEvent(buffer.trim())
          if (onFrame(parsed.event, parsed.data)) {
            return
          }
        }
        return
      }
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let separatorIndex = buffer.indexOf('\n\n')
      while (separatorIndex >= 0) {
        const frame = buffer.slice(0, separatorIndex).trim()
        buffer = buffer.slice(separatorIndex + 2)
        if (frame) {
          const parsed = parseSseEvent(frame)
          if (onFrame(parsed.event, parsed.data)) {
            await reader.cancel()
            return
          }
        }
        separatorIndex = buffer.indexOf('\n\n')
      }
    }
  }

  const startSSE = (
    userMsg: string,
    sessionId: string,
    codeGenType?: string,
    displayMessage?: string,
    attachments?: AttachmentInfo[],
  ) => {
    generating.value = true
    streamWarning.value = ''
    let streamCompleted = false
    let hasBusinessError = false

    // 标记用户消息中的附件（前端展示用）
    if (attachments && attachments.length > 0) {
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === 'user') {
        lastMsg.attachments = attachments
      }
    }

    const aiMsgIndex = messages.value.length
    messages.value.push({ role: 'ai', content: '', status: 'running', toolStatus: '', toolCalls: [] })

    const isStructuredToolMode =
      codeGenType === 'vue_project' || codeGenType === 'multi-file' || codeGenType === 'single_file'

    const controller = new AbortController()
    currentAbortController = controller

    void (async () => {
      try {
        const requestBody = buildChatStreamRequestBody({
          appId: unref(appId),
          sessionId,
          message: userMsg,
          displayMessage,
          attachments,
        })
        const response = await ssePost({
          path: '/app/chat/gen/code/stream',
          body: requestBody,
          signal: controller.signal,
        })

        await readSseStream(response, (eventName, data) => {
          if (eventName === 'meta') {
            try {
              const meta = JSON.parse(data)
              void meta
            } catch (e) {
              console.error('SSE Meta Parse Error', e)
            }
            return false
          }

          if (eventName === 'business-error') {
            hasBusinessError = true
            try {
              const payload = JSON.parse(data)
              const errorMsg = payload.message || '操作失败'
              messages.value[aiMsgIndex].content += `\n\n[错误] ${errorMsg}`
              messages.value[aiMsgIndex].status = 'failed'
              message.error(errorMsg)
            } catch {
              message.error('操作失败')
            }
            return true
          }

          if (eventName === 'done') {
            streamCompleted = true
            return true
          }

          const rawData = data
          if (rawData === '[DONE]') {
            streamCompleted = true
            return true
          }

          const fragments = extractBusinessChunk(rawData)
          for (const fragment of fragments) {
            if (fragment === '[DONE]') {
              streamCompleted = true
              return true
            }
            if (!fragment) continue
            appendStreamChunk(aiMsgIndex, fragment, isStructuredToolMode)
          }
          return false
        })

        if (streamCompleted) {
          finalizeGeneration(aiMsgIndex, true, true)
          return
        }
        if (!hasBusinessError && !controller.signal.aborted) {
          streamWarning.value = '连接中断，本次 AI 输出可能未完整保存。可重新加载当前会话查看已落库内容。'
          messages.value[aiMsgIndex].status = 'failed'
          message.warning('连接中断，已停止本次生成')
        }
        finalizeGeneration(aiMsgIndex, false)
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        const errorText = error instanceof Error ? error.message : String(error)
        messages.value[aiMsgIndex].status = 'failed'
        if (errorText) {
          messages.value[aiMsgIndex].content += `\n\n[错误] ${errorText}`
        }
        message.error('操作失败')
        finalizeGeneration(aiMsgIndex, false)
      }
    })()
  }

  const stopSSE = () => {
    if (currentAbortController) {
      currentAbortController.abort()
      currentAbortController = null
    }
    generating.value = false
  }

  /**
   * 重连到活跃生成：前端切走再回来时，续收后续实时事件。
   * POST /resume 从 Sink 订阅新事件，追加到现有的 AI message。
   * @param sessionId   会话 ID
   * @param codeGenType 代码生成类型（决定是否 JSON 解析）
   * @param aiMsgIndex  已存在的 AI message 的索引
   */
  const resumeSSE = async (sessionId: string, codeGenType?: string, aiMsgIndex?: number): Promise<boolean> => {
    const msgIndex = aiMsgIndex ?? messages.value.length - 1
    if (msgIndex < 0 || msgIndex >= messages.value.length) return false
    generating.value = true

    const controller = new AbortController()
    currentAbortController = controller

    const isStructuredToolMode =
      codeGenType === 'vue_project' || codeGenType === 'multi-file' || codeGenType === 'single_file'

    try {
      const response = await ssePost({
        path: '/app/chat/gen/code/stream/resume',
        body: { sessionId },
        signal: controller.signal,
      })

      await readSseStream(response, (eventName, data) => {
        if (eventName === 'business-error') {
          finalizeGeneration(msgIndex, false)
          return true
        }
        if (eventName === 'done') {
          finalizeGeneration(msgIndex, true, true)
          return true
        }
        if (eventName === 'meta') return false

        const rawData = data
        if (rawData === '[DONE]') {
          finalizeGeneration(msgIndex, true, true)
          return true
        }

        const fragments = extractBusinessChunk(rawData)
        for (const fragment of fragments) {
          if (fragment === '[DONE]') {
            finalizeGeneration(msgIndex, true, true)
            return true
          }
          if (fragment) appendStreamChunk(msgIndex, fragment, isStructuredToolMode)
        }
        return false
      })

      finalizeGeneration(msgIndex, true, true)
      return true
    } catch (error) {
      if (controller.signal.aborted) return false
      finalizeGeneration(msgIndex, false)
      return false
    }
  }

  const appendStreamChunk = (aiMsgIndex: number, chunk: string, _structuredToolMode: boolean) => {
    if (!chunk) return

    const processJson = (jsonStr: string): boolean => {
      try {
        const messageObj = JSON.parse(jsonStr)
        if (messageObj && typeof messageObj === 'object') {
          // ai_response → 追加到消息文本
          if (messageObj.type === 'ai_response' && typeof messageObj.data === 'string') {
            const data = messageObj.data
            if (data && data !== 'waiting_for_user' && messages.value[aiMsgIndex]) {
              messages.value[aiMsgIndex].content += data
            }
            return true
          }
          // 工具调用/状态 → 走 dispatchMessageEvent
          if (typeof messageObj.type === 'string') {
            return dispatchMessageEvent(messageObj, aiMsgIndex)
          }
        }
        return false
      } catch {
        return false
      }
    }

    // 始终优先尝试 JSON 解析（工具事件、状态事件等）
    if (processJson(chunk)) {
      return
    }

    // 尝试分割多个 JSON 对象：{...}{...}{...}
    const fragments = splitConcatenatedJsonObjects(chunk)
    if (fragments.length > 1) {
      let anyProcessed = false
      for (const fragment of fragments) {
        if (processJson(fragment)) {
          anyProcessed = true
        }
      }
      if (anyProcessed) {
        return
      }
    }

    // 非结构化模式：纯文本追加到消息
    messages.value[aiMsgIndex].content += chunk
  }

  const ensureToolState = (
    aiMsgIndex: number,
  ): (ChatMessage & { toolCalls: ToolCallRecord[]; toolStatus: string }) | null => {
    const targetMessage = messages.value[aiMsgIndex]
    if (!targetMessage) return null
    if (!targetMessage.toolCalls) {
      targetMessage.toolCalls = []
    }
    if (!targetMessage.toolStatus) {
      targetMessage.toolStatus = ''
    }
    return targetMessage as ChatMessage & { toolCalls: ToolCallRecord[]; toolStatus: string }
  }

  const dispatchMessageEvent = (messageObj: Record<string, unknown>, aiMsgIndex: number): boolean => {
    const type = messageObj.type
    if (type === 'ai_response') {
      const data = (messageObj.data as string) || ''
      if (data !== 'waiting_for_user') {
        messages.value[aiMsgIndex].content += data
      }
      return true
    }
    if (type === 'tool_request') {
      if (messageObj.name === 'ask_user') {
        const payload = parseAskUserStructuredPayload(
          messageObj.arguments as string | Record<string, unknown> | undefined,
        )
        if (!payload) return true
        const targetMessage = messages.value[aiMsgIndex]
        if (
          !targetMessage.planning ||
          targetMessage.planning.questionSetId !== payload.questionSetId
        ) {
          targetMessage.planning = payload
        }
        return true
      }
      const targetMessage = ensureToolState(aiMsgIndex)
      if (!targetMessage) return true
      const id = (messageObj.id as string) || ''
      const name = (messageObj.name as string) || ''
      const args = (messageObj.arguments as string) || ''
      const agentName = (messageObj.agentName as string) || ''
      const description = formatToolCallDescription(name, args, 'request', undefined)
      targetMessage.toolCalls.push({
        type: 'request',
        id,
        name,
        description,
        arguments: args,
        status: 'running',
        timestamp: Date.now(),
        agentName,
      })
      targetMessage.toolStatus = description
      if (agentName) targetMessage.agentName = agentName
      return true
    }
    if (type === 'tool_executed') {
      if (messageObj.name === 'ask_user') return true
      const targetMessage = ensureToolState(aiMsgIndex)
      if (!targetMessage) return true
      const toolId = (messageObj.id as string) || ''
      const name = (messageObj.name as string) || ''
      const args = (messageObj.arguments as string) || ''
      const result = (messageObj.result as string) || ''
      const agentName = (messageObj.agentName as string) || ''
      const existing = targetMessage.toolCalls.find((tc) => tc.id === toolId)
      if (existing) {
        existing.type = 'executed'
        existing.result = result
        existing.status = 'completed'
      } else {
        targetMessage.toolCalls.push({
          type: 'executed',
          id: toolId,
          name,
          description: formatToolCallDescription(name, args, 'executed', result),
          arguments: args,
          result,
          status: 'completed',
          timestamp: Date.now(),
          agentName,
        })
      }
      // 工具执行完成 → 文件可能已变化，防抖触发预览检查
      if (previewUpdateTimer) clearTimeout(previewUpdateTimer)
      previewUpdateTimer = setTimeout(() => {
        onPreviewUpdate()
        previewUpdateTimer = null
      }, 2000)
      return true
    }
    if (type === 'status') {
      const statusText = (messageObj.message as string) || ''
      if (statusText) {
        const targetMessage = ensureToolState(aiMsgIndex)
        if (targetMessage) {
          targetMessage.toolStatus = statusText
        }
      }
      return true
    }
    if (type === 'agent_start') {
      const agentName = (messageObj.agentName as string) || ''
      if (agentName) {
        const targetMessage = ensureToolState(aiMsgIndex)
        if (targetMessage) {
          targetMessage.currentAgent = agentName
        }
      }
      return true
    }
    if (type === 'workflow_event') {
      handleWorkflowEvent(messageObj, aiMsgIndex)
      return true
    }
    if (type === 'done') {
      // done 收尾事件；由 eventSource 'done' listener 统一处理
      return true
    }
    // 未知 type：返回 false 让调用方走兜底（静默忽略）
    return false
  }

  const parseAskUserStructuredPayload = (
    argumentsData?: string | Record<string, unknown>,
  ): PlanningQuestionSet | null => {
    if (!argumentsData) return null
    try {
      let argsObj: Record<string, unknown>
      if (typeof argumentsData === 'string') {
        argsObj = JSON.parse(argumentsData)
      } else {
        argsObj = argumentsData
      }
      const questionSetId =
        (argsObj.questionSetId as string) ||
        ((argsObj.questions as Array<{ id?: string }> | undefined)?.[0]?.id ?? 'qs_legacy')
      const stage = (argsObj.stage as string) || ''
      const protocolVersion = Number(argsObj.protocolVersion || 1)
      const rawQuestions = Array.isArray(argsObj.questions) ? (argsObj.questions as Array<Record<string, unknown>>) : []
      const questions: PlanningQuestion[] = rawQuestions.map((q) => {
        const promptText = String(q.prompt || q.question || '')
        // 兜底归一化 inputType：协议值是 single_select / multi_select。
        // 后端已对非法值归一化并拒绝 text，但前端再做一次防御，
        // 防止后端漏处理时直接把 single_choice / select 等变体显示成"无选项"。
        const rawInputType = String(q.inputType || '').toLowerCase()
        let inputType: PlanningQuestion['inputType']
        if (rawInputType === 'multi_select' || rawInputType === 'multi' || rawInputType === 'multiple' || rawInputType.includes('multi')) {
          inputType = 'multi_select'
        } else {
          inputType = 'single_select'
        }
        return {
          id: String(q.id || ''),
          prompt: promptText,
          question: promptText,
          inputType,
          required: q.required !== false,
          reason: (q.reason as string) || '',
          placeholder: (q.placeholder as string) || '',
          options: Array.isArray(q.options)
            ? (q.options as Array<Record<string, unknown>>).map((opt) => ({
                id: String(opt.id || opt.value || opt.label || ''),
                label: String(opt.label || opt.id || opt.value || ''),
                description: (opt.description as string) || '',
                recommended: Boolean(opt.recommended),
              }))
            : [],
        }
      })
      return { questionSetId, stage, protocolVersion, questions }
    } catch (e) {
      console.warn('[ask_user] parseAskUserStructuredPayload failed', argumentsData, e)
      return null
    }
  }

  const parseAskUserArgs = (argumentsData?: string | Record<string, unknown>) => {
    const payload = parseAskUserStructuredPayload(argumentsData)
    if (!payload) return null
    const first = payload.questions[0]
    if (!first) return null
    return {
      question: first.prompt,
      inputType: first.inputType,
      options: (first.options || []).map((o) => o.id),
    }
  }

  const handleWorkflowEvent = (eventData: Record<string, unknown>, _aiMsgIndex: number) => {
    const eventType = eventData.event as string
    const data = (eventData.data || {}) as Record<string, unknown>

    if (eventType === 'workflow_completed') {
      onAppUpdate?.({ codeGenType: data.codeGenType as string | undefined })
    }
  }

  return {
    generating,
    streamWarning,
    startSSE,
    stopSSE,
    resumeSSE,
  }
}
