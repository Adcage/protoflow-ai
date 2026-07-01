"""Playground 模式专用 Prompt 模块。"""

from app.prompts.modules import PromptModule


class PlaygroundModeModule(PromptModule):
    """Playground 模式说明模块。

    告知 AI 当前处于工具能力测试模式，允许自由使用工具、不受项目规则约束。
    """

    id = "playground_mode"
    category = "test"  # type: ignore[assignment]

    def enabled(self, context, state) -> bool:  # type: ignore[override]
        """Playground 模式始终启用（由 _build_playground_services 注册时控制）。"""
        return True

    def render(self, context, state) -> str:  # type: ignore[override]
        return (
            "## Playground 模式\n"
            "\n"
            "当前处于 AI 工具能力测试 Playground 模式。\n"
            "- 你可以自由使用已启用的工具来回答问题和执行操作\n"
            "- 不受项目规则或应用模板约束\n"
            "- 直接与用户对话，不需要遵循特定的代码生成流程\n"
            "- 用户可能测试各种工具组合，请配合演示工具能力\n"
            "- 工作区路径下可以自由创建文件用于测试\n"
        )
