"""链路构建策略抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from app.runtime.event_bus import EventBus
from app.runtime.services import RuntimeServices

if TYPE_CHECKING:
    from app.agent_loop_vnext.state import SingleImplementState
    from app.capabilities.skills.registry import SkillRegistry
    from app.rag.service import RAGService
    from app.runtime.context import ExecutionContext
    from app.tools.file_tools import FileTools


class LoopStrategy(ABC):
    """链路构建策略 — 定义一条 agent loop 链路的完整构建方式。

    每种 generation_mode（如 application、test_playground）对应一个
    LoopStrategy 子类。orchestrator 根据 generation_mode 选择对应策略，
    然后通过策略构建链路所需的全部组件。

    设计原则：
    - 策略只负责"如何构建链路组件"，不负责"如何运行循环"
    - 循环运行逻辑由 SingleImplementLoopRunner 统一处理
    - 新增模式只需新增一个 LoopStrategy 子类，不改 Runner
    """

    @abstractmethod
    def build_services(self, event_bus: EventBus) -> RuntimeServices:
        """构建 RuntimeServices（含 PromptModuleRegistry 等）。

        不同模式注册不同的 Prompt 模块。
        """

    @abstractmethod
    def build_system_prompt(
        self,
        context: "ExecutionContext",
        state: "SingleImplementState",
        tools: list,
        skill_registry: "SkillRegistry | None" = None,
        rag_service: "RAGService | None" = None,
    ) -> str:
        """构建系统提示词。"""

    @abstractmethod
    def create_tools(
        self,
        file_tools: "FileTools",
        skill_registry: "SkillRegistry | None" = None,
        state: "SingleImplementState | None" = None,
        rag_service: "RAGService | None" = None,
    ) -> list:
        """创建该链路使用的工具列表。"""


def get_loop_strategy(
    generation_mode: str | int | None,
    *,
    runtime_orchestrator: Any | None = None,
    is_test: bool = False,
) -> LoopStrategy:
    """根据 generation_mode 选择链路构建策略。

    Args:
        generation_mode: protobuf 枚举值或字符串
            - 2 / "test_playground" → PlaygroundLoop
            - 其他 → ImplementorLoop（默认）
        runtime_orchestrator: RuntimeOrchestrator 实例（用于访问 platform_client 等共享依赖）
        is_test: 是否测试模式
    """
    # 延迟导入避免循环引用
    from app.agent_loop_vnext.loops.implement_loop import ImplementorLoop
    from app.agent_loop_vnext.loops.playground_loop import PlaygroundLoop

    # protobuf 枚举值 → 字符串
    if isinstance(generation_mode, int):
        mode_map = {0: None, 1: "application", 2: "test_playground"}
        generation_mode = mode_map.get(generation_mode)

    if generation_mode == "test_playground":
        return PlaygroundLoop(runtime_orchestrator, is_test=is_test)
    return ImplementorLoop(runtime_orchestrator, is_test=is_test)