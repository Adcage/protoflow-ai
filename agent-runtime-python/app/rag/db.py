"""PostgreSQL 连接池管理与表初始化。"""

from __future__ import annotations

import logging

import asyncpg

from app.rag.config import RAGConfig

logger = logging.getLogger(__name__)

# 建表 SQL（与 sql/pg_create_table.sql 保持一致）
_CREATE_TABLES_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_library (
    slug VARCHAR(100) PRIMARY KEY,
    display_name VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',
    doc_count INT DEFAULT 0,
    indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_document (
    id BIGSERIAL PRIMARY KEY,
    library_slug VARCHAR(100) NOT NULL REFERENCES knowledge_library(slug) ON DELETE CASCADE,
    filename VARCHAR(200) NOT NULL,
    source_path VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    chunk_count INT DEFAULT 0,
    indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(library_slug, filename)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_document_library ON knowledge_document (library_slug);

CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id BIGSERIAL PRIMARY KEY,
    doc_id BIGINT NOT NULL REFERENCES knowledge_document(id) ON DELETE CASCADE,
    library_slug VARCHAR(100) NOT NULL,
    heading VARCHAR(500) DEFAULT '',
    content TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_embedding
    ON knowledge_chunk USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_library ON knowledge_chunk (library_slug);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_doc ON knowledge_chunk (doc_id);

CREATE TABLE IF NOT EXISTS knowledge_meta (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO knowledge_meta (key, value)
VALUES ('embedding_model_name', '')
ON CONFLICT (key) DO NOTHING;
"""


class DatabaseManager:
    """PostgreSQL 连接池管理与表初始化。"""

    def __init__(self, config: RAGConfig) -> None:
        self._config = config
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        """获取连接池，必须在 ensure_tables() 之后使用。"""
        if self._pool is None:
            raise RuntimeError("PG 连接池未初始化，请先调用 initialize()")
        return self._pool

    async def initialize(self) -> None:
        """创建连接池并初始化表结构。"""
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._config.pg_dsn,
                min_size=2,
                max_size=10,
            )
            logger.info("PG 连接池创建成功: %s:%d/%s", self._config.pg_host, self._config.pg_port, self._config.pg_database)
        except Exception as e:
            logger.error("PG 连接池创建失败: %s", e)
            raise

        await self._ensure_tables()

    async def _ensure_tables(self) -> None:
        """确保表结构存在。"""
        if self._pool is None:
            raise RuntimeError("PG 连接池未初始化")
        async with self._pool.acquire() as conn:
            await conn.execute(_CREATE_TABLES_SQL)
        logger.info("PG 表结构初始化完成")

    async def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PG 连接池已关闭")
