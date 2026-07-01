const STREAM_CONTROL_MESSAGES = new Set(['waiting_for_user', '对话完成'])

export function isStreamControlMessage(text?: string | null): boolean {
  if (!text) return false
  return STREAM_CONTROL_MESSAGES.has(text.trim())
}
