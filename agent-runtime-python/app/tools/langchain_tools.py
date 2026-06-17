import logging
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.tools.file_tools import FileTools
from app.tools.terminal_tools import TerminalTools

logger = logging.getLogger("app.tools.langchain_tools")


class WriteFileInput(BaseModel):
    relative_path: str = Field(description="文件相对路径，例如 src/App.vue")
    content: str = Field(description="要写入的文件内容")


class ReadFileInput(BaseModel):
    relative_path: str = Field(description="文件相对路径")
    scope: str = Field(
        default="workspace",
        description="读取范围: workspace=项目工作区(默认), skill=当前skill资源目录",
    )


class ReadDirInput(BaseModel):
    relative_path: str = Field(default=".", description="目录相对路径，默认为项目根目录")


class RunCommandInput(BaseModel):
    command: str = Field(description="要在项目工作区执行的终端命令。仅在skill工作流明确要求时使用（如安装依赖、构建项目）。")
    timeout: int = Field(default=30, description="超时秒数，最大120")


class WriteFileTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "write_file"
    description: str = "将内容写入指定文件。如果文件不存在则创建，如果目录不存在则自动创建。"
    args_schema: Type[BaseModel] = WriteFileInput
    file_tools: FileTools | None = None

    def _run(self, relative_path: str, content: str) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, relative_path: str, content: str) -> str:
        return await self.file_tools.write_file(relative_path, content)


class ReadFileTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "read_file"
    description: str = "读取指定文件的内容。设置 scope='skill' 可读取当前skill的参考资源文件。"
    args_schema: Type[BaseModel] = ReadFileInput
    file_tools: FileTools | None = None

    def _run(self, relative_path: str, scope: str = "workspace") -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, relative_path: str, scope: str = "workspace") -> str:
        return await self.file_tools.read_file(relative_path, scope=scope)


class ReadDirTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "read_dir"
    description: str = "列出指定目录下的文件和子目录。"
    args_schema: Type[BaseModel] = ReadDirInput
    file_tools: FileTools | None = None

    def _run(self, relative_path: str = ".") -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, relative_path: str = ".") -> str:
        return await self.file_tools.read_dir(relative_path)


class RunCommandTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "run_command"
    description: str = "在项目工作区执行预授权终端命令。仅在skill工作流明确要求时使用（如npm install安装依赖、npm run build构建项目、运行检查脚本）。"
    args_schema: Type[BaseModel] = RunCommandInput
    terminal_tools: TerminalTools | None = None

    def _run(self, command: str, timeout: int = 30) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, command: str, timeout: int = 30) -> str:
        return await self.terminal_tools.run_command(command, timeout=timeout)


def create_file_tools(file_tools: FileTools) -> list[BaseTool]:
    return [
        WriteFileTool(file_tools=file_tools),
        ReadFileTool(file_tools=file_tools),
        ReadDirTool(file_tools=file_tools),
    ]


def create_all_tools(
    file_tools: FileTools,
    terminal_tools: TerminalTools | None = None,
) -> list[BaseTool]:
    tools = create_file_tools(file_tools)
    if terminal_tools is not None:
        tools.append(RunCommandTool(terminal_tools=terminal_tools))
    return tools
