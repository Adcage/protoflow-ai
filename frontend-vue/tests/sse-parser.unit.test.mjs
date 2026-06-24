/**
 * SSE 流式 JSON 解析与多事件合并工具测试。
 *
 * 覆盖：
 * - 单段 JSON 解析
 * - 多段平铺 JSON 正确分割
 * - 字符串内大括号不被错误分割
 * - 嵌套 JSON 不被错误分割
 * - 转义引号正确处理
 * - Java {d:...} 包装、裸业务 JSON、多段合并三种 rawData 形态
 */

import test from 'node:test'
import assert from 'node:assert/strict'

// 重复实现 sseParser 的 splitConcatenatedJsonObjects 与 extractBusinessChunk，
// 以便在无构建/无类型系统的 node:test 环境下运行；保持与 src/composables/sseParser.ts 一致。
function splitConcatenatedJsonObjects(input) {
  const results = []
  let depth = 0
  let inString = false
  let escape = false
  let start = -1
  for (let i = 0; i < input.length; i++) {
    const ch = input[i]
    if (escape) { escape = false; continue }
    if (inString) {
      if (ch === '\\') { escape = true }
      else if (ch === '"') { inString = false }
      continue
    }
    if (ch === '"') { inString = true; continue }
    if (ch === '{') { if (depth === 0) start = i; depth++ }
    else if (ch === '}') {
      depth--
      if (depth === 0 && start >= 0) {
        results.push(input.slice(start, i + 1))
        start = -1
      } else if (depth < 0) {
        depth = 0
      }
    }
  }
  if (results.length === 0) return [input]
  return results
}

function extractBusinessChunk(rawData) {
  if (!rawData) return []
  if (rawData === '[DONE]') return ['[DONE]']
  try {
    const outer = JSON.parse(rawData)
    if (outer && typeof outer === 'object' && 'd' in outer) {
      return [outer.d || '']
    }
    if (outer && typeof outer === 'object' && 'type' in outer) {
      return [rawData]
    }
    if (outer && typeof outer === 'object' && 'done' in outer) {
      return ['[DONE]']
    }
  } catch {}
  const fragments = splitConcatenatedJsonObjects(rawData)
  if (fragments.length > 1) return fragments
  return [rawData]
}

test('splitConcatenatedJsonObjects: 单段 JSON 整体返回', () => {
  const input = '{"type":"status","message":"x"}'
  assert.deepEqual(splitConcatenatedJsonObjects(input), [input])
})

test('splitConcatenatedJsonObjects: 两段平铺正确分割', () => {
  const seg1 = '{"type":"status","message":"x"}'
  const seg2 = '{"type":"status","message":"y"}'
  const merged = seg1 + seg2
  assert.deepEqual(splitConcatenatedJsonObjects(merged), [seg1, seg2])
})

test('splitConcatenatedJsonObjects: 多段不同类型正确分割（用户真实场景）', () => {
  const seg1 = '{"message":"Route step","type":"status"}'
  const seg2 = '{"id":"call_1","name":"read_dir","arguments":"{\\"relativeDirPath\\": \\".\\"}","type":"tool_request"}'
  const seg3 = '{"data":"waiting_for_user","type":"ai_response"}'
  const merged = seg1 + seg2 + seg3
  const result = splitConcatenatedJsonObjects(merged)
  assert.equal(result.length, 3)
  for (const fragment of result) {
    JSON.parse(fragment)
  }
})

test('splitConcatenatedJsonObjects: 字符串内大括号不被分割', () => {
  const seg1 = '{"a":"hello { world }","type":"x"}'
  const seg2 = '{"type":"y"}'
  const merged = seg1 + seg2
  assert.deepEqual(splitConcatenatedJsonObjects(merged), [seg1, seg2])
})

test('splitConcatenatedJsonObjects: 嵌套 JSON 不被错误分割', () => {
  const seg1 = '{"a":{"b":{"c":1}},"type":"x"}'
  const seg2 = '{"type":"y"}'
  assert.deepEqual(splitConcatenatedJsonObjects(seg1 + seg2), [seg1, seg2])
})

test('splitConcatenatedJsonObjects: 转义引号', () => {
  const seg1 = '{"a":"say \\"hello\\"","type":"x"}'
  const seg2 = '{"type":"y"}'
  assert.deepEqual(splitConcatenatedJsonObjects(seg1 + seg2), [seg1, seg2])
})

test('splitConcatenatedJsonObjects: 空字符串返回空', () => {
  assert.deepEqual(splitConcatenatedJsonObjects(''), [''])
})

test('extractBusinessChunk: Java {d:...} 包装取出内层', () => {
  const wrapped = JSON.stringify({ d: '{"type":"status","message":"Route step"}' })
  assert.deepEqual(extractBusinessChunk(wrapped), ['{"type":"status","message":"Route step"}'])
})

test('extractBusinessChunk: 裸业务 JSON 直接返回', () => {
  const raw = '{"type":"status","message":"Route step"}'
  assert.deepEqual(extractBusinessChunk(raw), [raw])
})

test('extractBusinessChunk: 多段合并正确分割为多段', () => {
  const merged =
    '{"message":"Route step","type":"status"}' +
    '{"id":"call_1","name":"read_dir","arguments":"{\\"relativeDirPath\\": \\".\\"}","type":"tool_request"}' +
    '{"data":"waiting_for_user","type":"ai_response"}'
  const result = extractBusinessChunk(merged)
  assert.equal(result.length, 3)
  for (const fragment of result) {
    JSON.parse(fragment)
  }
})

test('extractBusinessChunk: [DONE] 标记', () => {
  assert.deepEqual(extractBusinessChunk('[DONE]'), ['[DONE]'])
})

test('extractBusinessChunk: done 包装格式', () => {
  const wrapped = JSON.stringify({ done: true })
  assert.deepEqual(extractBusinessChunk(wrapped), ['[DONE]'])
})

test('extractBusinessChunk: 空字符串', () => {
  assert.deepEqual(extractBusinessChunk(''), [])
})
