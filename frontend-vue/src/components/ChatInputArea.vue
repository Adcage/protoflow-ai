<template>
  <div class="chat-input-area">
    <!-- 附件预览区 -->
    <div v-if="attachedFiles.length > 0" class="attachment-preview-area">
      <div v-if="getImageFiles().length > 0" class="upload-image-grid">
        <div v-for="item in getImageFiles()" :key="item.file.name + item.file.size" class="upload-image-card">
          <img :src="item.previewUrl" class="upload-image-thumb" @click="openImagePreview(item)" />
          <button type="button" class="upload-image-remove" @click="removeFileByItem(item)">
            <CloseOutlined />
          </button>
        </div>
      </div>
      <div v-if="getNonImageFiles().length > 0" class="upload-file-list">
        <div v-for="item in getNonImageFiles()" :key="item.file.name + item.file.size" class="attachment-item">
          <PaperClipOutlined class="attachment-icon" />
          <span class="attachment-name">{{ item.file.name }}</span>
          <CloseOutlined class="attachment-remove" @click="removeFileByItem(item)" />
        </div>
      </div>
    </div>

    <div class="input-row">
      <a-textarea
        v-model:value="inputText"
        :placeholder="placeholder"
        :auto-size="{ minRows: 1, maxRows: 4 }"
        :disabled="disabled || generating"
        @press-enter="handleEnter"
        class="chat-textarea"
      />
      <div class="input-actions">
        <!-- 附件上传按钮 -->
        <a-tooltip title="上传附件（图片/文档/代码/压缩包）">
          <a-button type="text" size="small" :disabled="generating" @click="triggerFileInput">
            <template #icon><PaperClipOutlined /></template>
          </a-button>
        </a-tooltip>
        <input
          ref="fileInputRef"
          type="file"
          multiple
          accept="image/*,.pdf,.doc,.docx,.zip,.tar,.gz,.js,.ts,.tsx,.jsx,.py,.java,.css,.html,.vue,.go,.rs,.c,.cpp,.sh,.sql,.txt,.md,.json,.xml,.yaml,.yml,.csv"
          style="display: none"
          @change="onFileChange"
        />
        <a-tooltip title="优化提示词">
          <a-button
            type="text"
            size="small"
            :disabled="!inputText.trim() || generating"
            :loading="enhancing"
            @click="$emit('enhance', inputText)"
          >
            <template #icon><BulbOutlined /></template>
          </a-button>
        </a-tooltip>
        <a-button
          type="primary"
          size="small"
          :disabled="(!inputText.trim() && attachedFiles.length === 0) || generating"
          :loading="uploading"
          @click="handleSend"
        >
          <template #icon><SendOutlined /></template>
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { BulbOutlined, CloseOutlined, PaperClipOutlined, SendOutlined } from '@ant-design/icons-vue'
import type { AttachmentInfo } from '@/utils/chatStreamRequest'
import { validateChatAttachmentFiles } from '@/utils/chatAttachmentValidation'
import request from '@/request'

const props = withDefaults(
  defineProps<{
    generating?: boolean
    enhancing?: boolean
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    generating: false,
    enhancing: false,
    placeholder: '输入你的需求，按 Enter 发送...',
    disabled: false,
  },
)

const emit = defineEmits<{
  send: [message: string, attachments: AttachmentInfo[]]
  enhance: [message: string]
}>()

const inputText = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const attachedFiles = ref<{ file: File; previewUrl?: string }[]>([])
const uploadedAttachments = ref<AttachmentInfo[]>([])
const uploading = ref(false)
const openImagePreviewer = (url: string) => {
  window.dispatchEvent(new CustomEvent('image-preview-open', { detail: url }))
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const onFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return

  const selectedFiles = Array.from(target.files)
  const validation = validateChatAttachmentFiles([...attachedFiles.value.map((item) => item.file), ...selectedFiles])
  if (!validation.valid) {
    message.warning(validation.message)
    target.value = ''
    return
  }

  const newFiles: { file: File; previewUrl?: string }[] = []
  for (const f of selectedFiles) {
    // 总文件数限制
    if (attachedFiles.value.length + newFiles.length >= 5) {
      message.warning('最多上传 5 个文件')
      break
    }
    const item: { file: File; previewUrl?: string } = { file: f }
    // 图片生成缩略图预览
    if (f.type.startsWith('image/')) {
      item.previewUrl = URL.createObjectURL(f)
    }
    newFiles.push(item)
  }
  attachedFiles.value.push(...newFiles)
  // 重置 input 以便重新选择同一文件
  target.value = ''
}

const removeFile = (index: number) => {
  const item = attachedFiles.value[index]
  if (item.previewUrl) {
    URL.revokeObjectURL(item.previewUrl)
  }
  attachedFiles.value.splice(index, 1)
  // 如果之前已上传过该文件，也从已上传列表中移除
  uploadedAttachments.value.splice(index, 1)
}

const removeFileByItem = (item: { file: File; previewUrl?: string }) => {
  const index = attachedFiles.value.indexOf(item)
  if (index >= 0) {
    removeFile(index)
  }
}

const getImageFiles = () => attachedFiles.value.filter((item) => !!item.previewUrl)

const getNonImageFiles = () => attachedFiles.value.filter((item) => !item.previewUrl)

const openImagePreview = (item: { file: File; previewUrl?: string }) => {
  if (item.previewUrl) {
    openImagePreviewer(item.previewUrl)
  }
}

const handleSend = async () => {
  if (props.generating) return
  const msg = inputText.value.trim()

  // 没有文本也没有附件，不发送
  if (!msg && attachedFiles.value.length === 0) return

  // 如果有附件，先上传再发送
  if (attachedFiles.value.length > 0) {
    uploading.value = true
    try {
      const formData = new FormData()
      for (const item of attachedFiles.value) {
        formData.append('files', item.file)
      }
      const res = await request.post('/file/upload/chat-attachment', formData, {
        timeout: 60000,
      })
      if (res.data?.code === 0) {
        uploadedAttachments.value = res.data.data || []
      } else {
        message.error(res.data?.message || '文件上传失败')
        return
      }
    } catch (e) {
      message.error('文件上传失败')
      return
    } finally {
      uploading.value = false
    }
  }

  const attachments = [...uploadedAttachments.value]
  emit('send', msg, attachments)
  inputText.value = ''

  // 清空附件
  for (const item of attachedFiles.value) {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl)
  }
  attachedFiles.value = []
  uploadedAttachments.value = []
}

const handleEnter = (e: KeyboardEvent) => {
  if (e.shiftKey) return
  e.preventDefault()
  handleSend()
}

defineExpose({
  inputText,
  clearInput: () => {
    inputText.value = ''
    attachedFiles.value = []
    uploadedAttachments.value = []
  },
})
</script>

<style scoped>
.chat-input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.attachment-preview-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
  padding: 10px;
  background: rgba(255, 250, 246, 0.84);
  border-radius: 18px;
  border: 1px solid rgba(232, 224, 216, 0.9);
}

.upload-image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.upload-image-card {
  position: relative;
  overflow: hidden;
  width: 96px;
  height: 96px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow:
    0 10px 24px rgba(28, 24, 21, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.55);
}

.upload-image-thumb {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: pointer;
  transition: transform 0.18s ease, filter 0.18s ease;
}

.upload-image-thumb:hover {
  transform: scale(1.02);
  filter: saturate(1.04);
}

.upload-image-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: rgba(24, 21, 19, 0.62);
  color: #fff;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.2s ease;
}

.upload-image-remove:hover {
  background: rgba(24, 21, 19, 0.82);
  transform: scale(1.06);
}

.upload-file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.attachment-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  cursor: default;
}

.attachment-icon {
  font-size: 16px;
  color: var(--color-text-secondary);
}

.attachment-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.attachment-remove {
  margin-left: 2px;
  font-size: 12px;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color 0.2s;
}
.attachment-remove:hover {
  color: var(--color-error);
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.chat-textarea {
  flex: 1;
  border-radius: 6px;
  resize: none;
  background: var(--color-background) !important;
  border-color: var(--color-border) !important;
  color: var(--color-text) !important;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.chat-textarea:focus,
.chat-textarea:focus-within {
  border-color: var(--color-cta) !important;
  box-shadow: 0 0 0 2px var(--color-cta-lighter) !important;
}

.input-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.input-actions :deep(.ant-btn-primary) {
  box-shadow: 0 2px 8px rgba(200, 90, 62, 0.25);
}
</style>
