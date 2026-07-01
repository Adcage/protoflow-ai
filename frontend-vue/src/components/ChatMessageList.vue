<template>
  <div class="chat-message-list" ref="listRef">
    <div v-if="hasMore" class="load-more-bar">
      <a-button type="link" size="small" @click="$emit('loadEarlier')">加载更早的消息</a-button>
    </div>
    <div
      v-for="(msg, index) in messages"
      :key="index"
      :class="['message-item', msg.role === 'user' ? 'user-msg' : 'ai-msg']"
    >
      <a-avatar :src="msg.role === 'user' ? userAvatar : '/ai-avatar.png'" />
      <div class="message-body">
        <template v-if="msg.role === 'ai' && getPlanningData(index)">
          <!-- 工具状态栏 -->
          <div v-if="shouldShowTooling(msg)" class="message-tooling" @click.stop>
            <button
              type="button"
              class="message-tool-summary"
              :class="{ 'is-interactive': hasToolLog(msg) }"
              @click.stop="toggleToolLog(index)"
            >
              <span class="message-tool-summary-dot" :class="getSummaryDotClass(msg)"></span>
              <span class="message-tool-summary-text">{{ getMessageToolSummary(msg) }}</span>
              <span v-if="msg.toolCalls?.length" class="message-tool-summary-meta">
                {{ msg.toolCalls.length }} 次工具调用
              </span>
              <span v-if="getMessageAgentSummary(msg)" class="message-tool-summary-agent">
                {{ getMessageAgentSummary(msg) }}
              </span>
              <span v-if="hasToolLog(msg)" class="message-tool-summary-arrow">
                {{ isToolLogExpanded(index, msg) ? '收起' : '展开' }}
              </span>
            </button>
            <div v-if="hasToolLog(msg) && isToolLogExpanded(index, msg)" class="message-tool-log">
              <div
                v-for="toolCall in msg.toolCalls"
                :key="toolCall.id"
                class="message-tool-log-row"
              >
                <span
                  class="message-tool-log-dot"
                  :class="{
                    'is-running': toolCall.status === 'running',
                    'is-completed': toolCall.status === 'completed',
                    'is-failed': toolCall.status === 'failed',
                  }"
                ></span>
                <div class="message-tool-log-copy">
                  <div class="message-tool-log-heading">
                    <span v-if="toolCall.agentName" class="message-tool-log-badge">{{ getAgentBadgeText(toolCall.agentName) }}</span>
                    <span class="message-tool-log-name">{{ getToolCallName(toolCall) }}</span>
                  </div>
                  <span class="message-tool-log-desc">{{ toolCall.description }}</span>
                </div>
                <span class="message-tool-log-status">{{ formatToolCallStatus(toolCall.status) }}</span>
              </div>
            </div>
          </div>
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
        <template v-else-if="msg.role === 'ai'">
          <div v-if="shouldShowTooling(msg)" class="message-tooling" @click.stop>
            <button
              type="button"
              class="message-tool-summary"
              :class="{ 'is-interactive': hasToolLog(msg) }"
              @click.stop="toggleToolLog(index)"
            >
              <span class="message-tool-summary-dot" :class="getSummaryDotClass(msg)"></span>
              <span class="message-tool-summary-text">{{ getMessageToolSummary(msg) }}</span>
              <span v-if="msg.toolCalls?.length" class="message-tool-summary-meta">
                {{ msg.toolCalls.length }} 次工具调用
              </span>
              <span v-if="getMessageAgentSummary(msg)" class="message-tool-summary-agent">
                {{ getMessageAgentSummary(msg) }}
              </span>
              <span v-if="hasToolLog(msg)" class="message-tool-summary-arrow">
                {{ isToolLogExpanded(index, msg) ? '收起' : '展开' }}
              </span>
            </button>
            <div v-if="hasToolLog(msg) && isToolLogExpanded(index, msg)" class="message-tool-log">
              <div
                v-for="toolCall in msg.toolCalls"
                :key="toolCall.id"
                class="message-tool-log-row"
              >
                <span
                  class="message-tool-log-dot"
                  :class="{
                    'is-running': toolCall.status === 'running',
                    'is-completed': toolCall.status === 'completed',
                    'is-failed': toolCall.status === 'failed',
                  }"
                ></span>
                <div class="message-tool-log-copy">
                  <div class="message-tool-log-heading">
                    <span v-if="toolCall.agentName" class="message-tool-log-badge">{{ getAgentBadgeText(toolCall.agentName) }}</span>
                    <span class="message-tool-log-name">{{ getToolCallName(toolCall) }}</span>
                  </div>
                  <span class="message-tool-log-desc">{{ toolCall.description }}</span>
                </div>
                <span class="message-tool-log-status">{{ formatToolCallStatus(toolCall.status) }}</span>
              </div>
            </div>
          </div>
          <div class="message-content">
            <template v-for="parsed in [parseAiMessage(msg.content)]" :key="`parsed-${index}`">
              <div
                v-if="parsed"
                class="message-text"
                v-html="renderMarkdown(parsed)"
                @click="handleMessageTextClick"
              ></div>
            </template>
          </div>
        </template>
        <template v-else>
          <div v-if="getImageAttachments(msg.attachments).length > 0" class="user-message-media attachments-preview attachments-preview-images">
            <div class="user-message-media-stack">
              <button
                v-for="att in getImageAttachments(msg.attachments)"
                :key="att.id"
                type="button"
                class="attachment-image-card"
                @click="openImagePreview(att.url)"
              >
                <img :src="att.url" :alt="att.fileName" class="attachment-image-thumb" />
              </button>
            </div>
          </div>
          <div v-if="getFileAttachments(msg.attachments).length > 0" class="attachments-preview attachments-preview-files">
            <div v-for="att in getFileAttachments(msg.attachments)" :key="att.id" class="attachment-chip">
              <PaperClipOutlined />
              <span class="attachment-label">{{ att.fileName }}</span>
            </div>
          </div>
          <div
            v-if="hasDisplayMessageContent(msg.content, msg.attachments)"
            class="message-content user-message-bubble"
          >
            <div
              class="message-text"
              v-html="renderMarkdown(getDisplayMessageContent(msg.content, msg.attachments))"
            ></div>
          </div>
        </template>
      </div>
    </div>
    <div v-if="generating" class="generating-indicator"><LoadingOutlined /> AI 正在思考并生成内容...</div>

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
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { LoadingOutlined, PaperClipOutlined } from '@ant-design/icons-vue'
import MarkdownIt from 'markdown-it'
import PlanningForm from '@/components/PlanningForm.vue'
import PlanConfirmationCard from '@/components/PlanConfirmationCard.vue'
import { getDisplayMessageContent } from '@/utils/chatAttachmentDisplay'
import { normalizeLooseMarkdown } from '@/utils/chatMarkdown'
import {
  buildMessageAgentSummary,
  buildMessageToolSummary,
  getAgentBadgeText,
  getToolDisplayName,
  resolveToolLogExpanded,
} from '@/utils/chatMessageTooling'
import type { AttachmentInfo } from '@/utils/chatStreamRequest'
import type { ChatMessage, PlanningQuestion, PlanningQuestionSet } from '@/types/chat'

export interface ElementInfo {
  tagName: string
  pagePath?: string
  selector?: string
  textContent?: string
  [key: string]: unknown
}

type PlanningData =
  | {
      planningType: 'clarification'
      questionSetId?: string
      questions: PlanningQuestion[]
      // 兼容旧字段
      question?: string
      inputType?: string
      options?: PlanningQuestion['options']
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
    hasMore?: boolean
  }>(),
  {
    generating: false,
    streamWarning: '',
    userAvatar: '',
    selectedElement: null,
    hasMore: false,
  },
)

defineEmits<{
  planningSubmit: [answers: Record<string, string>]
  planningSkip: [index: number]
  planConfirm: [index: number]
  reloadSession: []
  clearSelectedElement: []
  loadEarlier: []
}>()

const listRef = ref<HTMLElement>()
const expandedToolLogs = ref<Record<number, boolean>>({})

function closeAllToolLogs() {
  const nextState: Record<number, boolean> = {}
  props.messages.forEach((msg, index) => {
    if (hasToolLog(msg)) {
      nextState[index] = false
    }
  })
  expandedToolLogs.value = nextState
}

function handleDocumentClick() {
  closeAllToolLogs()
}

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
  // 优先从 planning.answers 取（JSON 格式提交后直接存储在 AI 消息上）
  const msg = props.messages[index]
  if (msg?.planning?.answers && Object.keys(msg.planning.answers).length > 0) {
    return msg.planning.answers
  }
  // 回退：从下一条用户消息解析
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

function parseAiMessage(content: string): string {
  return stripLegacyToolMarkers(content).trim()
}

function stripLegacyToolMarkers(content: string) {
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

function getImageAttachments(attachments?: AttachmentInfo[]) {
  return (attachments || []).filter((att) => att.mimeType.startsWith('image/'))
}

function getFileAttachments(attachments?: AttachmentInfo[]) {
  return (attachments || []).filter((att) => !att.mimeType.startsWith('image/'))
}

function hasDisplayMessageContent(content: string, attachments?: AttachmentInfo[]) {
  return getDisplayMessageContent(content, attachments).trim().length > 0
}

function getMessageToolSummary(msg: ChatMessage) {
  return buildMessageToolSummary({
    status: msg.status,
    toolStatus: msg.toolStatus,
    toolCalls: msg.toolCalls,
  })
}

function getMessageAgentSummary(msg: ChatMessage) {
  return buildMessageAgentSummary(msg.toolCalls, msg.agentName || msg.currentAgent)
}

function shouldShowTooling(msg: ChatMessage) {
  return msg.role === 'ai' && (getMessageToolSummary(msg).length > 0 || hasToolLog(msg))
}

function hasToolLog(msg: ChatMessage) {
  return Boolean(msg.toolCalls && msg.toolCalls.length > 0)
}

function isToolLogExpanded(index: number, msg: ChatMessage) {
  return resolveToolLogExpanded(expandedToolLogs.value[index], msg.status)
}

function toggleToolLog(index: number) {
  if (!props.messages[index] || !hasToolLog(props.messages[index])) return
  const nextExpanded = !isToolLogExpanded(index, props.messages[index])
  expandedToolLogs.value = { [index]: nextExpanded }
}

function formatToolCallStatus(status: 'running' | 'completed' | 'failed') {
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  return '进行中'
}

function getToolCallName(toolCall: { name?: string; arguments?: string }) {
  return getToolDisplayName(toolCall.name, toolCall.arguments)
}

function getSummaryDotClass(msg: ChatMessage) {
  if (msg.status === 'failed') return 'is-failed'
  if (msg.status === 'running') return 'is-running'
  return 'is-completed'
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

const renderMarkdown = (text: string) => {
  return md
    .render(normalizeLooseMarkdown(text))
    // 仅恢复被 markdown-it 安全转义的 <br> 标签，其他 HTML 继续保持转义态
    .replace(/&lt;br\s*\/?&gt;/gi, '<br />')
}

/** 通过自定义事件打开图片预览（绕过 composable 模块隔离问题） */
function openImagePreview(url: string) {
  window.dispatchEvent(new CustomEvent('image-preview-open', { detail: url }))
}

/** 事件委托：点击 v-html 渲染的 <img> 时打开图片预览 */
function handleMessageTextClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.tagName === 'IMG') {
    const src = (target as HTMLImageElement).src
    if (src) {
      e.preventDefault()
      openImagePreview(src)
    }
  }
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

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
})

defineExpose({ scrollToBottom, listRef })
</script>

<style scoped>
.chat-message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 18px 18px;
  background:
    radial-gradient(circle at top, rgba(200, 90, 62, 0.06), transparent 24%),
    linear-gradient(180deg, rgba(248, 244, 240, 0.82), rgba(253, 249, 245, 0.94));
}

.message-item {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
}

.message-item.user-msg {
  flex-direction: row-reverse;
}

.attachments-preview {
  margin-bottom: 10px;
}

.attachments-preview-images {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.attachments-preview-files {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.attachment-image-card {
  display: block;
  width: clamp(64px, 14vw, 112px);
  overflow: hidden;
  padding: 0;
  border: none;
  border-radius: 18px;
  background: transparent;
  box-shadow: none;
  cursor: pointer;
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.attachment-image-card:hover {
  transform: translateY(-1px);
}

.attachment-image-thumb {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 18px;
  box-shadow:
    0 10px 26px rgba(0, 0, 0, 0.12),
    0 0 0 1px rgba(255, 255, 255, 0.08);
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 18px rgba(28, 24, 21, 0.04);
  cursor: default;
}

.attachment-label {
  font-size: 12px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.message-item.user-msg .message-body {
  align-items: flex-end;
}

.message-item.user-msg .attachments-preview-images {
  justify-content: flex-end;
}

.user-message-media {
  width: 100%;
}

.user-message-media-stack {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}

.message-item.user-msg .attachment-image-card {
  background: transparent;
}

.user-message-bubble {
  align-self: flex-end;
  max-width: min(420px, 100%);
}

.message-body {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-tooling {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 2px;
}

.message-tool-summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  max-width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  color: #7b6e62;
  font-size: 12px;
  line-height: 1.5;
  text-align: left;
}

.message-tool-summary.is-interactive {
  cursor: pointer;
}

.message-tool-summary-dot,
.message-tool-log-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}

.message-tool-summary-dot.is-running,
.message-tool-log-dot.is-running {
  background: #d4944c;
  box-shadow: 0 0 0 4px rgba(212, 148, 76, 0.14);
}

.message-tool-summary-dot.is-completed,
.message-tool-log-dot.is-completed {
  background: #4f9d69;
}

.message-tool-summary-dot.is-failed,
.message-tool-log-dot.is-failed {
  background: #d85c4a;
}

.message-tool-summary-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-tool-summary-meta,
.message-tool-summary-arrow {
  color: #a08f81;
  white-space: nowrap;
}

.message-tool-summary-agent {
  color: #8a7a6e;
  white-space: nowrap;
}

.message-tool-summary-agent::before {
  content: '·';
  margin-right: 6px;
  color: #b4a396;
}

.message-tool-log {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 24;
  width: min(360px, calc(100vw - 112px));
  max-width: calc(100vw - 112px);
  max-height: 260px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(220, 207, 196, 0.7);
  border-radius: 14px;
  background: rgba(255, 252, 249, 0.96);
  box-shadow:
    0 18px 36px rgba(28, 24, 21, 0.12),
    0 0 0 1px rgba(255, 255, 255, 0.42);
  backdrop-filter: blur(10px);
}

.message-tool-log-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.message-tool-log-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
  flex: 1;
}

.message-tool-log-heading {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-wrap: wrap;
}

.message-tool-log-name {
  font-size: 12px;
  font-weight: 600;
  color: #4e4036;
}

.message-tool-log-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #eef2ff;
  color: #6366f1;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.message-tool-log-desc {
  font-size: 12px;
  color: #7b6e62;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-tool-log-status {
  font-size: 11px;
  color: #9f8d80;
  white-space: nowrap;
}

.message-content {
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  box-shadow: 0 10px 24px rgba(28, 24, 21, 0.05);
}

.user-msg .message-content {
  background: linear-gradient(135deg, var(--color-primary), #24384b);
  color: var(--color-text-on-cta);
  border: 1px solid rgba(28, 45, 61, 0.12);
  border-bottom-right-radius: 4px;
}

.ai-msg .message-content {
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text);
  border-left: 3px solid var(--color-cta);
  border: 1px solid rgba(220, 207, 196, 0.7);
  border-left-width: 4px;
  border-bottom-left-radius: 4px;
}

.message-text :deep(code) {
  background: rgba(28, 24, 21, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 13px;
}

.message-text :deep(pre) {
  background: rgba(28, 24, 21, 0.045);
  padding: 8px 12px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-text :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 13px;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4) {
  margin: 12px 0 6px;
  font-weight: 600;
  line-height: 1.4;
  font-family: var(--font-heading);
}

.message-text :deep(h1) { font-size: 18px; }
.message-text :deep(h2) { font-size: 16px; }
.message-text :deep(h3) { font-size: 15px; }
.message-text :deep(h4) { font-size: 14px; }

.message-text :deep(ul),
.message-text :deep(ol) {
  padding-left: 20px;
  margin: 6px 0;
}

.message-text :deep(li) {
  margin: 2px 0;
}

.message-text :deep(p) {
  margin: 4px 0;
}

.message-text :deep(table) {
  width: 100%;
  margin: 10px 0;
  border-collapse: collapse;
  overflow: hidden;
  border: 1px solid rgba(220, 207, 196, 0.85);
  border-radius: 10px;
  font-size: 13px;
  background: rgba(255, 252, 249, 0.72);
}

.message-text :deep(th),
.message-text :deep(td) {
  padding: 8px 10px;
  border: 1px solid rgba(220, 207, 196, 0.85);
  vertical-align: top;
  text-align: left;
  word-break: break-word;
}

.message-text :deep(th) {
  background: rgba(245, 236, 228, 0.9);
  font-weight: 600;
}

.message-text :deep(blockquote) {
  border-left: 3px solid var(--color-cta-light);
  padding-left: 10px;
  margin: 8px 0;
  color: var(--color-text-secondary);
}

.message-text :deep(a) {
  color: var(--color-cta);
  text-decoration: none;
}

.message-text :deep(a:hover) {
  text-decoration: underline;
  color: var(--color-cta-hover);
}

.message-text :deep(img) {
  max-width: 100%;
  border-radius: 16px;
  cursor: pointer;
  box-shadow:
    0 10px 24px rgba(0, 0, 0, 0.12),
    0 0 0 1px rgba(255, 255, 255, 0.08);
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.message-text :deep(img:hover) {
  opacity: 0.85;
  transform: translateY(-1px);
}

.user-msg .message-text :deep(code) {
  background: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.95);
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
  padding: 0 2px 12px;
}

.selected-element-content {
  font-size: 12px;
  line-height: 1.8;
}

@media (max-width: 768px) {
  .message-tool-log {
    position: fixed;
    left: 16px;
    right: 16px;
    bottom: 20px;
    top: auto;
    width: auto;
    max-width: none;
    max-height: min(50vh, 320px);
  }
}
</style>
