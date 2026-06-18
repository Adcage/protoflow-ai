"""路由提示词模块：route_initial（首次路由）、route_after_implement（implement 后路由）、route_after_validate（validate 后路由）。"""

from typing import Any

from app.prompts.modules import PromptModule


class RouteInitialModule(PromptModule):
    """首次路由模块，判断进入 plan / implement 模式。
    当 code_gen_type 未确定时，AI 调用 ask_user 让用户选择应用类型。"""

    id = "route_initial"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return not getattr(state, "route_decided", False)

    def render(self, context: Any, state: Any) -> str:
        code_gen_type = getattr(context, "code_gen_type", None)
        type_value = code_gen_type.value if code_gen_type else None
        recommended = getattr(state, "recommended_code_gen_type", None)

        type_status = ""
        if recommended:
            type_status = f"应用类型已确定：{recommended}"
        elif type_value:
            type_status = f"应用类型已确定：{type_value}"
        else:
            type_status = "应用类型未确定，需要先让用户选择"

        return (
            "## 路由判断\n"
            "\n"
            "你是一个路由判断助手。你需要根据当前工作区状态和用户需求，判断应该进入哪种模式。\n"
            "\n"
            f"**当前状态**：{type_status}\n"
            "\n"
            "### 判断规则\n"
            "\n"
            "1. **应用类型未确定**：先分析用户需求适合哪种应用类型，然后调用 `ask_user` 让用户确认：\n"
            "   - 单文件应用（single_file）：适合简单展示页、落地页\n"
            "   - 多文件应用（multi-file）：适合有样式/逻辑分离需求的项目\n"
            "   - Vue 工程（vue_project）：适合多页面、路由、状态管理的项目\n"
            "   用户确认后，调用 `decide_route(mode=\"plan\", code_gen_type=\"用户选择\")`\n"
            "\n"
            "2. **工作区为空且应用类型已确定**：调用 `decide_route(mode=\"plan\")`，进入规划模式\n"
            "\n"
            "3. **工作区有内容且用户需求是简单修改**（如改颜色、调整布局、修文字）：调用 `decide_route(mode=\"implement\")`，直接修改\n"
            "\n"
            "4. **工作区有内容且用户需求是复杂变更**（如重新设计、新增模块、大范围重构）：调用 `decide_route(mode=\"plan\")`，需要规划\n"
            "\n"
            "**3 步内必须做出决策。** 判断后必须调用 `decide_route`。"
        )


class RouteAfterImplementModule(PromptModule):
    """implement 完成后的路由模块，判断是否需要校验。"""

    id = "route_after_implement"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "implement_just_finished", False)

    def render(self, context: Any, state: Any) -> str:
        files_touched = getattr(state, "files_touched", [])
        run_mode = getattr(context, "run_mode", "generate")
        files_count = len(files_touched)

        # 当前使用代码规则判断，后续替换为轻量模型
        should_validate = (run_mode == "generate" and files_count > 3) or files_count >= 3
        recommendation = "validate" if should_validate else "finish"

        return (
            "## 路由判断\n"
            "\n"
            "AI 刚完成代码生成，你需要判断是否需要校验。\n"
            "\n"
            f"**上下文**：\n"
            f"- 本次改动的文件数：{files_count}\n"
            f"- 改动模式：{run_mode}\n"
            f"- 建议路由：{recommendation}\n"
            "\n"
            "### 判断规则\n"
            "\n"
            "- 如果是首次生成或改动量较大（3 个以上文件）：调用 `decide_route(mode=\"validate\")`\n"
            "- 如果是简单修改（1-2 个文件的小改动）：调用 `decide_route(mode=\"finish\")`\n"
            "\n"
            "**1 步内必须做出决策。**"
        )


class RouteAfterValidateModule(PromptModule):
    """validate 完成后的路由模块，判断是否需要修复。"""

    id = "route_after_validate"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "validate_just_finished", False)

    def render(self, context: Any, state: Any) -> str:
        validation_status = getattr(state, "validation_status", "pending")
        failures = getattr(state, "validation_failures", [])
        check_results = getattr(state, "validation_check_results", [])

        # 构建校验结果摘要
        results_text = ""
        if check_results:
            lines = []
            for r in check_results:
                icon = "✓" if r.get("status") == "pass" else ("✗" if r.get("status") == "fail" else "⚠")
                lines.append(f"{icon} [{r.get('severity', '?')}] {r.get('id', '?')}: {r.get('message', '')}")
            results_text = "\n".join(lines)

        failures_text = ""
        if failures:
            failure_lines = []
            for f in failures:
                failure_lines.append(f"- {f.get('issue', str(f))}")
            failures_text = "\n".join(failure_lines)

        recommendation = "implement" if validation_status == "failed" else "finish"

        parts = [
            "## 路由判断\n",
            "\n校验刚刚完成，你需要根据校验结果判断下一步。\n",
            f"\n**校验状态**：{validation_status}\n",
            f"**建议路由**：{recommendation}\n",
        ]

        if results_text:
            parts.append(f"\n### 校验结果\n\n{results_text}\n")

        if failures_text:
            parts.append(f"\n### 失败项\n\n{failures_text}\n")

        parts.append(
            "\n### 判断规则\n"
            "\n"
            "- 校验通过（无 error 级别失败）：调用 `decide_route(mode=\"finish\")`\n"
            "- 校验有 error 级别失败：调用 `decide_route(mode=\"implement\")`，AI 将修复问题后重新校验\n"
            "\n"
            "**1 步内必须做出决策。**"
        )

        return "".join(parts)
