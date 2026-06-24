"""application 生成模式的 Plan 和 Validate Prompt 模块。

这些模块由 GenerationModeDefinition 引用，在运行时按 generationMode 动态追加到
共享基础 Profile 中。不得在其他模式加载。
"""

from typing import Any

from app.prompts.modules import PromptModule


class ApplicationPlanModule(PromptModule):
    """application 模式的 Plan 阶段补充指令。

    追加到共享 plan 基础 Profile 之后，提供应用类项目的规划约束。
    """

    id = "application_plan"
    category = "strategic"

    def render(self, context: Any, state: Any) -> str:
        return (
            "## Application 模式规划约束\n"
            "\n"
            "当前生成模式为 application（应用类项目），规划时必须遵守：\n"
            "\n"
            "- 产物格式为 web_single_file、web_multi_file 或 vue_project；\n"
            "- 实施计划中每个任务的 allowed_files 必须列出具体文件路径，"
            "不得使用通配符或模糊描述；\n"
            "- 验收标准必须包含可运行的检查项；\n"
            "- 禁止在计划中包含未注册的产物格式。"
        )


class ApplicationValidateModule(PromptModule):
    """application 模式的 Validate 阶段补充指令。

    追加到共享 validate 基础 Profile 之后，提供应用类项目的校验约束。
    """

    id = "application_validate"
    category = "strategic"

    def render(self, context: Any, state: Any) -> str:
        return (
            "## Application 模式校验约束\n"
            "\n"
            "当前生成模式为 application（应用类项目），校验时必须检查：\n"
            "\n"
            "- 入口文件存在且非空；\n"
            "- 产物格式与实施计划一致；\n"
            "- Vue 项目必须包含 package.json 和 vite.config.js；\n"
            "- 多文件项目必须包含 index.html、style.css、script.js；\n"
            "- 单文件项目必须包含 index.html。"
        )
