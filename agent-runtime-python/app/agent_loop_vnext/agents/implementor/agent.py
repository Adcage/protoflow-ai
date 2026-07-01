"""Implementor Agent —— 代码实现助手，vNext 首个 Agent。"""

from app.agent_loop_vnext.base.agent import Agent
from app.agent_loop_vnext.agents.implementor.prompt import ImplementorPromptBuilder
from app.agent_loop_vnext.agents.implementor.tools import create_implementor_tools
from app.agent_loop_vnext.shared.tools.base import AgentTool
from app.runtime.context import ExecutionContext
from app.runtime.services import RuntimeServices


class ImplementorAgent(Agent):
    """代码实现 Agent —— 理解用户需求并生成代码实现。"""

    name = "implementor"
    description = "理解用户需求并生成代码实现"

    def create_tools(
        self,
        file_tools,
        services: RuntimeServices,
    ) -> list[AgentTool]:
        skill_registry = None
        if services.asset_manager is not None:
            skill_registry = services.asset_manager.get_index().skill_registry
        return create_implementor_tools(
            file_tools,
            skill_registry=skill_registry,
            state=self._state,
            rag_service=services.rag_service,
        )

    def build_system_prompt(
        self,
        context: ExecutionContext,
        services: RuntimeServices,
    ) -> str:
        skill_registry = None
        if services.asset_manager is not None:
            skill_registry = services.asset_manager.get_index().skill_registry
        builder = ImplementorPromptBuilder(
            context, self._state,
            skill_registry=skill_registry,
            rag_service=services.rag_service,
        )
        return builder.build_system_prompt()
