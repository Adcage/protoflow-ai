"""RAG 数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LibraryInfo:
    """文档库信息。"""

    slug: str
    display_name: str
    description: str = ""
    doc_count: int = 0
    indexed_at: str | None = None


@dataclass(frozen=True)
class DocumentInfo:
    """文档信息。"""

    id: int
    library_slug: str
    filename: str
    source_path: str
    file_hash: str
    chunk_count: int = 0
    indexed_at: str | None = None


@dataclass(frozen=True)
class DocumentChunk:
    """文档片段（切分结果，写入 PG 前的中间结构）。"""

    content: str
    heading: str = ""
    chunk_index: int = 0
    library_slug: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    """检索结果。"""

    content: str
    heading: str
    library_slug: str
    similarity: float
    doc_id: int = 0
