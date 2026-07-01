"""Implementor Agent 的工具集绑定。

每个 Agent 的 tools.py 从 shared/tools/ 中挑选工具并注入 FileTools 依赖。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent_loop_vnext.shared.tools.base import AgentTool
from app.agent_loop_vnext.base.state import AgentRunState
from app.agent_loop_vnext.shared.tools.ask_user_tool import AskUserTool
from app.agent_loop_vnext.shared.tools.bash_tool import BashTool
from app.agent_loop_vnext.shared.tools.file_tools import (
    EditTool,
    GlobTool,
    GrepTool,
    InsertTool,
    ReadTool,
    WriteTool,
)
from app.agent_loop_vnext.shared.tools.rag_search_tool import SearchDocsTool
from app.agent_loop_vnext.shared.tools.skill_tools import LoadSkillTool
from app.agent_loop_vnext.state import SingleImplementState
from app.capabilities.skills.registry import SkillRegistry
from app.tools.file_tools import FileTools

if TYPE_CHECKING:
    from app.rag.service import RAGService


def create_implementor_tools(
    file_tools: FileTools,
    skill_registry: SkillRegistry | None = None,
    state: SingleImplementState | AgentRunState | None = None,
    rag_service: RAGService | None = None,
) -> list[AgentTool]:
    """创建 implementor Agent 的工具集。

    Args:
        file_tools: 文件操作依赖
        skill_registry: 技能注册表
        state: Agent 状态
        rag_service: RAG 服务实例，enabled 时注册 SearchDocs 工具
    """
    tools: list[AgentTool] = [
        ReadTool(file_tools=file_tools, state=state),
        WriteTool(file_tools=file_tools),
        EditTool(file_tools=file_tools),
        InsertTool(file_tools=file_tools),
        GlobTool(file_tools=file_tools),
        GrepTool(file_tools=file_tools),
        LoadSkillTool(skill_registry=skill_registry, state=state),
        BashTool(file_tools=file_tools),
        AskUserTool(state=state),  # event_bus injected by runner after creation
    ]

    # RAG 技术文档检索（条件注册）
    if rag_service and rag_service.enabled:
        tools.append(SearchDocsTool(rag_service=rag_service))

    return tools
