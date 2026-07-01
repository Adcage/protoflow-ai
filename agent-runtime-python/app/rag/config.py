"""RAG 配置 — 从全局 Settings 中提取 RAG 相关参数。"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class RAGConfig:
    """RAG 运行时配置，由 Settings 转换而来。"""

    # PostgreSQL 连接
    pg_dsn: str
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str

    # 知识库目录
    knowledge_dir: str

    # 切分参数
    chunk_max_size: int
    chunk_overlap: int

    # 检索参数
    search_top_k: int
    search_similarity_threshold: float

    @classmethod
    def from_settings(cls, settings: Settings) -> RAGConfig:
        """从全局 Settings 实例创建 RAGConfig。"""
        return cls(
            pg_dsn=f"postgresql://{settings.pg_user}:{settings.pg_password}@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}",
            pg_host=settings.pg_host,
            pg_port=settings.pg_port,
            pg_database=settings.pg_database,
            pg_user=settings.pg_user,
            pg_password=settings.pg_password,
            knowledge_dir=settings.knowledge_dir,
            chunk_max_size=settings.rag_chunk_max_size,
            chunk_overlap=settings.rag_chunk_overlap,
            search_top_k=settings.rag_search_top_k,
            search_similarity_threshold=settings.rag_search_similarity_threshold,
        )
