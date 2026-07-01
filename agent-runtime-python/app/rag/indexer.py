"""索引服务 — 扫描 knowledge/ 目录，增量比对，切分，embedding，写入 PG。"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import asyncpg
from langchain_openai import OpenAIEmbeddings

from app.rag.splitters.base import SplitterRegistry

logger = logging.getLogger(__name__)


class KnowledgeIndexer:
    """知识库索引服务。

    支持：
    - 增量索引：比对 file_hash，只处理新增/修改/删除的文件
    - 全量重建：embedding 模型变更时清空重建
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        embedding_model: OpenAIEmbeddings,
        splitter_registry: SplitterRegistry,
    ) -> None:
        self._pool = pool
        self._embedding_model = embedding_model
        self._splitter_registry = splitter_registry

    async def index_documents(self, knowledge_dir: Path) -> None:
        """增量索引：扫描 knowledge/ 目录，处理新增/修改/删除的文件。"""
        if not knowledge_dir.exists():
            return

        # 获取所有 .md 文件
        md_files: list[tuple[str, str, Path]] = []  # (library_slug, filename, path)
        for lib_dir in knowledge_dir.iterdir():
            if not lib_dir.is_dir() or lib_dir.name.startswith("."):
                continue
            for md_file in lib_dir.glob("*.md"):
                md_files.append((lib_dir.name, md_file.name, md_file))

        if not md_files:
            logger.info("知识库目录下没有 Markdown 文件")
            return

        # 获取 PG 中已有的文档记录
        async with self._pool.acquire() as conn:
            existing_docs = await conn.fetch(
                "SELECT id, library_slug, filename, source_path, file_hash FROM knowledge_document"
            )
        existing_map: dict[str, dict] = {
            f"{row['library_slug']}/{row['filename']}": dict(row) for row in existing_docs
        }

        # 比对：新增/修改/删除
        current_keys = {f"{slug}/{filename}" for slug, filename, _ in md_files}
        existing_keys = set(existing_map.keys())

        # 删除：PG 有但文件系统没有
        deleted_keys = existing_keys - current_keys
        for key in deleted_keys:
            doc = existing_map[key]
            await self._delete_document(doc["id"])
            logger.info("删除文档: %s", key)

        # 新增/修改
        indexed_count = 0
        for slug, filename, file_path in md_files:
            key = f"{slug}/{filename}"
            file_hash = self._compute_file_hash(file_path)

            if key in existing_map:
                # 已存在，检查 hash
                if existing_map[key]["file_hash"] == file_hash:
                    continue  # 未变化，跳过
                # 修改：先删旧 chunk，再重新索引
                await self._delete_document(existing_map[key]["id"])
                logger.info("文档已修改，重建索引: %s", key)

            # 索引文件
            await self._index_file(slug, filename, file_path, file_hash)
            indexed_count += 1

        # 更新 library 的 doc_count 和 indexed_at
        await self._update_library_stats()

        logger.info("增量索引完成: 新增/修改 %d 个文件，删除 %d 个文件", indexed_count, len(deleted_keys))

    async def full_reindex(self, knowledge_dir: Path) -> None:
        """全量重建索引（embedding 模型变更时调用）。"""
        logger.info("开始全量重建索引...")

        # 清空所有文档和 chunk
        async with self._pool.acquire() as conn:
            await conn.execute("TRUNCATE knowledge_document CASCADE")

        # 重新索引所有文件
        if not knowledge_dir.exists():
            logger.warning("知识库目录不存在: %s", knowledge_dir)
            return

        indexed_count = 0
        for lib_dir in knowledge_dir.iterdir():
            if not lib_dir.is_dir() or lib_dir.name.startswith("."):
                continue
            for md_file in lib_dir.glob("*.md"):
                file_hash = self._compute_file_hash(md_file)
                await self._index_file(lib_dir.name, md_file.name, md_file, file_hash)
                indexed_count += 1

        # 更新 library 统计
        await self._update_library_stats()

        logger.info("全量重建索引完成: 共索引 %d 个文件", indexed_count)

    async def _index_file(self, library_slug: str, filename: str, file_path: Path, file_hash: str) -> None:
        """索引单个文件：读取 → 切分 → embedding → 写入 PG。"""
        content = file_path.read_text(encoding="utf-8")
        if not content.strip():
            return

        # 切分
        splitter = self._splitter_registry.get(".md")
        if splitter is None:
            logger.warning("没有注册 .md 切分器，跳过文件: %s", filename)
            return

        chunks = await splitter.split(content, metadata={"library_slug": library_slug, "filename": filename})
        if not chunks:
            return

        # 计算 embedding
        texts = [chunk.content for chunk in chunks]
        try:
            embeddings = await self._embedding_model.aembed_documents(texts)
        except Exception as e:
            logger.error("Embedding 计算失败: %s, 错误: %s", filename, e)
            return

        # 写入 PG
        source_path = str(file_path).replace("\\", "/")
        async with self._pool.acquire() as conn:
            # 插入文档记录
            doc_id = await conn.fetchval(
                """INSERT INTO knowledge_document (library_slug, filename, source_path, file_hash, chunk_count, indexed_at)
                   VALUES ($1, $2, $3, $4, $5, NOW())
                   RETURNING id""",
                library_slug,
                filename,
                source_path,
                file_hash,
                len(chunks),
            )

            # 批量插入 chunk（向量转换为 string 格式供 pgvector）
            await conn.executemany(
                """INSERT INTO knowledge_chunk (doc_id, library_slug, heading, content, chunk_index, embedding)
                   VALUES ($1, $2, $3, $4, $5, $6::vector)""",
                [
                    (doc_id, chunk.library_slug, chunk.heading, chunk.content, chunk.chunk_index, str(embedding))
                    for chunk, embedding in zip(chunks, embeddings)
                ],
            )

        logger.debug("索引文件: %s/%s, %d chunks", library_slug, filename, len(chunks))

    async def _delete_document(self, doc_id: int) -> None:
        """删除文档及其所有 chunk。"""
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM knowledge_document WHERE id = $1", doc_id)

    async def _update_library_stats(self) -> None:
        """更新所有 library 的 doc_count 和 indexed_at。"""
        async with self._pool.acquire() as conn:
            # 更新有文档的库
            await conn.execute(
                """UPDATE knowledge_library l
                   SET doc_count = (SELECT COUNT(*) FROM knowledge_document d WHERE d.library_slug = l.slug),
                       indexed_at = NOW()
                   WHERE EXISTS (SELECT 1 FROM knowledge_document d WHERE d.library_slug = l.slug)"""
            )
            # 清空空库的计数
            await conn.execute(
                """UPDATE knowledge_library
                   SET doc_count = 0, indexed_at = NULL
                   WHERE NOT EXISTS (SELECT 1 FROM knowledge_document d WHERE d.library_slug = knowledge_library.slug)"""
            )

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """计算文件 MD5 哈希。"""
        content = file_path.read_bytes()
        return hashlib.md5(content).hexdigest()
