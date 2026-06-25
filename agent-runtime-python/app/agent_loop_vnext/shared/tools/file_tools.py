"""vNext 文件操作工具集：view / create / str_replace / insert。

参考 Anthropic 官方 str_replace_based_edit_tool 设计。
所有 path 参数均为相对于工作区根目录的相对路径。
底层复用 app.tools.file_tools.FileTools 执行实际文件操作。
"""

import logging
import os
from typing import Type

from pydantic import BaseModel, Field

from app.agent_loop_vnext.shared.tools.base import AgentTool
from app.tools.file_tools import FileTools

logger = logging.getLogger("app.agent_loop_vnext.shared.tools.file_tools")


# --- Input Schemas ---

class ViewInput(BaseModel):
    path: str = Field(description="文件或目录的相对路径，例如 src/App.vue")
    view_range: list[int] | None = Field(
        default=None,
        description="查看的行范围 [start, end]，1-indexed，end=-1 表示到文件末尾。仅查看文件时有效。",
    )


class CreateInput(BaseModel):
    path: str = Field(description="要创建的文件相对路径，例如 src/App.vue。文件已存在则报错。")
    content: str = Field(description="文件内容")


class StrReplaceInput(BaseModel):
    path: str = Field(description="要修改的文件相对路径，例如 src/App.vue")
    old_str: str = Field(description="要替换的原始文本，必须精确匹配（包括缩进和空格）")
    new_str: str = Field(description="替换后的新文本")


class InsertInput(BaseModel):
    path: str = Field(description="要修改的文件相对路径，例如 src/App.vue")
    insert_line: int = Field(description="在第几行之后插入，0 表示文件开头")
    insert_text: str = Field(description="要插入的文本")


# --- Tools ---

class ViewTool(AgentTool):
    name: str = "view"
    description: str = "查看文件内容或列出目录结构。目录为空时返回'目录为空'，文件为空时返回'文件内容为空'。"
    args_schema: Type[BaseModel] = ViewInput
    file_tools: FileTools | None = None

    async def _arun(self, path: str, view_range: list[int] | None = None) -> str:
        abs_path = self.file_tools._workspace.resolve(path)

        if os.path.isdir(abs_path):
            result = await self.file_tools.read_dir(path)
            return result if result else "目录为空"

        if not os.path.exists(abs_path):
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                f"文件不存在: {path}", code=AgentErrorCode.TOOL_CALL_FAILED
            )

        content = await self.file_tools.read_file(path)
        if not content.strip():
            return "文件内容为空"

        if view_range and len(view_range) == 2:
            lines = content.splitlines()
            start, end = view_range
            if end == -1 or end > len(lines):
                end = len(lines)
            if start < 1:
                start = 1
            content = "\n".join(lines[start - 1:end])

        return content


class CreateTool(AgentTool):
    name: str = "create"
    description: str = "创建新文件。如果文件已存在则报错。"
    args_schema: Type[BaseModel] = CreateInput
    file_tools: FileTools | None = None

    async def _arun(self, path: str, content: str) -> str:
        abs_path = self.file_tools._workspace.resolve(path)
        if os.path.exists(abs_path):
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                f"文件已存在: {path}", code=AgentErrorCode.TOOL_CALL_FAILED
            )
        return await self.file_tools.write_file(path, content)


class StrReplaceTool(AgentTool):
    name: str = "str_replace"
    description: str = "替换文件中精确匹配的文本。用于对已有文件做精细修改。old_str 必须精确匹配（包括缩进和空格）。"
    args_schema: Type[BaseModel] = StrReplaceInput
    file_tools: FileTools | None = None

    async def _arun(self, path: str, old_str: str, new_str: str) -> str:
        if not old_str:
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                "old_str 不能为空", code=AgentErrorCode.TOOL_CALL_FAILED
            )

        return await self.file_tools.modify_file(path, old_str, new_str)


class InsertTool(AgentTool):
    name: str = "insert"
    description: str = "在文件的指定行号后插入文本。0 表示在文件开头插入。"
    args_schema: Type[BaseModel] = InsertInput
    file_tools: FileTools | None = None

    async def _arun(self, path: str, insert_line: int, insert_text: str) -> str:
        from app.core.error_codes import AgentErrorCode
        from app.core.exceptions import AgentRuntimeError

        abs_path = self.file_tools._workspace.resolve(path)
        if not os.path.exists(abs_path):
            raise AgentRuntimeError(
                f"文件不存在: {path}", code=AgentErrorCode.TOOL_CALL_FAILED
            )

        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if insert_line < 0 or insert_line > total_lines:
            raise AgentRuntimeError(
                f"insert_line {insert_line} 超出文件行数范围 (0-{total_lines})",
                code=AgentErrorCode.TOOL_CALL_FAILED,
            )

        lines.insert(insert_line, insert_text.rstrip("\n") + "\n")

        with open(abs_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        logger.info("insert | path=%s line=%d len=%d", path, insert_line, len(insert_text))
        return f"插入成功: {path}"
