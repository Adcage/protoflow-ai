"""RAG 服务门面 — 统一管理初始化、索引、检索、状态。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.modeling.roles import ModelRole
from app.rag.config import RAGConfig
from app.rag.db import DatabaseManager
from app.rag.indexer import KnowledgeIndexer
from app.rag.library_sync import LibrarySyncService
from app.rag.models import LibraryInfo, SearchResult
from app.rag.retriever import KnowledgeRetriever
from app.rag.splitters.base import SplitterRegistry
from app.rag.splitters.markdown_splitter import MarkdownSplitter
from app.services.embedding_factory import EmbeddingModelFactory

if TYPE_CHECKING:
    from app.modeling.resolver import ModelResolver, ResolvedModelConfig

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 服务门面，统一管理初始化、索引、检索、状态。

    使用方式：
        rag = RAGService()
        await rag.initialize(model_resolver, embedding_factory)
        if rag.enabled:
            results = await rag.search("ant design vue table pagination")
    """

    def __init__(self) -> None:
        self._enabled: bool = False
        self._config: RAGConfig | None = None
        self._db: DatabaseManager | None = None
        self._retriever: KnowledgeRetriever | None = None
        self._indexer: KnowledgeIndexer | None = None
        self._library_sync: LibrarySyncService | None = None
        self._embedding_model: OpenAIEmbeddings | None = None
        self._cached_libraries: list[LibraryInfo] = []

    @property
    def enabled(self) -> bool:
        """RAG 功能是否可用。"""
        return self._enabled

    async def initialize(self, model_resolver: ModelResolver) -> None:  # type: ignore[name-defined]
        """启动时初始化：连接 PG、解析 embedding 配置、建表、触发索引。

        Args:
            model_resolver: ModelResolver 实例，用于解析 EMBEDDING 角色配置
        """
        try:
            # 1. 解析 embedding 配置
            self._config = RAGConfig.from_settings(settings)

            # 尝试 resolve EMBEDDING 角色
            try:
                resolved: ResolvedModelConfig | None = model_resolver.resolve(ModelRole.EMBEDDING)  # type: ignore[name-defined]
            except (RuntimeError, KeyError):
                resolved = None

            if resolved is None or not resolved.api_key or not resolved.model_name:
                # TODO: 接入系统级状态感知，通知前端管理员
                logger.error(
                    "RAG 功能未启用：Embedding 模型未配置。"
                    "请配置 app.ai.runtime-models.embedding (provider/base-url/api-key/model-name)"
                )
                self._enabled = False
                return

            # 2. 创建 Embedding 模型
            embedding_factory = EmbeddingModelFactory()
            self._embedding_model = embedding_factory.create({
                "provider": resolved.provider,
                "modelName": resolved.model_name,
                "apiKey": resolved.api_key,
                "baseUrl": resolved.base_url,
            })

            # 3. 连接 PG
            self._db = DatabaseManager(self._config)
            await self._db.initialize()

            # 4. 注册切分器
            splitter_registry = SplitterRegistry()
            splitter_registry.register(
                ".md",
                MarkdownSplitter,
                max_chunk_size=self._config.chunk_max_size,
                overlap=self._config.chunk_overlap,
            )

            # 5. 初始化服务
            pool = self._db.pool
            self._library_sync = LibrarySyncService(pool)
            self._indexer = KnowledgeIndexer(pool, self._embedding_model, splitter_registry)
            self._retriever = KnowledgeRetriever(
                pool,
                self._embedding_model,
                top_k=self._config.search_top_k,
                similarity_threshold=self._config.search_similarity_threshold,
            )

            # 6. 同步 library 信息
            knowledge_dir = Path(self._config.knowledge_dir)
            self._cached_libraries = await self._library_sync.sync(knowledge_dir)

            # 7. 检查 embedding 模型是否变更，决定增量还是全量索引
            await self._check_and_index(knowledge_dir, resolved.model_name)

            self._enabled = True
            logger.info("RAG 功能已启用")

        except Exception as e:
            # TODO: 接入系统级状态感知，通知前端管理员
            logger.error("RAG 初始化失败: %s", e)
            self._enabled = False

    async def search(
        self,
        query: str,
        library: str | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """检索技术文档。

        Args:
            query: 检索查询文本
            library: 限定文档库 slug
            top_k: 返回结果数量

        Returns:
            SearchResult 列表
        """
        if not self._enabled or self._retriever is None:
            return []
        return await self._retriever.search(query, library=library, top_k=top_k)

    async def reindex(self) -> None:
        """手动触发全量重建索引。"""
        if not self._enabled or self._indexer is None or self._config is None:
            logger.warning("RAG 未启用，无法触发重建索引")
            return
        knowledge_dir = Path(self._config.knowledge_dir)
        await self._indexer.full_reindex(knowledge_dir)

    async def list_libraries(self) -> list[LibraryInfo]:
        """获取所有文档库信息。"""
        if not self._enabled or self._library_sync is None:
            return []
        return await self._library_sync.list_libraries()

    def get_available_docs_description(self) -> str:
        """返回 Prompt 注入用的文档库目录描述。"""
        if not self._enabled or self._library_sync is None:
            return ""
        # 从缓存获取 library 列表
        if not self._cached_libraries:
            return "## 可查的技术文档\n你可以使用 SearchDocs 工具检索技术文档库。当你不确定某个组件的 API 或用法时，请主动使用 SearchDocs 查询。"

        parts = ["## 可查的技术文档", "你可以使用 SearchDocs 工具检索以下技术文档库："]
        for lib in self._cached_libraries:
            parts.append(f"- {lib.display_name}: {lib.description}")
        parts.append("当你不确定某个组件的 API 或用法时，请主动使用 SearchDocs 查询。")
        return "\n".join(parts)

    async def close(self) -> None:
        """关闭资源。"""
        if self._db:
            await self._db.close()

    async def _check_and_index(self, knowledge_dir: Path, current_model_name: str) -> None:
        """检查 embedding 模型是否变更，决定增量还是全量索引。"""
        if self._db is None or self._indexer is None:
            raise RuntimeError("RAG 服务未初始化，无法索引")

        pool = self._db.pool
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM knowledge_meta WHERE key = 'embedding_model_name'"
            )

        stored_model_name = row["value"] if row else ""

        if stored_model_name and stored_model_name != current_model_name:
            # 模型变更 → 全量重建
            logger.info(
                "Embedding 模型变更: %s → %s，触发全量重建索引",
                stored_model_name,
                current_model_name,
            )
            await self._indexer.full_reindex(knowledge_dir)
        else:
            # 增量索引
            await self._indexer.index_documents(knowledge_dir)

        # 更新 PG 中的模型名记录
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO knowledge_meta (key, value, updated_at)
                   VALUES ('embedding_model_name', $1, NOW())
                   ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = NOW()""",
                current_model_name,
            )
