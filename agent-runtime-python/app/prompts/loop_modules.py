"""Agent Loop 大循环提示词模块：plan/implement/validate 工作流、校验反馈、工具列表、计划规范、用户需求、Skill 上下文。"""

from typing import Any

from app.prompts.modules import PromptModule


class PlanWorkflowModule(PromptModule):
    """plan 模式工作流指令，从 PLAN_MODE_SYSTEM_PROMPT 拆解。"""

    id = "plan_workflow"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "mode", "") == "plan"

    def render(self, context: Any, state: Any) -> str:
        return (
            "你处于规划模式（Plan Mode）。你的职责是理解用户需求，制定完整实现计划，然后尽快切换到实现模式开始生成代码。\n"
            "\n"
            "**重要：你应该在 2-3 个步骤内完成规划并切换，不要在 plan 模式反复徘徊。**\n"
            "\n"
            "## 工作流\n"
            "\n"
            "**步骤 1：判断是否有 Skill（1 步）**\n"
            "\n"
            "- 如果有选中的 Skill：用 `read_file(scope=\"skill\", path=\"SKILL.md\")` 读取 Skill 正文，了解生成策略和约束；如需参考布局/清单，最多再读 1 个参考文件。然后进入步骤 2。\n"
            "- 如果没有选中的 Skill：**直接进入步骤 2**，不要反复查看空工作区。\n"
            "\n"
            "**步骤 2：编写实现计划（1 步）**\n"
            "\n"
            "按照计划编写规范，调用 `write_plan(outline=\"...\")` 写入实现计划。计划必须包含文件清单、生成顺序、技术选型和关键逻辑。\n"
            "\n"
            "**步骤 3：切换到 Implement 模式**\n"
            "\n"
            "计划写入后立即调用 `switch_mode(\"implement\")`。必须先调用 `write_plan` 写入计划，才能切换到 implement 模式。\n"
            "\n"
            "## 切换到 Implement 模式的条件\n"
            "\n"
            "满足以下条件即可切换（只需 1-3 个步骤）：\n"
            "\n"
            "1. 用户需求已理解（不需要完美理解，合理推测即可）\n"
            "2. 如有 Skill，已读取 Skill 正文\n"
            "3. 已通过 `write_plan` 写入实现计划\n"
            "\n"
            "**不要在计划阶段追求完美。** 对于明确的简单需求（如'创建一个登录页面'），可以直接在 1 步内完成规划并切换，在实施时再逐步完善。\n"
            "\n"
            "## 注意事项\n"
            "\n"
            "- 你没有写文件权限，不要尝试调用 write_file\n"
            "- 工作区为空时不要反复调用 read_dir，直接开始规划\n"
            "- 如果连续 3 步没有进展，立即调用 `write_plan` 写入当前理解，然后 `switch_mode(\"implement\")` 强行切换\n"
            "- 用户对应用本身的细节（如配色、布局、功能），你先按最佳实践自主决定，不要问用户\n"
            "- **不要在回复中复述 Skill 原文内容**，只提取关键规则和约束用于指导实现，对用户可见的回复必须是简洁的中文摘要"
        )


class ImplementWorkflowModule(PromptModule):
    """implement 模式工作流指令，从 IMPLEMENT_MODE_SYSTEM_PROMPT 拆解。"""

    id = "implement_workflow"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "mode", "") == "implement"

    def render(self, context: Any, state: Any) -> str:
        outline_text = "暂无实现规划"
        outline = getattr(state, "implementation_outline", None)
        if outline:
            if isinstance(outline, dict):
                outline_text = outline.get("text", str(outline))
            else:
                outline_text = str(outline)

        return (
            "你处于实现模式（Implement Mode）。你的职责是按照规划步骤生成完整的项目代码，生成完毕后调用 finish。\n"
            "\n"
            "**重要：进入 implement 模式后，专注于代码生成，不要再反复分析或重复读取已有文件。**\n"
            "\n"
            f"## 实现计划\n\n{outline_text}\n\n"
            "## 工作流\n"
            "\n"
            "1. 按实现计划中的顺序，逐个创建文件。用 write_file 写入完整的、可直接运行的内容。\n"
            "2. 文件路径使用正斜杠 /。每个文件一次性写完完整内容，不省略、不使用占位符。\n"
            "3. 如果是 Vue 项目，写入所有文件后执行 npm install 安装依赖。\n"
            "4. 重点：全部文件创建完成后立即调用 finish，不要画蛇添足。\n"
            "5. 如果实现计划为空或不完整，按用户需求的合理理解自主生成，不需要回 plan 模式。\n"
            "\n"
            "## 返回 Plan 模式的条件（极少使用）\n"
            "\n"
            "仅在以下情况切换回 plan：\n"
            "- 用户项目非常大（10+ 个核心文件），你需要重新规划分工\n"
            "- 规划中明确提到的关键资源（如特定 Skill 参考文件）不可用\n"
            "- 用户在这一轮明确表达了新需求\n"
            "\n"
            "## 注意事项\n"
            "\n"
            "- 你有完整的文件读写和终端执行权限\n"
            "- 每个文件写入完整可运行的代码，不要在文件之间拆分不完整的片段\n"
            "- 不要伪造工具执行结果\n"
            "- 生成过程直奔主题，3-5 个 write_file 内完成\n"
            "- **任务完成后必须调用 finish**\n"
            "- **不要在回复中复述 Skill 原文内容**，只引用关键规则和约束，对用户可见的回复必须是简洁的中文摘要"
        )


class ValidateWorkflowModule(PromptModule):
    """validate 模式工作流指令。"""

    id = "validate_workflow"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "mode", "") == "validate"

    def render(self, context: Any, state: Any) -> str:
        check_results_text = ""
        check_results = getattr(state, "validation_check_results", None)
        if check_results:
            lines = []
            for r in check_results:
                icon = "✓" if r.get("status") == "pass" else ("✗" if r.get("status") == "fail" else "⚠")
                lines.append(f"{icon} [{r.get('severity', '?')}] {r.get('id', '?')}: {r.get('message', '')}")
            check_results_text = "\n".join(lines)

        parts = [
            "你处于校验模式（Validate Mode）。你的职责是检查已生成的代码是否符合项目结构要求。\n",
            "\n",
            "## 工作流\n",
            "\n",
            "1. 首先调用 `run_checks` 执行项目结构校验，获取检查结果。\n",
            "2. 根据检查结果，如有必要可调用 `read_file` 或 `read_dir` 进一步了解文件内容。\n",
            "3. 综合判断后调用 `decide_validation` 输出校验结论。\n",
            "\n",
            "## 校验判断规则\n",
            "\n",
            "- 如果存在 error 级别的失败（如入口文件缺失）：调用 `decide_validation(verdict=\"fail\", issues=[...], suggestions=[...])`\n",
            "- 如果仅有 warning 级别的提醒（如占位符文本）：可接受，调用 `decide_validation(verdict=\"pass\")`\n",
            "- 如果全部通过：调用 `decide_validation(verdict=\"pass\")`\n",
            "\n",
            "**注意：3 步内必须输出校验结论。**",
        ]

        if check_results_text:
            parts.append(f"\n\n## 已缓存的检查结果\n\n{check_results_text}\n\n（已执行过 run_checks，无需重复执行）")

        return "".join(parts)


class ValidateFeedbackModule(PromptModule):
    """校验失败反馈模块，在 implement 模式下展示校验问题。"""

    id = "validate_feedback"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return (
            getattr(state, "mode", "") == "implement"
            and bool(getattr(state, "validation_failures", None))
        )

    def render(self, context: Any, state: Any) -> str:
        failures = getattr(state, "validation_failures", [])
        if not failures:
            return ""

        lines = ["## 校验反馈\n", "\n上次生成的代码存在以下问题，请修复后重新生成：\n"]
        for i, f in enumerate(failures, 1):
            lines.append(f"{i}. {f.get('issue', str(f))}")
            suggestion = f.get("suggestion", "")
            if suggestion:
                lines.append(f"   修复建议：{suggestion}")
        return "\n".join(lines)


class ToolListModule(PromptModule):
    """动态工具列表模块，在节点执行前注入工具列表。"""

    id = "tool_list"
    category = "strategic"

    def __init__(self) -> None:
        super().__init__()
        self._tools: list = []

    def set_tools(self, tools: list) -> None:
        self._tools = tools

    def enabled(self, context: Any, state: Any) -> bool:
        return len(self._tools) > 0

    def render(self, context: Any, state: Any) -> str:
        from app.agent_loop.nodes.step_base import _format_tool_list

        return "## 当前可用工具\n\n" + _format_tool_list(self._tools)


class PlanSpecModule(PromptModule):
    """计划编写规范模块。"""

    id = "plan_spec"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "mode", "") == "plan"

    def render(self, context: Any, state: Any) -> str:
        return (
            "## 计划编写规范\n"
            "\n"
            "请严格按照以下规范编写实现计划，调用 `write_plan(outline=\"...\")` 写入。\n"
            "\n"
            "### 1. 文件清单\n"
            "\n"
            "列出所有需要创建的文件，每个文件包含：\n"
            "- **文件路径**（如 `src/App.vue`、`index.html`）\n"
            "- **文件职责**（一句话说明这个文件做什么）\n"
            "- **关键依赖**（依赖哪些其他文件或第三方库）\n"
            "\n"
            "### 2. 生成顺序\n"
            "\n"
            "按依赖关系排列文件生成顺序，被依赖的文件先创建。\n"
            "\n"
            "### 3. 技术选型\n"
            "\n"
            "- 框架选择（如 Vue / React / 纯 HTML）\n"
            "- 样式方案（如 Tailwind / CSS Modules / 内联样式）\n"
            "- 关键第三方库\n"
            "\n"
            "### 4. 关键逻辑\n"
            "\n"
            "- 核心交互逻辑\n"
            "- 数据流向\n"
            "- 特殊处理（如响应式适配、动画等）"
        )


class UserPromptModule(PromptModule):
    """用户需求段落模块。"""

    id = "user_prompt"
    category = "mandatory"

    def render(self, context: Any, state: Any) -> str:
        prompt = getattr(context, "prompt", "")
        return f"## 用户需求\n\n{prompt}"


class SkillContextModule(PromptModule):
    """Skill 上下文模块，替换 PlanStepNode/ImplementStepNode 中的内联 Skill 信息构建。"""

    id = "skill_context"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        caps = getattr(state, "selected_capabilities", None)
        return caps is not None and getattr(caps, "skill", None) is not None

    def render(self, context: Any, state: Any) -> str:
        caps = getattr(state, "selected_capabilities", None)
        if caps is None:
            return ""
        skill = getattr(caps, "skill", None)
        if skill is None:
            # 显示可用 Skill 列表
            index = getattr(state, "_asset_index", None)
            if index is not None:
                skills = index.skill_registry.all()
                if skills:
                    lines = ["## 可用 Skill 列表\n", "\n你可以使用 `select_skill(skill_id, reason)` 选择一个适合当前任务的 Skill。\n"]
                    for s in skills:
                        lines.append(f"- **{s.id}**: {s.description}")
                    return "\n".join(lines)
            return ""

        skill_dir = str(skill.source_path.parent)
        return (
            f"## 已选择的 Skill\n\n"
            f"**{skill.name}** (ID: {skill.id}): {skill.description}\n\n"
            f"Skill 目录：`{skill_dir}`\n\n"
            f"你可以用 `read_asset(relative_path='skills/{skill.id}/SKILL.md')` 读取详细规则，"
            f"或用 `run_command` 执行 `{skill_dir}/scripts/search.py` 等脚本。"
        )
