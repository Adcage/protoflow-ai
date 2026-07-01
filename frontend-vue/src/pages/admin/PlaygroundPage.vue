<template>
  <div class="playground-page">
    <!-- 左栏：工具勾选面板 -->
    <div class="tool-config-panel">
      <div class="panel-header">
        <h3>工具配置</h3>
      </div>
      <div class="tool-list">
        <a-checkbox-group v-model:value="enabledTools" class="tool-checkbox-group">
          <template v-for="cat in toolCategories" :key="cat.key">
            <div class="tool-category-label">{{ cat.label }}</div>
            <div v-for="tool in cat.tools" :key="tool.name" class="tool-item">
              <a-checkbox :value="tool.name">
                <span class="tool-name">{{ tool.displayName }}</span>
                <span class="tool-desc">{{ tool.description }}</span>
              </a-checkbox>
            </div>
          </template>
        </a-checkbox-group>
      </div>
      <div class="tool-actions">
        <a-button size="small" type="link" @click="selectAllTools">全选</a-button>
        <a-button size="small" type="link" @click="deselectAllTools">全不选</a-button>
      </div>
    </div>

    <!-- 中栏：对话区 -->
    <div class="chat-panel">
      <div class="chat-panel-header">
        <div class="chat-panel-header-left">
          <a-tag color="green">Playground</a-tag>
          <span class="tool-count">{{ enabledTools.length }} 工具已启用</span>
        </div>
        <div class="chat-panel-header-right">
          <a-button size="small" @click="handleReset">
            <template #icon><ReloadOutlined /></template>
            新建对话
          </a-button>
        </div>
      </div>
      <ChatMessageList
        ref="chatMessageListRef"
        :messages="messages"
        :generating="generating"
        :stream-warning="streamWarning"
        :user-avatar="loginUserStore.loginUser.userAvatar || ''"
        @planning-submit="() => {}"
        @planning-skip="() => {}"
        @plan-confirm="() => {}"
        @reload-session="() => {}"
        @clear-selected-element="() => {}"
      />
      <ChatInputArea
        ref="chatInputAreaRef"
        :generating="generating"
        :placeholder="'输入指令测试 AI 工具能力...'"
        @send="handleSend"
      />
    </div>

    <!-- 右栏：工具调用详情 -->
    <div class="tool-detail-panel">
      <div class="panel-header">
        <h3>工具调用详情</h3>
        <a-button v-if="toolCallDetails.length > 0" size="small" type="link" @click="toolCallDetails = []">
          清空
        </a-button>
      </div>
      <div class="tool-call-timeline">
        <div v-for="(call, index) in toolCallDetails" :key="index" class="tool-call-item">
          <div class="tool-call-header" @click="toggleToolExpand(index)">
            <span :class="['tool-call-status-dot', call.status]"></span>
            <span class="tool-call-name">{{ call.name }}</span>
            <span v-if="call.duration" class="tool-call-duration">{{ call.duration }}ms</span>
            <span class="tool-call-expand-icon">{{ expandedTools[index] ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedTools[index]" class="tool-call-body">
            <div v-if="call.arguments" class="tool-call-section">
              <span class="section-label">入参</span>
              <pre class="section-content">{{ formatToolArgs(call.arguments) }}</pre>
            </div>
            <div v-if="call.result" class="tool-call-section">
              <span class="section-label">结果</span>
              <pre class="section-content result-content">{{ truncateResult(call.result) }}</pre>
            </div>
          </div>
        </div>
        <div v-if="toolCallDetails.length === 0" class="empty-detail">
          发送消息后，工具调用详情将在此展示
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { message as antMessage } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import ChatMessageList from '@/components/ChatMessageList.vue'
import ChatInputArea from '@/components/ChatInputArea.vue'
import { useLoginUserStore } from '@/stores/LoginUser'
import { usePlaygroundChat, type ToolCallDetail } from '@/composables/usePlaygroundChat'
import { listPlaygroundTools, resetPlayground } from '@/api/playgroundController'
import type { ChatMessage } from '@/types/chat'

const loginUserStore = useLoginUserStore()

// ── 工具配置 ──────────────────────────────────────────────

interface ToolInfo {
  name: string
  displayName: string
  description: string
  category: string
  defaultEnabled: boolean
}

const availableTools = ref<ToolInfo[]>([])
const enabledTools = ref<string[]>([])

const toolCategories = computed(() => {
  const catMap: Record<string, { key: string; label: string; tools: ToolInfo[] }> = {
    file: { key: 'file', label: '文件操作', tools: [] },
    search: { key: 'search', label: '搜索', tools: [] },
    system: { key: 'system', label: '系统', tools: [] },
    interaction: { key: 'interaction', label: '交互', tools: [] },
    knowledge: { key: 'knowledge', label: '知识库', tools: [] },
  }
  for (const tool of availableTools.value) {
    const cat = catMap[tool.category]
    if (cat) {
      cat.tools.push(tool)
    } else {
      // 未知分类归入系统
      catMap.system.tools.push(tool)
    }
  }
  return Object.values(catMap).filter((cat) => cat.tools.length > 0)
})

const selectAllTools = () => {
  enabledTools.value = availableTools.value.map((t) => t.name)
}

const deselectAllTools = () => {
  enabledTools.value = []
}

// ── 对话 ──────────────────────────────────────────────

const messages = ref<ChatMessage[]>([])
const toolCallDetails = ref<ToolCallDetail[]>([])
const expandedTools = reactive<Record<number, boolean>>({})

const chatMessageListRef = ref<InstanceType<typeof ChatMessageList>>()
const chatInputAreaRef = ref<InstanceType<typeof ChatInputArea>>()

const { generating, streamWarning, startPlaygroundSSE, stopPlaygroundSSE } = usePlaygroundChat({
  messages,
  enabledTools,
  onToolCallUpdate: (calls: ToolCallDetail[]) => {
    toolCallDetails.value = calls
  },
})

const handleSend = (msg: string) => {
  if (!msg.trim()) return
  if (enabledTools.value.length === 0) {
    antMessage.warning('请至少启用一个工具')
    return
  }
  // 显式清空输入框（ChatInputArea 内部 emit 后也会清空，这里做兜底）
  chatInputAreaRef.value?.clearInput?.()
  messages.value.push({ role: 'user', content: msg, status: 'success', toolCalls: [] })
  startPlaygroundSSE(msg)
}

const handleReset = async () => {
  if (generating.value) {
    stopPlaygroundSSE()
  }
  try {
    await resetPlayground()
    messages.value = []
    toolCallDetails.value = []
    antMessage.success('已新建对话')
  } catch {
    antMessage.error('重置失败')
  }
}

// ── 工具详情面板 ──────────────────────────────────────────

const toggleToolExpand = (index: number) => {
  expandedTools[index] = !expandedTools[index]
}

const formatToolArgs = (args: string): string => {
  try {
    const parsed = JSON.parse(args)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return args
  }
}

const truncateResult = (result: string): string => {
  if (result.length > 2000) {
    return result.slice(0, 2000) + '\n... (已截断)'
  }
  return result
}

// ── 初始化 ──────────────────────────────────────────────

onMounted(async () => {
  try {
    const res = await listPlaygroundTools()
    if (res.data?.code === 0 && res.data.data) {
      availableTools.value = res.data.data
      // 默认启用 defaultEnabled 的工具
      enabledTools.value = availableTools.value.filter((t: ToolInfo) => t.defaultEnabled).map((t: ToolInfo) => t.name)
    }
  } catch {
    // API 不可用时使用默认列表
    const defaultTools: ToolInfo[] = [
      { name: 'Read', displayName: '读取文件', description: '读取文件或目录内容', category: 'file', defaultEnabled: true },
      { name: 'Write', displayName: '写入文件', description: '创建新文件并写入内容', category: 'file', defaultEnabled: true },
      { name: 'Edit', displayName: '编辑文件', description: '精确替换文件中的内容', category: 'file', defaultEnabled: true },
      { name: 'Insert', displayName: '插入文本', description: '在文件指定行插入文本', category: 'file', defaultEnabled: true },
      { name: 'Glob', displayName: '搜索文件', description: '按文件名模式搜索文件路径', category: 'search', defaultEnabled: true },
      { name: 'Grep', displayName: '搜索内容', description: '按正则表达式搜索文件内容', category: 'search', defaultEnabled: true },
      { name: 'Bash', displayName: '执行命令', description: '执行终端命令（白名单限制）', category: 'system', defaultEnabled: true },
      { name: 'LoadSkill', displayName: '加载技能', description: '加载技能规则到上下文', category: 'knowledge', defaultEnabled: true },
      { name: 'AskUser', displayName: '向用户提问', description: '向用户提问并暂停等待回复', category: 'interaction', defaultEnabled: false },
      { name: 'SearchDocs', displayName: '检索文档', description: '从知识库检索技术文档', category: 'knowledge', defaultEnabled: false },
    ]
    availableTools.value = defaultTools
    enabledTools.value = defaultTools.filter((t) => t.defaultEnabled).map((t) => t.name)
  }
})
</script>

<style scoped>
.playground-page {
  height: 100%;
  display: flex;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(253, 249, 245, 0.98), rgba(245, 239, 232, 0.94));
}

/* 左栏：工具配置 */
.tool-config-panel {
  width: 240px;
  min-width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92);
  border-right: 1px solid rgba(220, 207, 196, 0.92);
  padding: 16px;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.tool-list {
  flex: 1;
  overflow-y: auto;
}

.tool-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.tool-category-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 12px 0 4px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tool-category-label:first-child {
  margin-top: 0;
}

.tool-item {
  padding: 4px 0;
}

.tool-name {
  font-size: 13px;
  color: var(--color-text);
}

.tool-desc {
  display: block;
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-left: 24px;
  margin-top: -2px;
}

.tool-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(220, 207, 196, 0.5);
  margin-top: 12px;
}

/* 中栏：对话区 */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 320px;
  background: rgba(255, 255, 255, 0.92);
  overflow: hidden;
}

.chat-panel-header {
  height: 44px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(220, 207, 196, 0.92);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(252, 250, 247, 0.92));
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

.tool-count {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* 右栏：工具详情 */
.tool-detail-panel {
  width: 320px;
  min-width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92);
  border-left: 1px solid rgba(220, 207, 196, 0.92);
  padding: 16px;
  overflow-y: auto;
}

.tool-call-timeline {
  flex: 1;
  overflow-y: auto;
}

.tool-call-item {
  margin-bottom: 8px;
  border: 1px solid rgba(220, 207, 196, 0.6);
  border-radius: 8px;
  overflow: hidden;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  cursor: pointer;
  background: rgba(245, 239, 232, 0.3);
}

.tool-call-header:hover {
  background: rgba(245, 239, 232, 0.6);
}

.tool-call-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tool-call-status-dot.running {
  background: #faad14;
}

.tool-call-status-dot.completed {
  background: #52c41a;
}

.tool-call-status-dot.failed {
  background: #ff4d4f;
}

.tool-call-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
  flex: 1;
}

.tool-call-duration {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.tool-call-expand-icon {
  font-size: 10px;
  color: var(--color-text-tertiary);
}

.tool-call-body {
  padding: 8px 10px;
  border-top: 1px solid rgba(220, 207, 196, 0.4);
}

.tool-call-section {
  margin-bottom: 6px;
}

.section-label {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}

.section-content {
  font-size: 11px;
  color: var(--color-text);
  background: rgba(245, 239, 232, 0.3);
  padding: 6px 8px;
  border-radius: 4px;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.result-content {
  max-height: 300px;
}

.empty-detail {
  text-align: center;
  padding: 32px 16px;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

@media (max-width: 1024px) {
  .playground-page {
    flex-direction: column;
  }

  .tool-config-panel,
  .tool-detail-panel {
    width: 100%;
    max-height: 200px;
    border-right: none;
    border-left: none;
  }
}
</style>
