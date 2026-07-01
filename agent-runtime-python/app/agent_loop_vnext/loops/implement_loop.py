"""正常 implementor 链路策略 — 现有逻辑的封装。

用于 application 模式（应用生成）。这是从原 RuntimeOrchestrator
提取出来的，所有现有逻辑完整保留。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agent_loop_vnext.loops.base import LoopStrategy
from app.runtime.event_bus import EventBus
from app.runtime.services import RuntimeServices

if TYPE_CHECKING:
    from app.agent_loop_vnext.state import SingleImplementState
    from app.capabilities.skills.registry import SkillRegistry
    from app.rag.service import RAGService
    from app.runtime.context import ExecutionContext
    from app.tools.file_tools import FileTools


class ImplementorLoop(LoopStrategy):
    """正常应用生成链路。

    - Prompt: ImplementorPromptBuilder（项目规则 + 输出合约 + skill + RAG）
    - Tools: create_implementor_tools 全量注册
    - Services: _build_services() 完整版
    """

    def __init__(self, runtime_orchestrator: Any | None = None, *, is_test: bool = False) -> None:
        self._orchestrator = runtime_orchestrator
        self._is_test = is_test

    def build_services(self, event_bus: EventBus) -> RuntimeServices:
        """复用 RuntimeOrchestrator._build_services() 完整逻辑。"""
        if self._orchestrator is not None:
            return self._orchestrator._build_services(event_bus)
        # 兜底：独立构建（不依赖 orchestrator 实例）
        raise RuntimeError(
            "ImplementorLoop 需要通过 runtime_orchestrator 参数注入 RuntimeOrchestrator 实例"
        )

    def build_system_prompt(
        self,
        context: "ExecutionContext",
        state: "SingleImplementState",
        tools: list,
        skill_registry: "SkillRegistry | None" = None,
        rag_service: "RAGService | None" = None,
    ) -> str:
        """使用 ImplementorPromptBuilder 构建正常链路 prompt。"""
        from app.agent_loop_vnext.agents.implementor.prompt import ImplementorPromptBuilder

        builder = ImplementorPromptBuilder(
            context, state,
            skill_registry=skill_registry,
            rag_service=rag_service,
        )
        return builder.build_system_prompt()

    def create_tools(
        self,
        file_tools: "FileTools",
        skill_registry: "SkillRegistry | None" = None,
        state: "SingleImplementState | None" = None,
        rag_service: "RAGService | None" = None,
    ) -> list:
        """全量注册 implementor 工具。"""
        from app.agent_loop_vnext.agents.implementor.tools import create_implementor_tools

        return create_implementor_tools(
            file_tools,
            skill_registry=skill_registry,
            state=state,
            rag_service=rag_service,
        )