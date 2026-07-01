"""检索服务 — query embedding + PG 向量检索。"""

from __future__ import annotations

import logging

import asyncpg
from langchain_openai import OpenAIEmbeddings

from app.rag.models import SearchResult

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """知识库向量检索服务。"""

    def __init__(
        self,
        pool: asyncpg.Pool,
        embedding_model: OpenAIEmbeddings,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
    ) -> None:
        self._pool = pool
        self._embedding_model = embedding_model
        self._top_k = top_k
        self._similarity_threshold = similarity_threshold

    async def search(
        self,
        query: str,
        library: str | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """语义检索知识库。

        Args:
            query: 检索查询文本
            library: 限定文档库 slug，None 表示全库搜索
            top_k: 返回结果数量，None 使用默认值

        Returns:
            SearchResult 列表，按相似度降序排列
        """
        k = top_k or self._top_k

        # 计算 query embedding
        try:
            query_embedding = await self._embedding_model.aembed_query(query)
        except Exception as e:
            logger.error("查询 embedding 计算失败: %s", e)
            return []

        # PG 向量检索（query_embedding 转换为 string 格式供 pgvector）
        query_vec_str = str(query_embedding)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT c.content, c.heading, c.library_slug, c.doc_id,
                          1 - (c.embedding <=> $1::vector) AS similarity
                   FROM knowledge_chunk c
                   WHERE ($2::varchar IS NULL OR c.library_slug = $2)
                     AND c.embedding IS NOT NULL
                     AND 1 - (c.embedding <=> $1::vector) > $3
                   ORDER BY c.embedding <=> $1::vector
                   LIMIT $4""",
                query_vec_str,
                library,
                self._similarity_threshold,
                k,
            )

        results = [
            SearchResult(
                content=row["content"],
                heading=row["heading"],
                library_slug=row["library_slug"],
                similarity=float(row["similarity"]),
                doc_id=row["doc_id"],
            )
            for row in rows
        ]

        logger.info(
            "RAG 检索: query=%s, library=%s, 命中 %d 条 (top-%d)",
            query[:50],
            library or "全部",
            len(results),
            k,
        )

        return results
