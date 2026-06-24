"""路由提示词模块：route_initial、route_after_plan、route_after_implement、route_after_validate。"""

from typing import Any

from app.prompts.modules import PromptModule


def _get_effective_type(state, context) -> str:
    artifact_type = getattr(state, "artifact_type_state", None)
    if artifact_type is not None and getattr(artifact_type, "effective", None):
        return artifact_type.effective
    code_gen_type = getattr(context, "code_gen_type", None)
    if code_gen_type is not None:
        return code_gen_type.value if hasattr(code_gen_type, "value") else str(code_gen_type)
    return "unknown"


class RouteInitialModule(PromptModule):
    """首次路由模块，判断进入 plan / implement 模式。
    信息不足时进入 Plan 澄清，不直接向用户提问。"""

    id = "route_initial"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return not getattr(state, "route_decided", False)

    def render(self, context: Any, state: Any) -> str:
        type_value = _get_effective_type(state, context)
        recommended = None
        artifact_type = getattr(state, "artifact_type_state", None)
        if artifact_type is not None:
            recommended = getattr(artifact_type, "recommended", None)

        type_status = ""
        if recommended:
            type_status = f"应用类型已确定：{recommended}"
        elif type_value:
            type_status = f"应用类型已确定：{type_value}"
        else:
            type_status = "应用类型未确定"

        return (
            "## 路由判断\n"
            "\n"
            "你是一个路由判断助手。你需要根据当前工作区状态和用户需求，判断应该进入哪种模式。\n"
            "\n"
            f"**当前状态**：{type_status}\n"
            "\n"
            "### 判断规则\n"
            "\n"
            "1. **应用类型未确定或需求不够清晰**：进入规划模式，在规划阶段可以与用户交互来澄清需求\n"
            "\n"
            "2. **工作区为空且应用类型已确定**：进入规划模式\n"
            "\n"
            "3. **工作区有内容且用户需求是简单修改**（如改颜色、调整布局、修文字）：直接进入实现模式\n"
            "\n"
            "4. **工作区有内容且用户需求是复杂变更**（如重新设计、新增模块、大范围重构）：进入规划模式\n"
            "\n"
            "信息不足时优先进入规划模式进行澄清。\n"
            "\n"
            "**3 步内必须做出决策。**"
        )


class RouteAfterPlanModule(PromptModule):
    """Plan 完成后的路由模块，判断计划是否完整。"""

    id = "route_after_plan"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "plan_just_finished", False)

    def render(self, context: Any, state: Any) -> str:
        # Phase 3: Plan 产物为结构化 ImplementationPlan（v2 envelope）
        has_plan = False
        envelope = getattr(state, "_state_envelope", None)
        if envelope is not None:
            plan_state = getattr(envelope.workflow, "plan", None)
            if plan_state is not None and getattr(plan_state, "implementation_plan", None) is not None:
                has_plan = True
        plan_status = "已有完整实施计划" if has_plan else "计划不完整或为空"

        return (
            "## 路由判断\n"
            "\n"
            "规划阶段刚刚完成，你需要判断下一步。\n"
            "\n"
            f"**规划状态**：{plan_status}\n"
            "\n"
            "### 判断规则\n"
            "\n"
            "- 计划完整：进入实现模式\n"
            "- 计划不完整：说明缺少什么内容，路由到实现模式（Plan 已完成一轮澄清，不再回 Plan 循环）\n"
            "\n"
            "**本步必须输出路由决策，说明下一步进入哪个模式。不允许只输出文字而不提交决策。**\n"
            "\n"
            "**1 步内必须做出决策。**"
        )


class RouteAfterImplementModule(PromptModule):
    """implement 完成后的路由模块，判断是否需要校验。"""

    id = "route_after_implement"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "implement_just_finished", False)

    def render(self, context: Any, state: Any) -> str:
        phase_files = getattr(state, "implement_phase_files", [])
        replan_requested = getattr(state, "implement_replan_requested", False)
        replan_reason = getattr(state, "implement_replan_reason", "")
        run_mode = getattr(context, "run_mode", None)
        files_count = len(phase_files)

        if run_mode and hasattr(run_mode, "value"):
            is_generate = run_mode.value == "generate"
        else:
            is_generate = True

        should_validate = is_generate or files_count == 0 or files_count >= 3
        if replan_requested:
            recommendation = "plan"
        else:
            recommendation = "validate" if should_validate else "finish"

        replan_context = ""
        if replan_requested:
            replan_context = f"- 重新规划原因：{replan_reason}\n"

        user_notice = (
            "**必须遵守**：说明实现阶段因计划存在关键缺口而请求重新规划，"
            "不要声称代码已经完成。\n"
            if replan_requested
            else (
                "**必须遵守**：在提交路由决策之前，你要用自然语言告诉用户 AI 刚才完成了什么工作。"
                "例如：'代码生成完成，已更新 index.html 和 style.css 两个文件。'\n"
            )
        )

        return (
            "## 路由判断\n"
            "\n"
            "AI 刚完成代码生成，你需要判断是否需要校验。\n"
            "\n"
            f"**上下文**：\n"
            f"- 本次改动的文件数：{files_count}\n"
            f"- 改动模式：{run_mode.value if run_mode and hasattr(run_mode, 'value') else 'generate'}\n"
            f"{replan_context}"
            f"- 建议路由：{recommendation}\n"
            "\n"
            "### 判断规则\n"
            "\n"
            "- 如果实现阶段提交了重新规划请求：路由到规划模式，不得路由到校验或完成\n"
            "- 否则，如果是首次生成、没有记录到文件改动，或改动量较大（3 个以上文件）：路由到校验模式\n"
            "- 否则，如果是简单修改（1-2 个文件的小改动）：路由到完成\n"
            "\n"
            f"{user_notice}"
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
                status = r.get("status", "?")
                icon = "✓" if status == "pass" else ("✗" if status == "fail" else "⚠")
                severity = r.get('severity', '')
                if status == "pass":
                    lines.append(f"{icon} {r.get('id', '?')}: {r.get('message', '')}")
                else:
                    lines.append(f"{icon} [{severity}] {r.get('id', '?')}: {r.get('message', '')}")
            results_text = "\n".join(lines)

        failures_text = ""
        if failures:
            failure_lines = []
            for f in failures:
                failure_lines.append(f"- {f.get('issue', str(f))}")
            failures_text = "\n".join(failure_lines)

        if validation_status == "failed":
            recommendation = "implement"
        elif validation_status == "pending":
            recommendation = "implement"
        else:
            recommendation = "finish"

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
            "- 校验通过（无 error 级别失败）：路由到完成\n"
            "- 校验有 error 级别失败：路由到实现模式\n"
            "- 校验状态为 pending（未提交结论即超限）：视为失败，路由到实现模式\n"
            "\n"
            "**必须遵守**：在提交路由决策之前，你要用自然语言告诉用户刚才的校验结果，"
            "以及这次生成了什么、代码质量如何。"
            "例如：'校验通过，登录页面已创建完成，三个文件均已生成且通过所有检查。'\n"
            "\n"
            "**1 步内必须做出决策。**"
        )

        return "".join(parts)
