/**
 * SSE 流式 JSON 解析与多事件合并工具。
 */

export interface DispatchContext {
  type?: string
  [key: string]: unknown
}

/**
 * 将可能拼接在一起的多个 JSON 对象拆开。
 * 例如 `{"type":"status",...}{"type":"tool_request",...}` 应被拆为两段。
 * 字符串内的大括号会被忽略（基于 JSON 字符串转义计数）。
 */
export const splitConcatenatedJsonObjects = (input: string): string[] => {
  const results: string[] = []
  let depth = 0
  let inString = false
  let escape = false
  let start = -1
  for (let i = 0; i < input.length; i++) {
    const ch = input[i]
    if (escape) {
      escape = false
      continue
    }
    if (inString) {
      if (ch === '\\') {
        escape = true
      } else if (ch === '"') {
        inString = false
      }
      continue
    }
    if (ch === '"') {
      inString = true
      continue
    }
    if (ch === '{') {
      if (depth === 0) start = i
      depth++
    } else if (ch === '}') {
      depth--
      if (depth === 0 && start >= 0) {
        results.push(input.slice(start, i + 1))
        start = -1
      } else if (depth < 0) {
        depth = 0
      }
    }
  }
  if (results.length === 0) {
    return [input]
  }
  return results
}

/**
 * 尝试从 rawData 中提取业务 JSON chunk。
 * 兼容三种情况：
 * 1. Java 包装的 {"d": "..."} 格式
 * 2. rawData 直接是业务 JSON（被错误去掉了 d 包装）
 * 3. 多段 SSE 事件合并到一次 onmessage（{...}{...}）
 */
export const extractBusinessChunk = (rawData: string): string[] => {
  if (!rawData) return []
  if (rawData === '[DONE]') return ['[DONE]']

  // 1. 尝试解析为单段 {d: ...} 包装
  try {
    const outer = JSON.parse(rawData)
    if (outer && typeof outer === 'object' && 'd' in outer) {
      return [outer.d || '']
    }
    if (outer && typeof outer === 'object' && 'type' in outer) {
      // 业务 JSON 直接到达
      return [rawData]
    }
    if (outer && typeof outer === 'object' && 'done' in outer) {
      return ['[DONE]']
    }
  } catch {
    // 解析失败：可能多段 JSON 拼接
  }

  // 2. 尝试分割多段 JSON
  const fragments = splitConcatenatedJsonObjects(rawData)
  if (fragments.length > 1) {
    return fragments
  }

  return [rawData]
}
