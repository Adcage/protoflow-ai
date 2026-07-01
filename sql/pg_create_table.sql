-- RAG 技术文档库表结构 (PostgreSQL + pgvector)
-- 使用前请确保已安装 pgvector 扩展: CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- 文档库
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_library (
    slug VARCHAR(100) PRIMARY KEY,         -- 目录名标识，如 ant-design-vue
    display_name VARCHAR(200) NOT NULL,     -- 前端展示名，如 Ant Design Vue 组件库
    description TEXT DEFAULT '',            -- 文档库描述
    doc_count INT DEFAULT 0,               -- 文档数量（冗余，避免 COUNT 查询）
    indexed_at TIMESTAMP,                  -- 最后索引时间
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 文档
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_document (
    id BIGSERIAL PRIMARY KEY,
    library_slug VARCHAR(100) NOT NULL REFERENCES knowledge_library(slug) ON DELETE CASCADE,
    filename VARCHAR(200) NOT NULL,         -- 文件名，如 table.md
    source_path VARCHAR(500) NOT NULL,      -- 完整路径，如 knowledge/ant-design-vue/table.md
    file_hash VARCHAR(64) NOT NULL,         -- MD5，增量比对用
    chunk_count INT DEFAULT 0,              -- chunk 数量（冗余）
    indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(library_slug, filename)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_document_library ON knowledge_document (library_slug);

-- ============================================================
-- 文档片段 + 向量
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id BIGSERIAL PRIMARY KEY,
    doc_id BIGINT NOT NULL REFERENCES knowledge_document(id) ON DELETE CASCADE,
    library_slug VARCHAR(100) NOT NULL,     -- 冗余，避免检索时 JOIN
    heading VARCHAR(500) DEFAULT '',         -- 章节标题
    content TEXT NOT NULL,                   -- chunk 文本
    chunk_index INT NOT NULL,                -- 文档内序号
    embedding VECTOR(1536),                  -- pgvector 向量（OpenAI text-embedding-3-small 维度）
    created_at TIMESTAMP DEFAULT NOW()
);

-- 向量索引（IVFFlat，适合中小数据量；数据量超过 10 万条时可切换到 HNSW）
CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_embedding
    ON knowledge_chunk USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 按文档库过滤索引
CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_library ON knowledge_chunk (library_slug);

-- 文档关联索引
CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_doc ON knowledge_chunk (doc_id);

-- ============================================================
-- 系统配置
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_meta (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 初始化：记录 embedding 模型名为空（首次配置后由 Python 写入）
INSERT INTO knowledge_meta (key, value)
VALUES ('embedding_model_name', '')
ON CONFLICT (key) DO NOTHING;
