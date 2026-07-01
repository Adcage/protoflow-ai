"""知识库管理 API — 供管理后台调用。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/knowledge", tags=["admin-knowledge"])


# ============================================================
# 数据模型
# ============================================================

class LibraryVO(BaseModel):
    slug: str
    display_name: str = ""
    description: str = ""
    doc_count: int = 0
    indexed_at: str | None = None
    has_index_json: bool = False


class DocumentVO(BaseModel):
    id: str
    library_slug: str
    filename: str
    file_size: int = 0
    file_hash: str = ""
    chunk_count: int = 0
    indexed_at: str | None = None


class RagStatusVO(BaseModel):
    enabled: bool = False
    embedding_configured: bool = False
    embedding_model: str = ""
    total_libraries: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    last_indexed_at: str | None = None
    error_message: str = ""


class ReindexResponse(BaseModel):
    success: bool
    message: str = ""
    documents_indexed: int = 0


class DeleteResponse(BaseModel):
    success: bool
    message: str = ""


# ============================================================
# 辅助函数
# ============================================================

def _get_knowledge_dir() -> Path:
    """获取知识库目录路径。"""
    return Path(settings.knowledge_dir).resolve()


def _get_library_meta(lib_dir: Path) -> dict:
    """读取 library 的 index.json 元数据。"""
    index_path = lib_dir / "index.json"
    if index_path.exists():
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _count_md_files(lib_dir: Path) -> int:
    """统计目录下 .md 文件数量。"""
    return len(list(lib_dir.glob("*.md")))


# ============================================================
# API 端点
# ============================================================

@router.get("/status", response_model=RagStatusVO)
async def get_rag_status():
    """获取 RAG 系统状态。"""
    knowledge_dir = _get_knowledge_dir()

    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        enabled = rag.enabled if rag else False
        embedding_model = ""
        error_message = ""
        if hasattr(rag, "_embedding_model") and rag._embedding_model:
            embedding_model = getattr(rag._embedding_model, "model", "")
    except Exception as e:
        enabled = False
        embedding_model = ""
        error_message = str(e)

    # 统计文件系统数据
    total_libs = 0
    total_docs = 0
    if knowledge_dir.exists():
        for lib_dir in knowledge_dir.iterdir():
            if lib_dir.is_dir() and not lib_dir.name.startswith("."):
                total_libs += 1
                total_docs += _count_md_files(lib_dir)

    # 统计 PG 数据
    total_chunks = 0
    last_indexed = None
    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        if rag and rag.enabled:
            async with rag._db.pool.acquire() as conn:
                total_chunks = await conn.fetchval("SELECT COUNT(*) FROM knowledge_chunk")
                row = await conn.fetchval("SELECT MAX(indexed_at) FROM knowledge_library")
                last_indexed = str(row) if row else None
    except Exception:
        pass

    return RagStatusVO(
        enabled=enabled,
        embedding_configured=bool(embedding_model),
        embedding_model=embedding_model,
        total_libraries=total_libs,
        total_documents=total_docs,
        total_chunks=total_chunks or 0,
        last_indexed_at=last_indexed,
        error_message=error_message,
    )


@router.get("/libraries", response_model=list[LibraryVO])
async def list_libraries():
    """列出所有文档库。"""
    knowledge_dir = _get_knowledge_dir()
    if not knowledge_dir.exists():
        return []

    # 从 PG 获取信息（如果有）
    pg_libs: dict[str, tuple[int, str | None]] = {}
    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        if rag and rag.enabled:
            async with rag._db.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT slug, doc_count, indexed_at FROM knowledge_library"
                )
                for row in rows:
                    pg_libs[row["slug"]] = (row["doc_count"], str(row["indexed_at"]) if row["indexed_at"] else None)
    except Exception:
        pass

    libraries: list[LibraryVO] = []
    for lib_dir in sorted(knowledge_dir.iterdir()):
        if not lib_dir.is_dir() or lib_dir.name.startswith("."):
            continue

        slug = lib_dir.name
        meta = _get_library_meta(lib_dir)
        pg_info = pg_libs.get(slug, (0, None))
        md_count = _count_md_files(lib_dir)
        has_index = (lib_dir / "index.json").exists()

        libraries.append(LibraryVO(
            slug=slug,
            display_name=meta.get("displayName", slug),
            description=meta.get("description", ""),
            doc_count=max(md_count, pg_info[0]),
            indexed_at=pg_info[1],
            has_index_json=has_index,
        ))

    return libraries


@router.get("/documents", response_model=list[DocumentVO])
async def list_documents(library: str | None = None):
    """列出文档（可选按库过滤）。"""
    knowledge_dir = _get_knowledge_dir()
    if not knowledge_dir.exists():
        return []

    # 从 PG 获取 chunk 信息（用 library_slug + filename 作为 key）
    pg_chunks: dict[str, int] = {}
    pg_indexed: dict[str, str] = {}
    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        if rag and rag.enabled:
            async with rag._db.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT library_slug, filename, chunk_count, indexed_at FROM knowledge_document"
                )
                for row in rows:
                    key = row["library_slug"] + "/" + row["filename"]
                    pg_chunks[key] = row["chunk_count"]
                    if row["indexed_at"]:
                        pg_indexed[key] = str(row["indexed_at"])
    except Exception:
        pass

    documents: list[DocumentVO] = []
    for lib_dir in sorted(knowledge_dir.iterdir()):
        if not lib_dir.is_dir() or lib_dir.name.startswith("."):
            continue
        if library and lib_dir.name != library:
            continue

        for md_file in sorted(lib_dir.glob("*.md")):
            source_path = str(md_file).replace("\\", "/")
            pg_key = lib_dir.name + "/" + md_file.name
            from app.rag.indexer import KnowledgeIndexer
            file_hash = KnowledgeIndexer._compute_file_hash(md_file)

            documents.append(DocumentVO(
                id=source_path,
                library_slug=lib_dir.name,
                filename=md_file.name,
                file_size=md_file.stat().st_size,
                file_hash=file_hash,
                chunk_count=pg_chunks.get(pg_key, 0),
                indexed_at=pg_indexed.get(pg_key),
            ))

    return documents


@router.post("/upload", response_model=DocumentVO)
async def upload_document(
    library: str = Form(...),
    file: UploadFile = File(...),
):
    """上传 Markdown 文档到指定库。"""
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="仅支持 .md 格式文件")

    knowledge_dir = _get_knowledge_dir()
    lib_dir = knowledge_dir / library
    lib_dir.mkdir(parents=True, exist_ok=True)

    # 检查 index.json 是否存在（没有就自动创建）
    index_path = lib_dir / "index.json"
    if not index_path.exists():
        index_path.write_text(
            json.dumps({"displayName": library, "description": ""}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 保存文件
    content = await file.read()
    file_path = lib_dir / file.filename
    file_path.write_bytes(content)

    from app.rag.indexer import KnowledgeIndexer
    file_hash = KnowledgeIndexer._compute_file_hash(file_path)

    # 触发索引
    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        if rag and rag.enabled:
            await rag.reindex()
    except Exception as e:
        logger.warning("上传后重建索引失败: %s", e)

    return DocumentVO(
        id=str(file_path).replace("\\", "/"),
        library_slug=library,
        filename=file.filename,
        file_size=file_path.stat().st_size,
        file_hash=file_hash,
    )


@router.delete("/document", response_model=DeleteResponse)
async def delete_document(library: str, filename: str):
    """删除文档。"""
    knowledge_dir = _get_knowledge_dir()
    file_path = knowledge_dir / library / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文档不存在")

    file_path.unlink()

    # 触发索引
    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        if rag and rag.enabled:
            await rag.reindex()
    except Exception as e:
        logger.warning("删除后重建索引失败: %s", e)

    return DeleteResponse(success=True, message="文档已删除")


@router.post("/reindex", response_model=ReindexResponse)
async def trigger_reindex():
    """触发全量重建索引。"""
    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        if not rag or not rag.enabled:
            return ReindexResponse(success=False, message="RAG 服务未启用")

        await rag.reindex()

        # 统计
        async with rag._db.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_document")

        return ReindexResponse(success=True, documents_indexed=count or 0)
    except Exception as e:
        logger.error("重建索引失败: %s", e)
        return ReindexResponse(success=False, message=str(e))


@router.post("/library", response_model=LibraryVO)
async def create_library(slug: str, display_name: str = "", description: str = ""):
    """创建新文档库。"""
    knowledge_dir = _get_knowledge_dir()
    lib_dir = knowledge_dir / slug

    if lib_dir.exists():
        raise HTTPException(status_code=400, detail="文档库已存在")

    lib_dir.mkdir(parents=True)
    index_path = lib_dir / "index.json"
    index_path.write_text(
        json.dumps({"displayName": display_name or slug, "description": description}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return LibraryVO(
        slug=slug,
        display_name=display_name or slug,
        description=description,
        has_index_json=True,
    )


@router.delete("/library", response_model=DeleteResponse)
async def delete_library(slug: str):
    """删除文档库。"""
    knowledge_dir = _get_knowledge_dir()
    lib_dir = knowledge_dir / slug

    if not lib_dir.exists():
        raise HTTPException(status_code=404, detail="文档库不存在")

    # 删除目录下所有文件
    import shutil
    shutil.rmtree(lib_dir)

    # 触发索引（清空 PG 数据）
    try:
        from app.runtime.orchestrator import _get_rag_service
        rag = _get_rag_service()
        if rag and rag.enabled:
            await rag.reindex()
    except Exception as e:
        logger.warning("删除库后重建索引失败: %s", e)

    return DeleteResponse(success=True, message="文档库已删除")
