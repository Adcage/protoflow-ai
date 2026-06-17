import logging
import os

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.tools.file_tools")


class Workspace:
    def __init__(self, root_path: str) -> None:
        self._root = os.path.abspath(root_path) if root_path else os.path.abspath(".")
        os.makedirs(self._root, exist_ok=True)

    @property
    def root(self) -> str:
        return self._root

    def resolve(self, relative_path: str) -> str:
        if not relative_path:
            raise AgentRuntimeError("路径不能为空", code=AgentErrorCode.PATH_TRAVERSAL_BLOCKED)
        normalized = os.path.normpath(os.path.join(self._root, relative_path))
        if not normalized.startswith(self._root):
            raise AgentRuntimeError(
                f"路径穿越被拦截: {relative_path}",
                code=AgentErrorCode.PATH_TRAVERSAL_BLOCKED,
            )
        return normalized

    def ensure_dir(self, file_path: str) -> None:
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)


class FileTools:
    def __init__(self, workspace: Workspace, skill_dir: str | None = None) -> None:
        self._workspace = workspace
        self._skill_dir = os.path.abspath(skill_dir) if skill_dir else None

    async def read_file(self, relative_path: str, scope: str = "workspace") -> str:
        if scope == "skill":
            abs_path = self._resolve_in_skill(relative_path)
        else:
            abs_path = self._workspace.resolve(relative_path)
        if not os.path.exists(abs_path):
            raise AgentRuntimeError(
                f"文件不存在: {relative_path}", code=AgentErrorCode.TOOL_CALL_FAILED
            )
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise AgentRuntimeError(
                f"读取文件失败: {e}", code=AgentErrorCode.TOOL_CALL_FAILED
            ) from e

    def _resolve_in_skill(self, relative_path: str) -> str:
        if self._skill_dir is None:
            raise AgentRuntimeError(
                "当前无选中skill，无法读取skill资源",
                code=AgentErrorCode.SKILL_RESOURCE_NOT_FOUND,
            )
        if not relative_path:
            raise AgentRuntimeError(
                "路径不能为空", code=AgentErrorCode.PATH_TRAVERSAL_BLOCKED
            )
        normalized = os.path.normpath(os.path.join(self._skill_dir, relative_path))
        if not normalized.startswith(self._skill_dir):
            raise AgentRuntimeError(
                f"路径穿越被拦截: {relative_path}",
                code=AgentErrorCode.PATH_TRAVERSAL_BLOCKED,
            )
        return normalized

    async def write_file(self, relative_path: str, content: str) -> str:
        abs_path = self._workspace.resolve(relative_path)
        try:
            self._workspace.ensure_dir(abs_path)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("write_file | path=%s size=%d", relative_path, len(content))
            return f"写入成功: {relative_path}"
        except Exception as e:
            raise AgentRuntimeError(
                f"写入文件失败: {e}", code=AgentErrorCode.TOOL_CALL_FAILED
            ) from e

    async def modify_file(self, relative_path: str, old_content: str, new_content: str) -> str:
        abs_path = self._workspace.resolve(relative_path)
        if not os.path.exists(abs_path):
            raise AgentRuntimeError(
                f"文件不存在: {relative_path}", code=AgentErrorCode.TOOL_CALL_FAILED
            )
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            if old_content not in file_content:
                raise AgentRuntimeError(
                    f"未找到要替换的内容: {relative_path}",
                    code=AgentErrorCode.TOOL_CALL_FAILED,
                )
            updated = file_content.replace(old_content, new_content, 1)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(updated)
            logger.info("modify_file | path=%s", relative_path)
            return f"修改成功: {relative_path}"
        except AgentRuntimeError:
            raise
        except Exception as e:
            raise AgentRuntimeError(
                f"修改文件失败: {e}", code=AgentErrorCode.TOOL_CALL_FAILED
            ) from e

    async def delete_file(self, relative_path: str) -> str:
        abs_path = self._workspace.resolve(relative_path)
        if not os.path.exists(abs_path):
            raise AgentRuntimeError(
                f"文件不存在: {relative_path}", code=AgentErrorCode.TOOL_CALL_FAILED
            )
        try:
            os.remove(abs_path)
            logger.info("delete_file | path=%s", relative_path)
            return f"删除成功: {relative_path}"
        except Exception as e:
            raise AgentRuntimeError(
                f"删除文件失败: {e}", code=AgentErrorCode.TOOL_CALL_FAILED
            ) from e

    async def read_dir(self, relative_path: str = ".") -> str:
        abs_path = self._workspace.resolve(relative_path)
        if not os.path.exists(abs_path):
            os.makedirs(abs_path, exist_ok=True)
            logger.info("read_dir | path=%s created", relative_path)
            return ""
        if not os.path.isdir(abs_path):
            raise AgentRuntimeError(
                f"路径不是目录: {relative_path}", code=AgentErrorCode.TOOL_CALL_FAILED
            )
        try:
            entries = os.listdir(abs_path)
            logger.info("read_dir | path=%s entries=%d", relative_path, len(entries))
            return "\n".join(entries)
        except Exception as e:
            raise AgentRuntimeError(
                f"读取目录失败: {e}", code=AgentErrorCode.TOOL_CALL_FAILED
            ) from e
