<template>
  <div class="chat-message-list" ref="listRef">
    <div
      v-for="(msg, index) in messages"
      :key="index"
      :class="['message-item', msg.role === 'user' ? 'user-msg' : 'ai-msg']"
    >
      <a-avatar :src="msg.role === 'user' ? userAvatar : '/ai-avatar.png'" />
      <div class="message-body">
        <template v-if="msg.role === 'ai' && getPlanningData(index)">
          <PlanningForm
            v-if="getPlanningData(index)!.planningType === 'clarification' && (getPlanningData(index) as Extract<PlanningData, { planningType: 'clarification' }>).questions"
            :questions="(getPlanningData(index) as Extract<PlanningData, { planningType: 'clarification' }>).questions"
            :readonly-answers="getPlanningAnswers(index)"
            @submit="(answers: Record<string, string>) => $emit('planningSubmit', answers)"
            @skip="$emit('planningSkip', index)"
          />
          <PlanConfirmationCard
            v-else-if="getPlanningData(index)!.planningType === 'plan_confirmation' && (getPlanningData(index) as Extract<PlanningData, { planningType: 'plan_confirmation' }>).outline"
            :outline="(getPlanningData(index) as Extract<PlanningData, { planningType: 'plan_confirmation' }>).outline"
            @confirm="$emit('planConfirm', index)"
            @cancel="$emit('planningSkip', index)"
          />
        </template>
        <div v-else class="message-content">
          <template v-if="msg.role === 'ai'">
            <template v-for="parsed in [parseAiMessage(msg.content, msg.toolEvents || [])]" :key="`parsed-${index}`">
              <div v-if="parsed.aiText" class="message-text" v-html="renderMarkdown(parsed.aiText)"></div>
              <details v-if="parsed.toolEvents.length" class="tool-call-card">
                <summary class="tool-call-summary">
                  <span class="tool-call-title">工具调用（{{ parsed.toolEvents.length }}）</span>
                  <span class="tool-call-hint">点击查看执行详情</span>
                </summary>
                <div class="tool-call-list">
                  <div
                    v-for="(eventItem, toolIndex) in parsed.toolEvents"
                    :key="`tool-${index}-${toolIndex}`"
                    class="tool-call-item"
                  >
                    <span :class="['tool-call-tag', eventItem.type]">
                      {{
                        eventItem.type === 'request'
                          ? '调用中'
                          : eventItem.type === 'executed'
                            ? '已完成'
                            : '进行中'
                      }}
                    </span>
                    <span class="tool-call-text">{{ eventItem.text }}</span>
                  </div>
                </div>
              </details>
            </template>
          </template>
          <div v-else class="message-text" v-html="renderMarkdown(msg.content)"></div>
        </div>
      </div>
    </div>
    <div v-if="generating" class="generating-indicator"><LoadingOutlined /> AI 正在思考并生成代码...</div>

    <div v-if="streamWarning" class="stream-warning">
      <a-alert type="warning" show-icon :message="streamWarning" />
      <a-button type="link" size="small" @click="$emit('reloadSession')">重新加载当前会话</a-button>
    </div>

    <div v-if="selectedElement" class="selected-element-panel">
      <a-alert type="info" show-icon>
        <template #message>当前选中元素</template>
        <template #description>
          <div class="selected-element-content">
            <div>标签：{{ selectedElement.tagName }}</div>
            <div>页面路径：{{ selectedElement.pagePath || '/' }}</div>
            <div>选择器：{{ selectedElement.selector || '未生成' }}</div>
            <div>文本：{{ selectedElement.textContent || '（无可见文本）' }}</div>
          </div>
        </template>
        <template #action>
          <a-button size="small" type="link" @click="$emit('clearSelectedElement')">清除</a-button>
        </template>
      </a-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { LoadingOutlined } from '@ant-design/icons-vue'
import PlanningForm from '@/components/PlanningForm.vue'
import PlanConfirmationCard from '@/components/PlanConfirmationCard.vue'

export interface ToolEvent {
  type: 'request' | 'executed' | 'status'
  text: string
}

export interface ChatMessage {
  role: 'user' | 'ai'
  content: string
  status?: string
  toolEvents?: ToolEvent[]
  planning?: PlanningQuestionSet
}

export interface ElementInfo {
  tagName: string
  pagePath?: string
  selector?: string
  textContent?: string
  [key: string]: unknown
}

type PlanningOption = {
  id?: string
  value?: string
  label: string
  description?: string
  recommended?: boolean
}

type PlanningQuestion = {
  id: string
  prompt?: string
  question: string
  inputType: 'single_select' | 'multi_select'
  required: boolean
  options?: PlanningOption[]
  reason?: string
  placeholder?: string
}

type PlanningQuestionSet = {
  questionSetId: string
  stage?: string
  protocolVersion?: number
  questions: PlanningQuestion[]
}

type PlanningData =
  | {
      planningType: 'clarification'
      questionSetId?: string
      questions: PlanningQuestion[]
      // 兼容旧字段
      question?: string
      inputType?: string
      options?: PlanningOption[]
      required?: boolean
    }
  | { planningType: 'plan_confirmation'; outline: PlanOutline; title?: string }

type PlanOutline = {
  title: string
  summary: string
  steps: string[]
  risks: string[]
  assumptions: string[]
}

const PLANNING_TAG_RE = /<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>/

const props = withDefaults(
  defineProps<{
    messages: ChatMessage[]
    generating?: boolean
    streamWarning?: string
    userAvatar?: string
    selectedElement?: ElementInfo | null
  }>(),
  {
    generating: false,
    streamWarning: '',
    userAvatar: '',
    selectedElement: null,
  },
)

defineEmits<{
  planningSubmit: [answers: Record<string, string>]
  planningSkip: [index: number]
  planConfirm: [index: number]
  reloadSession: []
  clearSelectedElement: []
}>()

const listRef = ref<HTMLElement>()

function getPlanningData(index: number): PlanningData | null {
  const msg = props.messages[index]
  if (!msg || msg.role !== 'ai') return null

  // 优先使用结构化 planning 字段（Phase 3）
  if (msg.planning && msg.planning.questions && msg.planning.questions.length > 0) {
    return {
      planningType: 'clarification',
      questionSetId: msg.planning.questionSetId,
      questions: msg.planning.questions.map((q) => ({
        id: q.id,
        question: q.question,
        inputType: q.inputType,
        required: q.required,
        options: q.options || [],
        reason: q.reason,
        placeholder: q.placeholder,
      })),
    }
  }

  // 回退到旧的 <planning> 标签解析（历史消息兼容）
  const match = msg.content.match(PLANNING_TAG_RE)
  if (!match) return null
  try {
    const data = JSON.parse(match[2])
    return { planningType: match[1] as PlanningData['planningType'], ...data }
  } catch {
    return null
  }
}

function getPlanningAnswers(index: number): Record<string, string> | null {
  const data = getPlanningData(index)
  if (!data || data.planningType !== 'clarification') return null
  const nextUserMsg = props.messages.slice(index + 1).find((m) => m.role === 'user')
  if (!nextUserMsg) return null
  const answers: Record<string, string> = {}
  for (const q of data.questions) {
    // 优先按 question.id 精确匹配；保留旧 question 文本匹配作为兜底
    const direct = nextUserMsg.content.match(new RegExp(`\\[\\s*${q.id}\\s*[：:]\\s*([^\\n]+)`, 'i'))
    if (direct) {
      answers[q.id] = direct[1].trim()
      continue
    }
    const escapedQ = q.question.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const answerRe = new RegExp(`${escapedQ}\\s*[：:]\\s*答[：:]\\s*(.+?)(?:\\n|$)`, 'i')
    const qaMatch = nextUserMsg.content.match(answerRe)
    if (qaMatch) {
      answers[q.id] = qaMatch[1].trim()
    }
  }
  return Object.keys(answers).length > 0 ? answers : null
}

function parseAiMessage(
  content: string,
  presetToolEvents: ToolEvent[] = [],
): { aiText: string; toolEvents: ToolEvent[] } {
  if (presetToolEvents.length > 0) {
    return {
      aiText: stripToolEventLines(content).trim(),
      toolEvents: presetToolEvents,
    }
  }
  const lines = content.split('\n')
  const aiTextLines: string[] = []
  const toolEvents: ToolEvent[] = []

  lines.forEach((line) => {
    const trimmedLine = line.trim()
    if (trimmedLine === 'waiting_for_user' || trimmedLine.startsWith('Agent loop completed:')) {
      return
    }
    if (trimmedLine.startsWith('[状态]')) {
      toolEvents.push({ type: 'status', text: trimmedLine.replace('[状态]', '').trim() || '处理中' })
      return
    }
    if (trimmedLine.startsWith('[工具调用]')) {
      toolEvents.push({ type: 'request', text: trimmedLine.replace('[工具调用]', '').trim() || '执行工具调用' })
      return
    }
    if (trimmedLine.startsWith('[工具完成]')) {
      toolEvents.push({ type: 'executed', text: trimmedLine.replace('[工具完成]', '').trim() || '工具执行成功' })
      return
    }
    if (trimmedLine.startsWith('准备写入文件')) {
      toolEvents.push({ type: 'request', text: trimmedLine })
      return
    }
    if (trimmedLine.startsWith('已写入文件')) {
      toolEvents.push({ type: 'executed', text: trimmedLine })
      return
    }
    aiTextLines.push(line)
  })

  return { aiText: aiTextLines.join('\n').trim(), toolEvents }
}

function stripToolEventLines(content: string) {
  return content
    .replace(/\n?waiting_for_user\n?/g, '')
    .replace(/\n?Agent loop completed:.*?\n?/g, '')
    .split('\n')
    .filter((line) => {
      const trimmedLine = line.trim()
      return !(
        trimmedLine.startsWith('[工具调用]') ||
        trimmedLine.startsWith('[工具完成]') ||
        trimmedLine.startsWith('[状态]') ||
        trimmedLine.startsWith('准备写入文件') ||
        trimmedLine.startsWith('已写入文件')
      )
    })
    .join('\n')
}

const renderMarkdown = (text: string) => {
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight
    }
  })
}

// 消息变化时自动滚动
watch(
  () => props.messages.length,
  () => scrollToBottom(),
)

defineExpose({ scrollToBottom, listRef })
</script>

<style scoped>
.chat-message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message-item {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.message-item.user-msg {
  flex-direction: row-reverse;
}

.message-item.user-msg .message-body {
  align-items: flex-end;
}

.message-body {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-content {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.user-msg .message-content {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.ai-msg .message-content {
  background: var(--color-background);
  color: var(--color-text);
  border-bottom-left-radius: 4px;
}

.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 13px;
}

.user-msg .message-text :deep(code) {
  background: rgba(255, 255, 255, 0.2);
}

.tool-call-card {
  margin-top: 8px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.tool-call-summary {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  background: var(--color-background);
}

.tool-call-title {
  font-weight: 500;
  color: var(--color-text-secondary);
}

.tool-call-hint {
  color: var(--color-text-tertiary);
}

.tool-call-list {
  padding: 8px 12px;
}

.tool-call-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
}

.tool-call-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.tool-call-tag.request {
  background: #e6f7ff;
  color: #1890ff;
}

.tool-call-tag.executed {
  background: #f6ffed;
  color: #52c41a;
}

.tool-call-tag.status {
  background: #fff7e6;
  color: #fa8c16;
}

.tool-call-text {
  color: var(--color-text-secondary);
}

.generating-indicator {
  text-align: center;
  padding: 16px;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.stream-warning {
  padding: 0 16px 8px;
}

.selected-element-panel {
  padding: 8px 16px;
}

.selected-element-content {
  font-size: 12px;
  line-height: 1.8;
}
</style>
