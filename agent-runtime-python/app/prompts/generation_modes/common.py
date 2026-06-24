"""通用生成模式澄清模块，用于 generationMode 为 unresolved 时的 Plan 阶段。"""

from typing import Any

from app.prompts.modules import PromptModule


class GenerationModeClarificationModule(PromptModule):
    """当 generationMode 为 unresolved 时，Plan 只能澄清模式并提交确认。"""

    id = "generation_mode_clarification"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        generation_mode = getattr(state, "generation_mode", None)
        if generation_mode is None:
            envelope = getattr(state, "_state_envelope", None)
            if envelope is not None:
                generation_mode = getattr(envelope.workflow, "generation_mode", None)
        return generation_mode == "unresolved"

    def render(self, context: Any, state: Any) -> str:
        return (
            "## 生成模式待确认\n"
            "\n"
            "当前请求的生成模式尚未确定。你的唯一职责是：\n"
            "\n"
            "1. 询问用户需要生成什么类型的产品（当前可用：application/应用类项目）；\n"
            "2. 用户确认后，使用模式确认工具写入已确认的 generationMode；\n"
            "3. 确认前禁止编写正式实施计划或写业务文件。\n"
            "\n"
            "**注意：当前只支持 application 模式。如果用户需求不属于应用类项目，"
            "请如实告知并等待进一步指示。**"
        )
