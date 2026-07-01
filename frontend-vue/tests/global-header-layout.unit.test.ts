import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

test('GlobalHeader 顶部导航应使用全宽容器而不是定宽居中容器', () => {
  const source = readFileSync(new URL('../src/components/GlobalHeader.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const style = descriptor.styles.map((item) => item.content).join('\n')

  assert.ok(style, 'GlobalHeader 应包含样式定义')
  assert.doesNotMatch(style, /max-width:\s*1400px/, '顶部导航不应继续限制在 1400px 定宽容器内')
  assert.doesNotMatch(style, /margin:\s*0\s+auto/, '顶部导航内容不应继续通过 auto margin 居中')
  assert.match(style, /padding:\s*0\s+var\(--space-page-x\)/, '顶部导航应复用页面级横向留白变量')
})
