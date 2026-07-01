import { ref, type Ref } from 'vue'
import { message as antMessage } from 'ant-design-vue'
import { ssePost } from '@/utils/sseRequest'
import { extractBusinessChunk, splitConcatenatedJsonObjects } from './sseParser'
import { formatToolCallDescription } from '@/utils/chatMessageTooling'
import { isStreamControlMessage } from '@/utils/streamControlMessage'
import type { ChatMessage, ToolCallRecord } from '@/types/chat'

/** 工具调用详情（右侧面板用） */
export interface ToolCallDetail {
  id: string
  name: string
  arguments: string
  result?: string
  status: 'running' | 'completed' | 'failed'
  startTime: number
  endTime?: number
  duration?: number
}

export interface PlaygroundChatOptions {
  messages: Ref<ChatMessage[]>
  enabledTools: Ref<string[]>
  onToolCallUpdate: (calls: ToolCallDetail[]) => void
}

/**
 * Playground SSE 流式对话 composable
 * 与 useSSEChat 类似，但请求走 /playground/chat/stream，不需要 appId/sessionId
 */
export function usePlaygroundChat(options: PlaygroundChatOptions) {
  const { messages, enabledTools, onToolCallUpdate } = options

  const generating = ref(false)
  const streamWarning = ref('')
  let currentAbortController: AbortController | null = null

  // 当前消息的工具调用详情列表
  let currentToolCalls: ToolCallDetail[] = []

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
    return { event: eventName, data: dataLines.join('\n') }
  }

  const readSseStream = async (
    response: Response,
    onFrame: (eventName: string, data: string) => boolean | void,
  ) => {
    const reader = response.body?.getReader()
    if (!reader) throw new Error('SSE 响应流为空')
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        if (buffer.trim()) {
          const parsed = parseSseEvent(buffer.trim())
          if (onFrame(parsed.event, parsed.data)) return
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

  const startPlaygroundSSE = (userMessage: string) => {
    generating.value = true
    streamWarning.value = ''
    currentToolCalls = []
    let streamCompleted = false
    let hasBusinessError = false

    const aiMsgIndex = messages.value.length
    messages.value.push({ role: 'ai', content: '', status: 'running', toolStatus: '', toolCalls: [] })

    const controller = new AbortController()
    currentAbortController = controller

    void (async () => {
      try {
        const response = await ssePost({
          path: '/playground/chat/stream',
          body: {
            message: userMessage,
            enabledTools: enabledTools.value,
          },
          signal: controller.signal,
        })

        await readSseStream(response, (eventName, data) => {
          if (eventName === 'meta') return false

          if (eventName === 'business-error') {
            hasBusinessError = true
            try {
              const payload = JSON.parse(data)
              const errorMsg = payload.message || '操作失败'
              messages.value[aiMsgIndex].content += `\n\n[错误] ${errorMsg}`
              messages.value[aiMsgIndex].status = 'failed'
              antMessage.error(errorMsg)
            } catch {
              antMessage.error('操作失败')
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
            appendStreamChunk(aiMsgIndex, fragment)
          }
          return false
        })

        if (streamCompleted) {
          finalizeGeneration(aiMsgIndex, true)
          return
        }
        if (!hasBusinessError && !controller.signal.aborted) {
          streamWarning.value = '连接中断，本次 AI 输出可能不完整。'
          messages.value[aiMsgIndex].status = 'failed'
          antMessage.warning('连接中断，已停止本次生成')
        }
        finalizeGeneration(aiMsgIndex, false)
      } catch (error) {
        if (controller.signal.aborted) return
        const errorText = error instanceof Error ? error.message : String(error)
        messages.value[aiMsgIndex].status = 'failed'
        if (errorText) {
          messages.value[aiMsgIndex].content += `\n\n[错误] ${errorText}`
        }
        antMessage.error('操作失败')
        finalizeGeneration(aiMsgIndex, false)
      }
    })()
  }

  const finalizeGeneration = (aiMsgIndex: number, streamCompleted: boolean) => {
    currentAbortController = null
    if (streamCompleted) streamWarning.value = ''
    if (!generating.value) return
    generating.value = false
    if (messages.value[aiMsgIndex]) {
      messages.value[aiMsgIndex].status = streamCompleted ? 'success' : 'failed'
    }
  }

  const appendStreamChunk = (aiMsgIndex: number, chunk: string) => {
    if (!chunk) return

    const processJson = (jsonStr: string): boolean => {
      try {
        const messageObj = JSON.parse(jsonStr)
        if (messageObj && typeof messageObj === 'object' && typeof messageObj.type === 'string') {
          return dispatchMessageEvent(messageObj, aiMsgIndex)
        }
        return false
      } catch {
        return false
      }
    }

    if (processJson(chunk)) return

    const fragments = splitConcatenatedJsonObjects(chunk)
    if (fragments.length > 1) {
      let anyProcessed = false
      for (const fragment of fragments) {
        if (processJson(fragment)) anyProcessed = true
      }
      if (anyProcessed) return
    }

    // 纯文本追加
    if (messages.value[aiMsgIndex]) {
      messages.value[aiMsgIndex].content += chunk
    }
  }

  const ensureToolState = (aiMsgIndex: number) => {
    const targetMessage = messages.value[aiMsgIndex]
    if (!targetMessage) return null
    if (!targetMessage.toolCalls) targetMessage.toolCalls = []
    if (!targetMessage.toolStatus) targetMessage.toolStatus = ''
    return targetMessage as ChatMessage & { toolCalls: ToolCallRecord[]; toolStatus: string }
  }

  const dispatchMessageEvent = (messageObj: Record<string, unknown>, aiMsgIndex: number): boolean => {
    const type = messageObj.type

    if (type === 'ai_response') {
      const data = (messageObj.data as string) || ''
      if (!isStreamControlMessage(data) && messages.value[aiMsgIndex]) {
        messages.value[aiMsgIndex].content += data
      }
      return true
    }

    if (type === 'tool_request') {
      const targetMessage = ensureToolState(aiMsgIndex)
      if (!targetMessage) return true
      const id = (messageObj.id as string) || ''
      const name = (messageObj.name as string) || ''
      const args = (messageObj.arguments as string) || ''
      const description = formatToolCallDescription(name, args, 'request', undefined)
      targetMessage.toolCalls.push({
        type: 'request',
        id,
        name,
        description,
        arguments: args,
        status: 'running',
        timestamp: Date.now(),
      })
      targetMessage.toolStatus = description

      // 添加到工具详情列表
      currentToolCalls.push({
        id,
        name,
        arguments: args,
        status: 'running',
        startTime: Date.now(),
      })
      onToolCallUpdate([...currentToolCalls])
      return true
    }

    if (type === 'tool_executed') {
      const targetMessage = ensureToolState(aiMsgIndex)
      if (!targetMessage) return true
      const toolId = (messageObj.id as string) || ''
      const name = (messageObj.name as string) || ''
      const args = (messageObj.arguments as string) || ''
      const result = (messageObj.result as string) || ''

      // 更新 ChatMessage 中的 toolCalls
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
        })
      }

      // 更新工具详情列表
      const detailIdx = currentToolCalls.findIndex((tc) => tc.id === toolId)
      if (detailIdx >= 0) {
        const now = Date.now()
        currentToolCalls[detailIdx].result = result
        currentToolCalls[detailIdx].status = 'completed'
        currentToolCalls[detailIdx].endTime = now
        currentToolCalls[detailIdx].duration = now - currentToolCalls[detailIdx].startTime
      } else {
        currentToolCalls.push({
          id: toolId,
          name,
          arguments: args,
          result,
          status: 'completed',
          startTime: Date.now() - 100,
          endTime: Date.now(),
          duration: 100,
        })
      }
      onToolCallUpdate([...currentToolCalls])
      return true
    }

    if (type === 'status') {
      const statusText = (messageObj.message as string) || ''
      if (statusText) {
        const targetMessage = ensureToolState(aiMsgIndex)
        if (targetMessage) targetMessage.toolStatus = statusText
      }
      return true
    }

    if (type === 'agent_start') {
      const agentName = (messageObj.agentName as string) || ''
      if (agentName) {
        const targetMessage = ensureToolState(aiMsgIndex)
        if (targetMessage) targetMessage.currentAgent = agentName
      }
      return true
    }

    return false
  }

  const stopPlaygroundSSE = () => {
    if (currentAbortController) {
      currentAbortController.abort()
      currentAbortController = null
    }
    generating.value = false
  }

  return {
    generating,
    streamWarning,
    startPlaygroundSSE,
    stopPlaygroundSSE,
  }
}
