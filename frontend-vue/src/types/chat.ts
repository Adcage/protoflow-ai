import type { AttachmentInfo } from '../utils/chatStreamRequest'

export interface ToolEvent {
  type: 'request' | 'executed' | 'status'
  text: string
}

export interface ToolCallRecord {
  type: 'request' | 'executed' | 'status'
  id: string
  name: string
  description: string
  arguments: string
  result?: string
  status: 'running' | 'completed' | 'failed'
  timestamp: number
  agentName?: string
}

export interface PlanningOption {
  id?: string
  value?: string
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

export interface PlanningQuestionSet {
  questionSetId: string
  stage?: string
  protocolVersion?: number
  questions: PlanningQuestion[]
  answers?: Record<string, string> // 用户已提交的回答，提交后填充
}

export interface ChatMessage {
  role: 'user' | 'ai'
  content: string
  status?: string
  toolStatus?: string
  toolEvents?: ToolEvent[]
  toolCalls?: ToolCallRecord[]
  planning?: PlanningQuestionSet
  attachments?: AttachmentInfo[]
  agentName?: string
  currentAgent?: string
}
