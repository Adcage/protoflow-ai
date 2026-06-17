import pytest
import tempfile
import os

from app.tools.file_tools import Workspace
from app.tools.terminal_tools import TerminalTools
from app.core.exceptions import AgentRuntimeError
from app.core.error_codes import AgentErrorCode


@pytest.fixture
def workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Workspace(tmpdir)


@pytest.fixture
def terminal_tools(workspace):
    return TerminalTools(
        workspace=workspace,
        allowed_commands=["python", "node", "npm", "npx", "pip", "git", "ls", "cat", "find", "head", "tail", "wc", "type", "cmd"],
        readonly_commands=["python", "ls", "cat", "git", "head", "tail", "find", "wc", "type", "cmd"],
        default_timeout=5,
        max_timeout=10,
        max_output_bytes=10240,
    )


class TestTerminalTools:
    @pytest.mark.asyncio
    async def test_command_allowed(self, terminal_tools):
        result = await terminal_tools.run_command('python -c "print(\'hello\')"')
        assert "hello" in result
        assert "exit_code=0" in result

    @pytest.mark.asyncio
    async def test_command_not_allowed(self, terminal_tools):
        with pytest.raises(AgentRuntimeError) as exc_info:
            await terminal_tools.run_command("unknown_cmd arg")
        assert exc_info.value.code == AgentErrorCode.COMMAND_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_shell_injection_blocked_double_ampersand(self, terminal_tools):
        with pytest.raises(AgentRuntimeError) as exc_info:
            await terminal_tools.run_command('python -c "print(\'a\')" && python -c "print(\'b\')"')
        assert exc_info.value.code == AgentErrorCode.COMMAND_INJECTION_BLOCKED

    @pytest.mark.asyncio
    async def test_shell_injection_blocked_semicolon(self, terminal_tools):
        with pytest.raises(AgentRuntimeError) as exc_info:
            await terminal_tools.run_command('python -c "print(\'a\')" ; python -c "print(\'b\')"')
        assert exc_info.value.code == AgentErrorCode.COMMAND_INJECTION_BLOCKED

    @pytest.mark.asyncio
    async def test_shell_injection_blocked_pipe(self, terminal_tools):
        with pytest.raises(AgentRuntimeError) as exc_info:
            await terminal_tools.run_command('python -c "print(\'a\')" | python -c "print(\'b\')"')
        assert exc_info.value.code == AgentErrorCode.COMMAND_INJECTION_BLOCKED

    @pytest.mark.asyncio
    async def test_command_timeout(self, terminal_tools):
        with pytest.raises(AgentRuntimeError) as exc_info:
            await terminal_tools.run_command('python -c "import time; time.sleep(30)"', timeout=1)
        assert exc_info.value.code == AgentErrorCode.COMMAND_TIMEOUT

    @pytest.mark.asyncio
    async def test_workspace_locked(self, workspace, terminal_tools):
        test_file = "workspace_test.txt"
        file_path = os.path.join(workspace.root, test_file)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("workspace content")
        result = await terminal_tools.run_command(f'python -c "print(open(\'{test_file}\', \'r\').read())"')
        assert "workspace content" in result

    @pytest.mark.asyncio
    async def test_readonly_mode_allowed(self, terminal_tools):
        result = await terminal_tools.run_command('python -c "print(\'ok\')"', readonly=True)
        assert "ok" in result
        assert "exit_code=0" in result

    @pytest.mark.asyncio
    async def test_readonly_mode_blocked_write_command(self, terminal_tools):
        terminal_tools_no_python = TerminalTools(
            workspace=terminal_tools._workspace,
            allowed_commands=["python", "node"],
            readonly_commands=["node"],
        )
        with pytest.raises(AgentRuntimeError) as exc_info:
            await terminal_tools_no_python.run_command('python -c "print(\'hello\')"', readonly=True)
        assert exc_info.value.code == AgentErrorCode.COMMAND_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_command_exit_code_nonzero(self, terminal_tools):
        result = await terminal_tools.run_command('python -c "import sys; sys.exit(1)"')
        assert "exit_code=1" in result

    @pytest.mark.asyncio
    async def test_command_empty_raises(self, terminal_tools):
        with pytest.raises(AgentRuntimeError):
            await terminal_tools.run_command("")
