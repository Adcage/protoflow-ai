import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

test('PlanningForm: 题干与补充说明应按 Markdown 渲染而不是纯文本输出', () => {
  const source = readFileSync(new URL('../src/components/PlanningForm.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const template = descriptor.template?.content || ''

  assert.match(template, /v-html="renderMarkdown\(currentQuestion\.question\)"/, '题干应通过 Markdown 渲染，避免 **粗体** 与换行直接裸露出来')
  assert.match(template, /v-html="renderMarkdown\(currentQuestion\.reason\)"/, '补充说明也应复用相同 Markdown 渲染能力')
})
