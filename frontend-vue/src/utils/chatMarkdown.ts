const FULL_LINE_EMPHASIS_RE = /^(\s*)\*\s*([^*\n][^*\n]*?)\s*\*(\s*)$/gm
const HEADING_RE = /^(#{1,6})([^#\s])/gm
const DASH_LIST_RE = /^(\s*-)(\S)/gm
const STAR_LIST_RE = /^(\s*\*)(?!\*)(\S)/gm
const ORDERED_LIST_RE = /^(\s*\d+\.)(\S)/gm

/**
 * 归一化模型常见的宽松 Markdown：
 * - `*项目信息*` 这类全行强调，转成更稳定的 `**项目信息**`
 * - `-项目类型` / `1.顶部Logo` 自动补空格
 * - `##标题` 自动补空格
 */
export function normalizeLooseMarkdown(text: string): string {
  return text
    .replace(HEADING_RE, '$1 $2')
    .replace(FULL_LINE_EMPHASIS_RE, '$1**$2**$3')
    .replace(DASH_LIST_RE, '$1 $2')
    .replace(STAR_LIST_RE, '$1 $2')
    .replace(ORDERED_LIST_RE, '$1 $2')
}
