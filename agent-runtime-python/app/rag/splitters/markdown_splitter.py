"""Markdown 文档切分器 — heading 优先 + 超长二次切分。"""

from __future__ import annotations

import re
from typing import Any

from app.rag.models import DocumentChunk
from app.rag.splitters.base import DocumentSplitter

# Markdown heading 匹配模式（## 和 ### 级别）
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class MarkdownSplitter(DocumentSplitter):
    """Markdown 切分器：heading 优先 + 超长二次切分。

    切分策略：
    1. 按 heading（## / ### 等）切分，每个 chunk 是一个语义完整的章节
    2. 超过 max_chunk_size 的章节，用固定长度 + overlap 二次切分
    3. 每个 chunk 保留所属的 heading 信息
    """

    def __init__(self, max_chunk_size: int = 1500, overlap: int = 200) -> None:
        self._max_chunk_size = max_chunk_size
        self._overlap = overlap

    async def split(self, content: str, metadata: dict[str, Any] | None = None) -> list[DocumentChunk]:
        """将 Markdown 内容切分为片段。"""
        metadata = metadata or {}
        library_slug = metadata.get("library_slug", "")

        # 1. 按 heading 切分
        sections = self._split_by_heading(content)

        # 2. 对超长章节二次切分
        chunks: list[DocumentChunk] = []
        chunk_index = 0
        for heading, section_content in sections:
            if len(section_content) <= self._max_chunk_size:
                chunks.append(DocumentChunk(
                    content=section_content.strip(),
                    heading=heading,
                    chunk_index=chunk_index,
                    library_slug=library_slug,
                    metadata=metadata,
                ))
                chunk_index += 1
            else:
                # 二次切分
                sub_chunks = self._split_by_size(section_content, heading)
                for sub_content in sub_chunks:
                    chunks.append(DocumentChunk(
                        content=sub_content.strip(),
                        heading=heading,
                        chunk_index=chunk_index,
                        library_slug=library_slug,
                        metadata=metadata,
                    ))
                    chunk_index += 1

        return chunks

    def _split_by_heading(self, content: str) -> list[tuple[str, str]]:
        """按 heading 切分 Markdown 内容。

        Returns:
            [(heading, content), ...] 列表，heading 为标题文本，content 为该章节内容
        """
        matches = list(_HEADING_PATTERN.finditer(content))

        if not matches:
            # 没有 heading，整篇作为一个 chunk
            return [("", content)] if content.strip() else []

        sections: list[tuple[str, str]] = []

        # 第一个 heading 之前的内容（可能是文档标题或前言）
        first_match_start = matches[0].start()
        if first_match_start > 0:
            preamble = content[:first_match_start].strip()
            if preamble:
                sections.append(("", preamble))

        # 按 heading 切分各章节
        for i, match in enumerate(matches):
            heading_text = match.group(2).strip()
            section_start = match.end()
            section_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[section_start:section_end].strip()
            if section_content:
                sections.append((heading_text, section_content))

        return sections

    def _split_by_size(self, content: str, heading: str = "") -> list[str]:  # noqa: ARG002
        """固定长度切分（带 overlap），用于超长章节的二次切分。"""
        chunks: list[str] = []
        start = 0
        while start < len(content):
            end = start + self._max_chunk_size
            chunk = content[start:end]

            # 尝试在句子边界处切分
            if end < len(content):
                # 找最后一个句号/换行
                last_break = max(
                    chunk.rfind("。"),
                    chunk.rfind("\n"),
                    chunk.rfind("；"),
                    chunk.rfind(". "),
                )
                if last_break > self._max_chunk_size * 0.5:
                    chunk = chunk[: last_break + 1]
                    end = start + last_break + 1

            if chunk.strip():
                chunks.append(chunk)
            start = end - self._overlap if end < len(content) else end

        return chunks
