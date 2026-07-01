import test from 'node:test'
import assert from 'node:assert/strict'
import MarkdownIt from 'markdown-it'
import { createJiti } from 'jiti'

const jiti = createJiti(import.meta.url, {
  interopDefault: true,
  moduleCache: false,
})

const { normalizeLooseMarkdown } = jiti('../src/utils/chatMarkdown.ts')

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

test('normalizeLooseMarkdown: 全行强调标题不应被误判为列表并露出裸星号', () => {
  const input = ['明白，我已整理好你的需求摘要，请确认：', '', '*需求摘要*', '*项目信息*', '-项目类型：全新项目'].join('\n')

  const html = md.render(normalizeLooseMarkdown(input))

  assert.doesNotMatch(html, /项目信息\*/, '强调标题不应残留尾部裸 *')
  assert.match(html, /<strong>项目信息<\/strong>/, '强调标题应按强调文本渲染')
  assert.match(html, /<li>项目类型：全新项目<\/li>/, '普通无序列表仍应正常识别')
})

test('normalizeLooseMarkdown: 编号列表缺少空格时也应识别为有序列表', () => {
  const input = ['*核心模块*', '1.顶部公司Logo', '2.主标题“欢迎登录”'].join('\n')

  const html = md.render(normalizeLooseMarkdown(input))

  assert.match(html, /<strong>核心模块<\/strong>/, '章节标题应保持强调样式')
  assert.match(html, /<ol>/, '编号条目应被识别为有序列表')
  assert.match(html, /<li>顶部公司Logo<\/li>/, '第一条编号列表应正常渲染')
  assert.match(html, /<li>主标题“欢迎登录”<\/li>/, '第二条编号列表应正常渲染')
})
