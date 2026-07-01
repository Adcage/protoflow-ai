<template>
  <div class="admin-page">
    <div class="page-container">
      <div class="page-header">
        <h1 class="page-title">知识库管理</h1>
        <p class="page-subtitle">管理 Agent 可检索的前端技术文档库</p>
      </div>

      <!-- 状态卡片 -->
      <div class="status-card">
        <div class="status-item">
          <span class="status-label">RAG 状态</span>
          <a-tag v-if="status.enabled" color="green">已启用</a-tag>
          <a-tag v-else color="red">未启用</a-tag>
        </div>
        <div class="status-item">
          <span class="status-label">Embedding 模型</span>
          <span class="status-value">{{ status.embedding_model || '未配置' }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">文档库</span>
          <span class="status-value">{{ status.total_libraries }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">文档</span>
          <span class="status-value">{{ status.total_documents }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">片段</span>
          <span class="status-value">{{ status.total_chunks }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">最后索引</span>
          <span class="status-value">{{ status.last_indexed_at ? dayjs(status.last_indexed_at).format('MM-DD HH:mm') : '从未' }}</span>
        </div>
      </div>

      <!-- 操作栏 -->
      <div class="action-bar">
        <a-space>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><Plus :size="14" /></template>
            新建文档库
          </a-button>
          <a-button @click="handleUpload" :disabled="!currentLibrary">
            <template #icon><Upload :size="14" /></template>
            上传文档
          </a-button>
          <a-button :loading="reindexLoading" @click="handleReindex">
            <template #icon><RefreshCw :size="14" /></template>
            {{ reindexLoading ? '重建中...' : '重建索引' }}
          </a-button>
        </a-space>
        <input
          ref="fileInputRef"
          type="file"
          accept=".md"
          style="display: none"
          @change="onFileSelected"
        />
      </div>

      <!-- 库选择 tabs -->
      <div class="library-tabs">
        <a-tabs v-model:activeKey="activeLibrary" @change="onLibraryChange">
          <a-tab-pane v-for="lib in libraries" :key="lib.slug" :tab="lib.display_name">
            <template #tab>
              <span class="tab-label">
                {{ lib.display_name }}
                <a-badge :count="lib.doc_count" :overflow-count="999" />
              </span>
            </template>
          </a-tab-pane>
        </a-tabs>
      </div>

      <!-- 文档表格 -->
      <div class="table-wrapper">
        <a-table
          :columns="columns"
          :data-source="documents"
          :loading="loading"
          :pagination="pagination"
          size="middle"
          row-key="id"
          :locale="{ emptyText: currentLibrary ? '暂无文档，点击上方「上传文档」添加 .md 文件' : '请先选择一个文档库' }"
        >
          <template #bodyCell="{ column, text, record }">
            <template v-if="column.key === 'filename'">
              <span class="file-name">
                <FileText :size="14" class="file-icon" />
                {{ text }}
              </span>
            </template>
            <template v-else-if="column.key === 'file_size'">
              <span class="time-text">{{ formatSize(record.file_size) }}</span>
            </template>
            <template v-else-if="column.key === 'chunk_count'">
              <span class="chunk-badge">{{ record.chunk_count }}</span>
            </template>
            <template v-else-if="column.key === 'indexed_at'">
              <span class="time-text">{{ record.indexed_at ? dayjs(record.indexed_at).format('MM-DD HH:mm') : '-' }}</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-popconfirm
                title="确定要删除这个文档吗？删除后需重建索引生效。"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDeleteDoc(record.library_slug, record.filename)"
              >
                <a-button type="text" size="small" class="danger-action-btn">
                  <template #icon><Trash2 :size="14" /></template>
                  删除
                </a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 新建库 Modal -->
      <a-modal
        v-model:open="createModalVisible"
        title="新建文档库"
        ok-text="创建"
        cancel-text="取消"
        @ok="handleCreateLibrary"
      >
        <a-form layout="vertical">
          <a-form-item label="标识 (slug)" required>
            <a-input v-model:value="newLibrary.slug" placeholder="如 ant-design-vue" />
          </a-form-item>
          <a-form-item label="显示名称">
            <a-input v-model:value="newLibrary.displayName" placeholder="如 Ant Design Vue 组件库" />
          </a-form-item>
          <a-form-item label="描述">
            <a-textarea v-model:value="newLibrary.description" placeholder="文档库说明" :rows="3" />
          </a-form-item>
        </a-form>
      </a-modal>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { Plus, Upload, RefreshCw, FileText, Trash2 } from '@lucide/vue'
import {
  getRagStatus,
  listLibraries,
  listDocuments,
  uploadDocument,
  deleteDocument,
  createLibrary,
  triggerReindex,
  type LibraryVO,
  type RagStatusVO,
  type DocumentVO,
} from '@/api/knowledgeController'

// ============================================================
// 状态
// ============================================================
const status = reactive<RagStatusVO>({
  enabled: false,
  embedding_configured: false,
  embedding_model: '',
  total_libraries: 0,
  total_documents: 0,
  total_chunks: 0,
  last_indexed_at: null,
  error_message: '',
})

const libraries = ref<LibraryVO[]>([])
const documents = ref<DocumentVO[]>([])
const activeLibrary = ref<string>('')
const loading = ref(false)
const reindexLoading = ref(false)
const createModalVisible = ref(false)
const fileInputRef = ref<HTMLInputElement>()

const newLibrary = reactive({
  slug: '',
  displayName: '',
  description: '',
})

// ============================================================
// 表格
// ============================================================
const columns = [
  { title: '文件名', dataIndex: 'filename', key: 'filename', ellipsis: true },
  { title: '大小', dataIndex: 'file_size', key: 'file_size', width: 100 },
  { title: '片段数', dataIndex: 'chunk_count', key: 'chunk_count', width: 90, align: 'center' },
  { title: '索引时间', dataIndex: 'indexed_at', key: 'indexed_at', width: 140 },
  { title: '操作', key: 'action', width: 100, align: 'center' },
]

const currentLibrary = computed(() => activeLibrary.value)

const pagination = computed(() => ({
  pageSize: 50,
  hideOnSinglePage: true,
}))

// ============================================================
// 方法
// ============================================================
const fetchStatus = async () => {
  try {
    const res = await getRagStatus()
    Object.assign(status, res.data as unknown as RagStatusVO)
  } catch (e) {
    console.error('获取 RAG 状态失败', e)
  }
}

const fetchLibraries = async () => {
  try {
    const res = await listLibraries()
    libraries.value = (res.data as unknown as LibraryVO[]) || []
    if (libraries.value.length > 0 && !activeLibrary.value) {
      activeLibrary.value = libraries.value[0].slug
      await fetchDocuments()
    }
  } catch (e) {
    console.error('获取文档库列表失败', e)
  }
}

const fetchDocuments = async () => {
  if (!activeLibrary.value) return
  loading.value = true
  try {
    const res = await listDocuments(activeLibrary.value)
    documents.value = (res.data as unknown as DocumentVO[]) || []
  } catch (e) {
    console.error('获取文档列表失败', e)
  } finally {
    loading.value = false
  }
}

const onLibraryChange = async () => {
  await fetchDocuments()
}

const handleReindex = async () => {
  reindexLoading.value = true
  try {
    const res = await triggerReindex()
    const data = res.data as unknown as { success: boolean; message: string; documents_indexed: number }
    if (data.success) {
      message.success(`重建索引完成，共 ${data.documents_indexed} 个文档`)
      await fetchStatus()
      await fetchDocuments()
    } else {
      message.error('重建索引失败: ' + (data.message || '未知错误'))
    }
  } catch (e) {
    message.error('重建索引请求失败')
  } finally {
    reindexLoading.value = false
  }
}

const handleUpload = () => {
  fileInputRef.value?.click()
}

const onFileSelected = async (e: Event) => {
  const input = e.target as HTMLInputElement
  if (!input.files || input.files.length === 0) return

  const file = input.files[0]
  if (!file.name.endsWith('.md')) {
    message.warning('仅支持 .md 格式文件')
    input.value = ''
    return
  }

  try {
    const res = await uploadDocument(activeLibrary.value, file)
    message.success(`上传成功: ${file.name}`)
    await fetchDocuments()
    await fetchStatus()
  } catch (e) {
    message.error('上传失败')
  }
  input.value = ''
}

const handleDeleteDoc = async (library: string, filename: string) => {
  try {
    const res = await deleteDocument(library, filename)
    const data = res.data as unknown as { success: boolean; message: string }
    if (data.success) {
      message.success('删除成功')
      await fetchDocuments()
      await fetchStatus()
    } else {
      message.error('删除失败: ' + data.message)
    }
  } catch (e) {
    message.error('删除请求失败')
  }
}

const showCreateModal = () => {
  newLibrary.slug = ''
  newLibrary.displayName = ''
  newLibrary.description = ''
  createModalVisible.value = true
}

const handleCreateLibrary = async () => {
  if (!newLibrary.slug) {
    message.warning('请输入文档库标识')
    return
  }
  try {
    await createLibrary(newLibrary.slug, newLibrary.displayName || undefined, newLibrary.description || undefined)
    message.success('文档库创建成功')
    createModalVisible.value = false
    await fetchLibraries()
    activeLibrary.value = newLibrary.slug
    await fetchDocuments()
    await fetchStatus()
  } catch (e) {
    message.error('创建失败')
  }
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ============================================================
// 初始化
// ============================================================
onMounted(async () => {
  await fetchStatus()
  await fetchLibraries()
})
</script>

<style scoped>
.admin-page {
  height: 100%;
  background: var(--color-background);
}

.page-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--space-2xl) var(--space-lg);
}

.page-header {
  margin-bottom: var(--space-lg);
}

.page-title {
  font-family: var(--font-heading);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 var(--space-xs) 0;
}

.page-subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0;
}

/* 状态卡片 */
.status-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-md) var(--space-lg);
  margin-bottom: var(--space-lg);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-lg);
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-label {
  font-size: 12px;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

/* 操作栏 */
.action-bar {
  margin-bottom: var(--space-md);
}

/* 库标签 */
.library-tabs {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  padding: var(--space-md) var(--space-lg) 0;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 表格 */
.table-wrapper {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-top: none;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  padding: var(--space-md);
}

.file-name {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text);
}

.file-icon {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.time-text {
  color: var(--color-text-muted);
  font-size: 13px;
}

.chunk-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  padding: 0 8px;
  height: 22px;
  background: var(--color-background);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.danger-action-btn {
  color: var(--color-text-secondary) !important;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.danger-action-btn:hover {
  color: var(--color-error) !important;
}

@media (max-width: 768px) {
  .page-container {
    padding: var(--space-lg) var(--space-md);
  }

  .page-title {
    font-size: 24px;
  }

  .status-card {
    flex-direction: column;
    gap: var(--space-md);
  }

  .status-item {
    flex-direction: row;
    justify-content: space-between;
  }
}
</style>
