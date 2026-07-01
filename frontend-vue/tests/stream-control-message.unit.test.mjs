import test from 'node:test'
import assert from 'node:assert/strict'
import { createJiti } from 'jiti'

const jiti = createJiti(import.meta.url, {
  interopDefault: true,
  moduleCache: false,
})

const { isStreamControlMessage } = jiti('../src/utils/streamControlMessage.ts')

test('isStreamControlMessage: 应识别协议控制文本而非业务正文', () => {
  assert.equal(isStreamControlMessage('waiting_for_user'), true)
  assert.equal(isStreamControlMessage('对话完成'), true)
  assert.equal(isStreamControlMessage(' 对话完成 '), true)
})

test('isStreamControlMessage: 正常业务文本不应被误杀', () => {
  assert.equal(isStreamControlMessage('已完成登录页实现，并补充了表单校验。'), false)
  assert.equal(isStreamControlMessage('需求摘要'), false)
  assert.equal(isStreamControlMessage(''), false)
})
