"""Playground 链路策略 — AI 工具能力测试专用。

与 ImplementorLoop 完全隔离：
- Prompt: 自定义 Playground 系统提示词（不提 Conductor/项目规则/输出合约）
- Tools: create_implementor_tools 全量 + 按 enabled_tools 过滤
- Services: 精简 PromptModuleRegistry（只保留必要模块）
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger("app.agent_loop_vnext.loops.playground_loop")


class PlaygroundLoop(LoopStrategy):
    """AI 工具能力测试 Playground 链路。

    设计要点：
    - 系统提示词明确告知 AI：当前是 Playground 模式，可自由使用工具
    - 工具按 context.runtime_options.enabled_tools 过滤
    - Prompt 模块精简：去掉 production_security / project_rules / workflow /
      output_contract / anti_roleplay / task_context 等生产约束
    - is_test=True：跳过敏感信息脱敏，方便调试
    """

    def __init__(self, runtime_orchestrator: Any | None = None, *, is_test: bool = True) -> None:
        self._orchestrator = runtime_orchestrator
        self._is_test = is_test

    def build_services(self, event_bus: EventBus) -> RuntimeServices:
        """构建 Playground 精简版 RuntimeServices。"""
        from app.prompts.default_modules import (
            RuntimeBoundaryModule,
            SafetyAndInjectionResistanceModule,
        )
        from app.prompts.loop_modules import (
            SkillContextModule,
            ToolListModule,
        )
        from app.prompts.playground_modules import PlaygroundModeModule
        from app.prompts.registry import PromptModuleRegistry
        from app.prompts.test_modules import TestModeInfoModule

        registry = PromptModuleRegistry()
        # Playground 启用的模块：精简到只保留必要的
        registry.register(RuntimeBoundaryModule())                # 运行时边界（必须）
        registry.register(SafetyAndInjectionResistanceModule())   # 基本注入防护（必须）
        registry.register(ToolListModule())                       # 工具列表（动态注入）
        registry.register(SkillContextModule())                    # Skill 上下文
        registry.register(TestModeInfoModule())                    # 测试模式（允许讨论内部机制）
        registry.register(PlaygroundModeModule())                  # Playground 模式说明

        # 复用 orchestrator 共享资源
        if self._orchestrator is None:
            raise RuntimeError("PlaygroundLoop 需要 runtime_orchestrator 参数")

        # 注册 application 生成模式（保持兼容）
        from app.generation_modes.application import register_application
        from app.generation_modes.registry import GenerationModeRegistry
        gen_mode_registry = GenerationModeRegistry()
        register_application(gen_mode_registry)

        # 访问 _global_rag_service
        from app.runtime.orchestrator import _get_rag_service

        return RuntimeServices(
            platform_client=self._orchestrator._platform_client,
            tool_client=None,
            chat_model_factory=self._orchestrator._chat_model_factory,
            model_policy=self._orchestrator._model_policy,
            model_resolver=self._orchestrator._model_resolver,
            prompt_composer=None,
            prompt_module_registry=registry,
            tool_registry=None,
            event_bus=event_bus,
            node_registry=None,
            asset_manager=self._orchestrator._asset_manager,
            quality_checker=self._orchestrator._quality_checker,
            artifact_writer=self._orchestrator._artifact_writer,
            generation_mode_registry=gen_mode_registry,
            rag_service=_get_rag_service(),
        )

    def build_system_prompt(
        self,
        context: "ExecutionContext",
        state: "SingleImplementState",
        tools: list,
        skill_registry: "SkillRegistry | None" = None,
        rag_service: "RAGService | None" = None,
    ) -> str:
        """构建 Playground 专用系统提示词。

        完全独立的 prompt，不复用 ImplementorPromptBuilder，避免角色冲突。
        """
        # 已加载的工具列表
        tool_names = [t.name for t in tools]
        enabled_tools_str = ", ".join(tool_names) if tool_names else "（未启用任何工具）"

        # 可用技能摘要（如果有）
        skills_section = ""
        if skill_registry is not None:
            all_skills = skill_registry.all()
            if all_skills:
                lines = [
                    "## 可用技能",
                    "可使用 LoadSkill 工具加载一个或多个技能。加载后可使用 skill/{技能ID}/ 路径读取参考文件。",
                    "",
                ]
                for skill in all_skills:
                    lines.append(f"- **{skill.id}**: {skill.description}")
                skills_section = "\n\n".join(lines)

        # 已加载的技能
        loaded_skills_section = ""
        if state.loaded_skills:
            lines = ["## 已加载技能参考文件"]
            for skill_id, loaded in state.loaded_skills.items():
                if loaded.references:
                    lines.append(f"**{skill_id}** 的参考文件：")
                    for ref in loaded.references:
                        lines.append(f"- skill/{skill_id}/{ref}")
                else:
                    lines.append(f"**{skill_id}**: 无参考文件")
            loaded_skills_section = "\n".join(lines)

        # RAG 文档说明
        rag_section = ""
        if rag_service is not None and rag_service.enabled:
            rag_section = rag_service.get_available_docs_description()

        prompt_parts = [
            (
                "你是 AI 工具能力测试助手。\n"
                "\n"
                "## 当前模式\n"
                "Playground 模式（工具能力测试模式）。\n"
                "- 你可以自由使用已启用的工具来回答问题和执行操作\n"
                "- 不受项目规则、应用模板、输出合约约束\n"
                "- 直接与用户对话，不需要遵循特定的代码生成流程\n"
                "- 用户可能测试各种工具组合，请配合演示工具能力\n"
                "- 工作区路径下可以自由创建文件用于测试\n"
            ),
            (
                "## 工作方式\n"
                "- 和用户正常对话交流，理解需求\n"
                "- 需要实现代码时，使用工具创建或修改文件\n"
                "- 需要了解项目现有结构时，使用 Read 工具查看\n"
                "- 需要搜索文件时，使用 Glob 按文件名搜索或 Grep 按内容搜索\n"
                "- 需要执行命令时（如安装依赖、构建项目），使用 Bash 工具\n"
                "- 需要向用户提问以明确需求时，使用 AskUser 工具\n"
                "- Bash 工具每次只能执行一条命令，不支持 &&、||、|、; 等操作符。多条命令请分多次调用\n"
                "- 不需要工具时直接回复，不要主动调用工具\n"
            ),
            f"## 当前已启用工具\n{enabled_tools_str}",
        ]
        if skills_section:
            prompt_parts.append(skills_section)
        if loaded_skills_section:
            prompt_parts.append(loaded_skills_section)
        if rag_section:
            prompt_parts.append(rag_section)

        return "\n\n".join(p for p in prompt_parts if p)

    def create_tools(
        self,
        file_tools: "FileTools",
        skill_registry: "SkillRegistry | None" = None,
        state: "SingleImplementState | None" = None,
        rag_service: "RAGService | None" = None,
    ) -> list:
        """创建工具列表。

        Playground 的工具过滤在 orchestrator 层根据 enabled_tools 完成，
        这里只负责"返回所有可用工具"。过滤逻辑放在 _run_playground 中。
        """
        from app.agent_loop_vnext.agents.implementor.tools import create_implementor_tools

        tools = create_implementor_tools(
            file_tools,
            skill_registry=skill_registry,
            state=state,
            rag_service=rag_service,
        )
        # 将 event_bus 注入需要它的工具
        if state is not None and hasattr(state, "_event_bus"):
            for tool in tools:
                if hasattr(tool, "event_bus") and tool.event_bus is None:
                    tool.event_bus = state._event_bus
        return tools