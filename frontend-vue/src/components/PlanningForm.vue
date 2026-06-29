<template>
  <div class="planning-form">
    <div class="planning-header">
      <span class="planning-icon">AI 需要补充一些信息</span>
      <span v-if="isReadonly" class="readonly-tag">已回答</span>
      <span v-else class="planning-progress">{{ currentStep + 1 }} / {{ questions.length }}</span>
    </div>

    <Transition name="slide" mode="out-in">
      <div v-if="showQuestions" :key="currentStep" class="planning-step">
        <div class="question-label">
          {{ currentQuestion.question }}
          <span v-if="currentQuestion.required" class="required-mark">*必填</span>
        </div>
        <div v-if="currentQuestion.reason" class="question-reason">{{ currentQuestion.reason }}</div>

        <template v-if="currentQuestion.inputType === 'single_select'">
          <div
            v-for="opt in currentQuestion.options"
            :key="optionKey(opt)"
            :class="['option-card', { selected: isSelected(opt), disabled: isReadonly }]"
            @click="!isReadonly && selectOption(opt)"
          >
            <span :class="['radio-dot', { active: isSelected(opt) }]" />
            <div class="option-content">
              <div class="option-label">
                {{ opt.label }}
                <span v-if="opt.recommended" class="recommended-tag">建议</span>
              </div>
              <div v-if="opt.description" class="option-description">{{ opt.description }}</div>
            </div>
          </div>
        </template>

        <template v-else-if="currentQuestion.inputType === 'multi_select'">
          <div
            v-for="opt in currentQuestion.options"
            :key="optionKey(opt)"
            :class="['option-card', { selected: isSelectedMulti(opt), disabled: isReadonly }]"
            @click="!isReadonly && toggleMulti(opt)"
          >
            <span :class="['checkbox-box', { checked: isSelectedMulti(opt) }]" />
            <div class="option-content">
              <div class="option-label">
                {{ opt.label }}
                <span v-if="opt.recommended" class="recommended-tag">建议</span>
              </div>
              <div v-if="opt.description" class="option-description">{{ opt.description }}</div>
            </div>
          </div>
        </template>

        <div class="custom-answer-section">
          <div
            :class="['option-card', { selected: showCustomInput }]"
            @click="toggleCustomInput"
          >
            <span :class="['radio-dot', { active: showCustomInput }]" />
            <div class="option-content">
              <div class="option-label">自定义回答</div>
              <div class="option-description">如果以上选项都不符合，可以在此输入你自己的回答</div>
            </div>
          </div>
          <a-textarea
            v-if="showCustomInput"
            v-model:value="customAnswer"
            placeholder="输入你的自定义回答..."
            :auto-size="{ minRows: 2, maxRows: 8 }"
            class="custom-input"
          />
        </div>
      </div>
    </Transition>

    <div class="planning-actions">
      <template v-if="isReadonly">
        <div class="readonly-nav">
          <a-button size="small" :disabled="currentStep <= 0" @click="goPrevReadonly">上一题</a-button>
          <span class="readonly-step">{{ currentStep + 1 }} / {{ questions.length }}</span>
          <a-button size="small" :disabled="currentStep >= questions.length - 1" @click="goNextReadonly">下一题</a-button>
        </div>
      </template>
      <template v-else>
        <a-button @click="handleSkip">
          {{ currentStep < questions.length - 1 ? '跳过本题' : '跳过' }}
        </a-button>
        <div class="action-right">
          <a-button v-if="currentStep > 0" class="prev-btn" @click="goPrev">上一题</a-button>
          <a-button
            v-if="currentStep < questions.length - 1"
            type="primary"
            :disabled="!hasCurrentAnswer"
            @click="goNext"
          >
            下一题
          </a-button>
          <a-button
            v-else
            type="primary"
            :disabled="!hasCurrentAnswer"
            @click="handleSubmit"
          >
            提交，继续生成
          </a-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

export interface PlanningOption {
  value?: string
  id?: string
  label: string
  description?: string
  recommended?: boolean
}

export interface PlanningQuestion {
  id: string
  prompt?: string
  question: string
  inputType: 'single_select' | 'multi_select'
  required: boolean
  options?: PlanningOption[]
  reason?: string
  placeholder?: string
}

const props = defineProps<{
  questions: PlanningQuestion[]
  readonlyAnswers?: Record<string, string> | null
}>()
const emit = defineEmits<{ submit: [answers: Record<string, string>]; skip: [] }>()

const currentStep = ref(0)
const showQuestions = ref(true)

const singleAnswers = ref<Record<string, string>>({})
const multiSelected = ref<string[]>([])
const textAnswer = ref('')
const showCustomInput = ref(false)
const customAnswer = ref('')
const customUsed = ref<Record<string, string>>({})

const isReadonly = computed(() => {
  return props.readonlyAnswers !== null && props.readonlyAnswers !== undefined && Object.keys(props.readonlyAnswers).length > 0
})

const currentQuestion = computed(() => props.questions[currentStep.value])

const currentAnswer = computed({
  get: () => {
    if (currentQuestion.value.inputType === 'multi_select') return multiSelected.value.join(',')
    if (showCustomInput.value && customAnswer.value) return customAnswer.value
    return singleAnswers.value[currentQuestion.value.id] || ''
  },
  set: (val: string) => {
    if (currentQuestion.value.inputType === 'single_select') {
      singleAnswers.value[currentQuestion.value.id] = val
    }
  },
})

watch(
  () => props.readonlyAnswers,
  (answers) => {
    if (answers && Object.keys(answers).length > 0) {
      singleAnswers.value = { ...answers }
      loadCurrentState()
    }
  },
  { immediate: true },
)

function optionKey(opt: PlanningOption): string {
  return opt.id || opt.value || opt.label
}

function getOptionId(opt: PlanningOption): string {
  return opt.id || opt.value || opt.label
}

function isSelected(opt: PlanningOption): boolean {
  return currentAnswer.value === getOptionId(opt)
}

function isSelectedMulti(opt: PlanningOption): boolean {
  return multiSelected.value.includes(getOptionId(opt))
}

function selectOption(opt: PlanningOption): void {
  currentAnswer.value = getOptionId(opt)
}

const hasCurrentAnswer = computed(() => {
  if (!currentQuestion.value.required) return true
  if (currentQuestion.value.inputType === 'multi_select') return multiSelected.value.length > 0
  if (showCustomInput.value && customAnswer.value.trim()) return true
  return !!singleAnswers.value[currentQuestion.value.id]
})

function toggleMulti(opt: PlanningOption) {
  const value = getOptionId(opt)
  const idx = multiSelected.value.indexOf(value)
  if (idx >= 0) {
    multiSelected.value.splice(idx, 1)
  } else {
    multiSelected.value.push(value)
  }
}

function toggleCustomInput() {
  showCustomInput.value = !showCustomInput.value
  if (showCustomInput.value) {
    singleAnswers.value[currentQuestion.value.id] = ''
  }
}

function saveCurrentAnswer() {
  const q = currentQuestion.value
  if (q.inputType === 'multi_select') {
    singleAnswers.value[q.id] = multiSelected.value.join(', ')
  } else if (showCustomInput.value && customAnswer.value.trim()) {
    customUsed.value[q.id] = customAnswer.value.trim()
    singleAnswers.value[q.id] = customAnswer.value.trim()
  }
}

function goNext() {
  saveCurrentAnswer()
  showQuestions.value = false
  currentStep.value++
  loadCurrentState()
  nextTickShow()
}

function goPrev() {
  saveCurrentAnswer()
  showQuestions.value = false
  currentStep.value--
  loadCurrentState()
  nextTickShow()
}

function loadCurrentState() {
  const q = currentQuestion.value
  textAnswer.value = ''
  multiSelected.value = []
  showCustomInput.value = false
  customAnswer.value = ''

  if (q.inputType === 'multi_select') {
    multiSelected.value = (singleAnswers.value[q.id] || '').split(', ').filter(Boolean)
  } else {
    if (customUsed.value[q.id]) {
      showCustomInput.value = true
      customAnswer.value = customUsed.value[q.id]
    }
    if (singleAnswers.value[q.id] && !customUsed.value[q.id]) {
      singleAnswers.value[q.id] = singleAnswers.value[q.id]
    }
  }
}

function nextTickShow() {
  setTimeout(() => {
    showQuestions.value = true
  }, 50)
}

function handleSubmit() {
  saveCurrentAnswer()
  emit('submit', { ...singleAnswers.value })
}

function handleSkip() {
  saveCurrentAnswer()
  emit('skip')
}

function goNextReadonly() {
  if (currentStep.value < props.questions.length - 1) {
    showQuestions.value = false
    currentStep.value++
    setTimeout(() => { showQuestions.value = true }, 50)
  }
}

function goPrevReadonly() {
  if (currentStep.value > 0) {
    showQuestions.value = false
    currentStep.value--
    setTimeout(() => { showQuestions.value = true }, 50)
  }
}
</script>

<style scoped>
.planning-form {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  overflow: hidden;
}

.planning-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-elevated);
}

.planning-icon {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.planning-progress {
  font-size: 12px;
  color: var(--color-text-muted);
}

.planning-step {
  padding: 18px;
}

.question-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 4px;
}

.required-mark {
  font-size: 11px;
  color: var(--color-error);
  margin-left: 6px;
}

.question-reason {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 14px;
}

.option-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--color-background);
}

.option-card:hover {
  border-color: var(--color-border-light);
}

.option-card.selected {
  border-color: var(--color-cta);
  background: rgba(34, 197, 94, 0.08);
}

.radio-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid var(--color-border-light);
  flex-shrink: 0;
  margin-top: 2px;
  transition: all 0.2s;
}

.radio-dot.active {
  border-color: var(--color-cta);
  background: var(--color-cta);
  box-shadow: 0 0 0 2px var(--color-background) inset;
}

.checkbox-box {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 2px solid var(--color-border-light);
  flex-shrink: 0;
  margin-top: 2px;
  transition: all 0.2s;
}

.checkbox-box.checked {
  border-color: var(--color-cta);
  background: var(--color-cta);
}

.option-content {
  flex: 1;
  min-width: 0;
}

.option-label {
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.4;
}

.recommended-tag {
  display: inline-block;
  font-size: 11px;
  color: var(--color-cta);
  background: rgba(34, 197, 94, 0.12);
  padding: 1px 7px;
  border-radius: 4px;
  margin-left: 6px;
  font-weight: 500;
}

.option-description {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
  line-height: 1.5;
}

.custom-answer-section {
  margin-top: 12px;
}

.custom-answer-section .option-card {
  border-style: dashed;
}

.custom-input {
  margin-top: 10px;
}

.custom-input :deep(textarea) {
  background: var(--color-background) !important;
  border-color: var(--color-border) !important;
  color: var(--color-text) !important;
}

.planning-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface-elevated);
}

.action-right {
  display: flex;
  gap: 8px;
}

.option-card.disabled {
  cursor: default;
  opacity: 0.7;
}

.option-card.disabled:hover {
  border-color: var(--color-border);
}

.readonly-tag {
  font-size: 11px;
  color: var(--color-text-muted);
  background: var(--color-surface-elevated);
  padding: 2px 8px;
  border-radius: 4px;
}

.readonly-hint {
  font-size: 13px;
  color: var(--color-text-muted);
  width: 100%;
  text-align: center;
}

.readonly-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  justify-content: center;
}

.readonly-step {
  font-size: 13px;
  color: var(--color-text-muted);
  min-width: 48px;
  text-align: center;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}

.slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
</style>
