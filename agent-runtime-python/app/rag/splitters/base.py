"""文档切分器基类与注册中心。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.rag.models import DocumentChunk


class DocumentSplitter(ABC):
    """文档切分器抽象基类。

    子类需实现 split() 方法，将原始文档内容切分为语义完整的片段。
    """

    @abstractmethod
    async def split(self, content: str, metadata: dict[str, Any] | None = None) -> list[DocumentChunk]:
        """将文档内容切分为片段。

        Args:
            content: 文档原始文本内容
            metadata: 附加元数据（如 library_slug、filename 等），可写入 chunk 的 metadata 字段

        Returns:
            切分后的 DocumentChunk 列表
        """


class SplitterRegistry:
    """切分器注册中心 — 按文件扩展名注册和获取切分器。

    使用方式:
        registry = SplitterRegistry()
        registry.register(".md", MarkdownSplitter)
        splitter = registry.get(".md")
    """

    def __init__(self) -> None:
        self._splitters: dict[str, type[DocumentSplitter]] = {}
        self._instances: dict[str, DocumentSplitter] = {}

    def register(self, file_extension: str, splitter_cls: type[DocumentSplitter], **kwargs: Any) -> None:
        """注册切分器类。

        Args:
            file_extension: 文件扩展名，如 ".md"
            splitter_cls: 切分器类（非实例）
            **kwargs: 创建实例时传入的构造参数
        """
        ext = file_extension.lower()
        self._splitters[ext] = splitter_cls
        self._instances[ext] = splitter_cls(**kwargs)

    def get(self, file_extension: str) -> DocumentSplitter | None:
        """按文件扩展名获取切分器实例。

        Args:
            file_extension: 文件扩展名，如 ".md"

        Returns:
            切分器实例，未注册时返回 None
        """
        ext = file_extension.lower()
        return self._instances.get(ext)

    def supported_extensions(self) -> list[str]:
        """返回所有已注册的文件扩展名。"""
        return list(self._splitters.keys())
