import asyncio
import logging
import os
import shlex
import time

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.tools.file_tools import Workspace

logger = logging.getLogger("app.tools.terminal_tools")

_SHELL_OPERATORS = frozenset({"&&", "||", "|", ";", "&", "<", ">", ">>", "<<"})
_SUBCOMMAND_PREFIX = "$("


class TerminalTools:
    def __init__(
        self,
        workspace: Workspace,
        allowed_commands: list[str],
        readonly_commands: list[str] | None = None,
        allowed_script_dirs: list[str] | None = None,
        default_timeout: int = 30,
        max_timeout: int = 120,
        max_output_bytes: int = 10240,
    ) -> None:
        self._workspace = workspace
        self._allowed = [cmd.strip() for cmd in allowed_commands if cmd.strip()]
        self._readonly = [cmd.strip() for cmd in (readonly_commands or []) if cmd.strip()]
        self._allowed_script_dirs = [
            os.path.abspath(d) for d in (allowed_script_dirs or []) if d.strip()
        ]
        self._default_timeout = default_timeout
        self._max_timeout = max_timeout

    async def run_command(
        self,
        command: str,
        timeout: int | None = None,
        readonly: bool = False,
    ) -> str:
        if not command or not command.strip():
            raise AgentRuntimeError(
                "命令不能为空",
                code=AgentErrorCode.TOOL_ARGS_ERROR,
            )

        command = command.strip()

        try:
            tokens = shlex.split(command)
        except ValueError:
            raise AgentRuntimeError(
                f"命令解析失败，可能存在未配对的引号: {command}",
                code=AgentErrorCode.COMMAND_INJECTION_BLOCKED,
            )

        if not tokens:
            raise AgentRuntimeError(
                "命令不能为空",
                code=AgentErrorCode.TOOL_ARGS_ERROR,
            )

        for token in tokens:
            if token in _SHELL_OPERATORS:
                raise AgentRuntimeError(
                    f"检测到命令链接符，已拒绝: {command}",
                    code=AgentErrorCode.COMMAND_INJECTION_BLOCKED,
                )
            if _SUBCOMMAND_PREFIX in token:
                raise AgentRuntimeError(
                    f"检测到命令链接符，已拒绝: {command}",
                    code=AgentErrorCode.COMMAND_INJECTION_BLOCKED,
                )

        prefix = tokens[0]

        # 只读模式校验只读白名单（ls/cat/git/...），写模式校验写白名单（npm/npx/...）。
        # 之前先统一查写白名单再查只读白名单，导致 ls 等只读命令在只读模式下永远被拒。
        if readonly:
            if prefix not in self._readonly:
                raise AgentRuntimeError(
                    f"命令不在只读列表中: {prefix}",
                    code=AgentErrorCode.COMMAND_NOT_ALLOWED,
                )
            if prefix == "python" and self._allowed_script_dirs:
                script_path = self._find_script_path(tokens)
                if script_path is None:
                    raise AgentRuntimeError(
                        "plan 模式下 python 命令必须指定脚本文件路径，不支持 -c 内联代码",
                        code=AgentErrorCode.COMMAND_NOT_ALLOWED,
                    )
                if not self._is_script_in_allowed_dirs(script_path):
                    raise AgentRuntimeError(
                        f"脚本不在允许的目录中: {script_path}",
                        code=AgentErrorCode.COMMAND_NOT_ALLOWED,
                    )
        else:
            if prefix not in self._allowed:
                raise AgentRuntimeError(
                    f"命令不在允许列表中: {prefix}",
                    code=AgentErrorCode.COMMAND_NOT_ALLOWED,
                )

        timeout = min(timeout or self._default_timeout, self._max_timeout)

        start_ms = time.monotonic()
        try:
            result = await self._execute(tokens, timeout)
            duration_ms = (time.monotonic() - start_ms) * 1000
            logger.info(
                "run_command | command=%s duration_ms=%.0f readonly=%s exit_code=%d",
                command,
                duration_ms,
                readonly,
                result["exit_code"],
            )
            return f"[exit_code={result['exit_code']}]\n{result['output']}"
        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start_ms) * 1000
            logger.warning(
                "run_command timeout | command=%s duration_ms=%.0f",
                command,
                duration_ms,
            )
            raise AgentRuntimeError(
                f"命令执行超时 ({timeout}s): {command}",
                code=AgentErrorCode.COMMAND_TIMEOUT,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_ms) * 1000
            logger.error(
                "run_command error | command=%s duration_ms=%.0f error=%s",
                command,
                duration_ms,
                e,
            )
            raise AgentRuntimeError(
                f"命令执行失败: {e}",
                code=AgentErrorCode.COMMAND_EXECUTION_FAILED,
            ) from e

    def _find_script_path(self, tokens: list[str]) -> str | None:
        for i, token in enumerate(tokens[1:], 1):
            if token.startswith("-"):
                if token in ("-m", "-W", "-X", "-E", "-s", "-S", "-O", "-OO", "-v", "-b", "-B", "-I"):
                    continue
                if token == "-c":
                    return None
                continue
            if token.endswith(".py"):
                return os.path.abspath(token)
            return os.path.abspath(token) if not token.startswith("-") else None
        return None

    def _is_script_in_allowed_dirs(self, script_path: str) -> bool:
        if not self._allowed_script_dirs:
            return True
        abs_path = os.path.abspath(script_path)
        return any(abs_path.startswith(d) for d in self._allowed_script_dirs)

    async def _execute(self, tokens: list[str], timeout: int) -> dict:
        proc = await asyncio.create_subprocess_exec(
            *tokens,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._workspace.root,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        out_text = stdout.decode("utf-8", errors="replace")
        err_text = stderr.decode("utf-8", errors="replace")

        combined = out_text
        if err_text:
            if combined:
                combined += "\n"
            combined += err_text

        exit_code = proc.returncode or 0
        return {"exit_code": exit_code, "output": combined}
