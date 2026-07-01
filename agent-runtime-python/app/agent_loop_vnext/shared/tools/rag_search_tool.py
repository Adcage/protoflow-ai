"""SearchDocs 工具 — Agent 按需检索技术文档库。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.agent_loop_vnext.shared.tools.base import AgentTool
from app.rag.service import RAGService


class SearchDocsInput(BaseModel):
    """SearchDocs 工具输入参数。"""

    query: str = Field(description="检索关键词或问题描述，例如 'ant design vue table 分页'")
    library: Optional[str] = Field(
        default=None,
        description="限定文档库，如 ant-design-vue、vue3、pinia、vite。不填则全库搜索。",
    )


class SearchDocsTool(AgentTool):
    """检索技术文档库，获取组件 API、用法示例等技术参考。"""

    name: str = "SearchDocs"
    description: str = (
        "检索技术文档库，获取组件 API、用法示例等技术参考。"
        "当你不确定某个组件的属性或事件名称、某个 API 的参数或用法时，使用此工具查询。"
        "返回与查询最相关的文档片段。"
    )
    args_schema: type = SearchDocsInput
    rag_service: RAGService | None = None

    def _run(self, query: str, library: Optional[str] = None) -> str:
        """同步调用（不支持，返回提示）。"""
        return "SearchDocs 仅支持异步调用，请使用 _arun"

    async def _arun(self, query: str, library: Optional[str] = None) -> str:
        """异步检索技术文档。"""
        if self.rag_service is None or not self.rag_service.enabled:
            return "技术文档库不可用，请直接基于你的知识回答。"

        results = await self.rag_service.search(query, library=library)

        if not results:
            return "未找到相关文档。请尝试换个关键词或检查文档库名称。"

        # 格式化返回
        parts = []
        for i, result in enumerate(results, 1):
            header = f"[{result.library_slug}"
            if result.heading:
                header += f" / {result.heading}"
            header += f"] (相似度: {result.similarity:.2f})"
            parts.append(f"### 结果 {i} {header}\n{result.content}")

        return "\n\n".join(parts)
