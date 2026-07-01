import request from '@/request'

/**
 * 获取 Playground 可用的工具列表
 */
export async function listPlaygroundTools() {
  return request.get('/playground/tools')
}

/**
 * 重置 Playground（新建对话 Session）
 */
export async function resetPlayground() {
  return request.post('/playground/reset')
}
