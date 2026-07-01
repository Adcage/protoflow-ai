"""Library 同步服务 — 扫描 knowledge/ 目录，同步 library 信息到 PG。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import asyncpg

from app.rag.models import LibraryInfo

logger = logging.getLogger(__name__)


class LibrarySyncService:
    """文档库同步服务。

    规则：
    - PG 已有 → 以 PG 为准，用 PG 数据覆盖 index.json
    - PG 没有 + 有 index.json → 读 index.json 创建 PG 记录
    - PG 没有 + 没有 index.json → 用目录名创建 PG 记录（兜底）
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def sync(self, knowledge_dir: Path) -> list[LibraryInfo]:
        """扫描 knowledge/ 目录并同步 library 信息到 PG。

        Args:
            knowledge_dir: 知识库根目录路径

        Returns:
            同步后的 LibraryInfo 列表
        """
        if not knowledge_dir.exists():
            logger.warning("知识库目录不存在: %s", knowledge_dir)
            return []

        # 扫描子目录
        dir_entries = [d for d in knowledge_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not dir_entries:
            logger.info("知识库目录下没有子目录: %s", knowledge_dir)
            return []

        libraries: list[LibraryInfo] = []

        for dir_entry in dir_entries:
            slug = dir_entry.name
            index_path = dir_entry / "index.json"

            # 从 index.json 读取元数据
            index_data = self._read_index_json(index_path)
            file_display_name = index_data.get("displayName", slug)
            file_description = index_data.get("description", "")

            # 查 PG 是否已存在
            async with self._pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT slug, display_name, description FROM knowledge_library WHERE slug = $1",
                    slug,
                )

            if existing:
                # PG 已有 → 以 PG 为准，同步写回 index.json
                pg_display_name = existing["display_name"]
                pg_description = existing["description"]

                # 如果 index.json 和 PG 不一致，用 PG 覆盖 index.json
                if pg_display_name != file_display_name or pg_description != file_description:
                    self._write_index_json(index_path, pg_display_name, pg_description)

                libraries.append(LibraryInfo(
                    slug=slug,
                    display_name=pg_display_name,
                    description=pg_description,
                ))
            else:
                # PG 没有 → 从 index.json 或目录名创建
                display_name = file_display_name
                description = file_description

                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO knowledge_library (slug, display_name, description)
                           VALUES ($1, $2, $3)""",
                        slug,
                        display_name,
                        description,
                    )

                # 确保 index.json 存在（PG 为权威，后续修改会同步回来）
                if not index_path.exists():
                    self._write_index_json(index_path, display_name, description)

                libraries.append(LibraryInfo(
                    slug=slug,
                    display_name=display_name,
                    description=description,
                ))
                logger.info("新建文档库: slug=%s, display_name=%s", slug, display_name)

        # 清理 PG 中已不存在目录的 library 记录
        existing_slugs = {d.name for d in dir_entries}
        async with self._pool.acquire() as conn:
            stale = await conn.fetch("SELECT slug FROM knowledge_library")
            for row in stale:
                if row["slug"] not in existing_slugs:
                    await conn.execute("DELETE FROM knowledge_library WHERE slug = $1", row["slug"])
                    logger.info("清理已删除的文档库: slug=%s", row["slug"])

        return libraries

    async def list_libraries(self) -> list[LibraryInfo]:
        """从 PG 获取所有文档库信息。"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT slug, display_name, description, doc_count, indexed_at FROM knowledge_library ORDER BY slug"
            )
        return [
            LibraryInfo(
                slug=row["slug"],
                display_name=row["display_name"],
                description=row["description"],
                doc_count=row["doc_count"],
                indexed_at=str(row["indexed_at"]) if row["indexed_at"] else None,
            )
            for row in rows
        ]

    @staticmethod
    def _read_index_json(path: Path) -> dict:
        """读取 index.json，不存在或解析失败返回空字典。"""
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("读取 index.json 失败: %s, 错误: %s", path, e)
            return {}

    @staticmethod
    def _write_index_json(path: Path, display_name: str, description: str) -> None:
        """写入 index.json。"""
        data = {"displayName": display_name, "description": description}
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("写入 index.json 失败: %s, 错误: %s", path, e)
