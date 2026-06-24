"""Agent Loop 大循环提示词模块：plan/implement/validate 工作流、校验反馈、工具列表、计划规范、用户需求、Skill 上下文。"""

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


class PlanWorkflowModule(PromptModule):
    """plan 模式工作流指令（Phase 3 用户驱动设计流程）。"""

    id = "plan_workflow"
    category = "strategic"

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "mode", "") == "plan"

    def _format_clarification_history(self, state: Any) -> str:
        """展示已提出的澄清问题，避免模型反复询问同一问题。"""
        questions = getattr(state, "clarification_questions", None) or []
        if not questions:
            return ""
        lines = ["\n### 已澄清的问题\n"]
        for q in questions:
            if isinstance(q, dict):
                text = q.get("prompt") or q.get("question") or ""
                qid = q.get("id", "")
            else:
                text = str(q)
                qid = ""
            if qid:
                lines.append(f"- [{qid}] {text}")
            else:
                lines.append(f"- {text}")
        lines.append("\n上述问题已提出，请勿再次询问。如用户回答已在对话历史中，直接根据回答继续。\n")
        return "\n".join(lines)

    def _format_stage(self, state: Any) -> str:
        envelope = getattr(state, "_state_envelope", None)
        if envelope is None:
            return ""
        plan = getattr(envelope.workflow, "plan", None)
        if plan is None:
            return ""
        stage = getattr(plan, "plan_stage", "discover_direction")
        return f"当前 PlanStage：{stage}\n"

    def _format_progress(self, state: Any) -> str:
        envelope = getattr(state, "_state_envelope", None)
        if envelope is None:
            return ""
        plan = getattr(envelope.workflow, "plan", None)
        if plan is None:
            return ""
        items = []
        if plan.requirement_brief is not None:
            items.append("需求摘要")
        if plan.project_inspection is not None:
            items.append("项目检查")
        if plan.selected_skill_id:
            items.append("技能选择")
        if plan.design_specification is not None:
            if plan.design_specification.confirmed:
                items.append("设计方案已确认")
            else:
                items.append("设计方案已提交待确认")
        if plan.implementation_plan is not None:
            items.append("实施计划已写完")
        if not items:
            return ""
        return "已完成的步骤：" + " → ".join(items) + "\n"

    def render(self, context: Any, state: Any) -> str:
        clarification_history = self._format_clarification_history(state)
        stage_line = self._format_stage(state)
        progress_line = self._format_progress(state)
        return (
            "你处于规划模式（Plan Mode）。你的职责是充分理解用户需求，"
            "完成多轮用户驱动设计澄清，并基于用户确认的结构化 DesignSpecification"
            "生成结构化 ImplementationPlan，由 Route 决定下一阶段。\n"
            "\n"
            "**核心原则：plan 模式是用户驱动的设计澄清与确认流程；你不能替用户做关键选择、"
            "不能直接进入实现、不能修改任何项目文件。**\n"
            f"{clarification_history}"
            f"{stage_line}"
            f"{progress_line}"
            "\n"
            "## 工作流（必须严格按当前 PlanStage 推进）\n"
            "\n"
            "**阶段推进规则**：每个 PlanStage 都有唯一允许的状态提交工具，"
            "调用它把对应字段写入状态后才能推进到下一阶段；跳阶段提交会被状态机拒绝。"
            "被拒绝时请改用本阶段允许的提交工具重试，不要直接结束对话。\n"
            "\n"
            "**discover_direction**：首次进入或用户改换方向时停留此阶段。"
            "必须询问应用方向、目标用户、主要使用场景；缺一即停留。"
            "本阶段需要提交**需求摘要**（application_direction + target_users 必填）后才能推进。\n"
            "\n"
            "**discover_scope**：方向摘要已提交后进入此阶段。询问功能范围、内容与数据需求、"
            "响应式目标、可访问性期望。每次只问同一决策层的少量问题（1~3 个）。"
            "范围澄清后需要提交**项目检查记录**（新建项目 decision=not_applicable，"
            "已有项目 decision=inspected + evidence_files）后推进。\n"
            "\n"
            "**inspect_existing_project**：已有项目修改时执行。必须只读检查相关目录与关键文件，"
            "使用**项目检查记录工具**写入 decision=inspected 并提供 evidence_files；"
            "新建项目使用 decision=not_applicable。\n"
            "\n"
            "**Skill 选择阶段**：基于需求和项目证据，从当前模式可用工具中选择合适的 Skill 入口。"
            "必须填写 selected_reason 引用证据；如确无匹配 Skill，形成结构化 NO_MATCHING_SKILL open item。"
            "选择 Skill 后自动推进到设计阶段。\n"
            "\n"
            "**design_propose 阶段**：使用当前模式的**设计提交工具**提交结构化 DesignSpecification。"
            "每个关键维度（视觉方向、配色、字体、组件语言、交互、响应式）必须给出至少 2~3 个互斥候选。"
            "提交后自动进入设计确认阶段。\n"
            "\n"
            "**design_confirm 阶段**：收到设计方案后，必须先通过结构化提问向用户完整展示所有"
            "设计备选，让用户在「没有需要调整」或「需要调整」中进行选择。"
            "用户明确表示确认后，再使用设计确认工具（直接使用设计确认工具会被系统拒绝，"
            "因为必须先通过结构化提问获取用户反馈）。\n"
            "\n"
            "**实施计划生成阶段**：设计确认后自动进入此阶段；"
            "不要再次询问「是否需要生成实施计划」。使用**实施计划写入工具**提交结构化 ImplementationPlan。"
            "每个 ImplementationTask 必须包含 task_id、"
            "goal、allowed_files、prohibited_files、dependencies、inputs、outputs、"
            "test_requirements、acceptance_criteria。\n"
            "\n"
            "## 关键约束\n"
            "\n"
            "- 禁止根据最佳实践替用户决定功能、布局、配色、风格或交互；\n"
            "- 禁止把「推荐」写成「已确认」；\n"
            "- 禁止在用户未确认最终设计时生成实施计划；\n"
            "- 禁止写业务文件、修改项目文件或执行写命令；\n"
            "- 禁止切换到 implement 或 validate；\n"
            "- 禁止达到调用硬上限后自动宣称完成；\n"
            "- 一轮只询问同一决策层的少量问题，禁止把整张大表单一次抛出。\n"
            "\n"
            "## 注意事项\n"
            "\n"
            "- Plan 阶段模型调用硬上限 60 次；达到 30 次时由编排层触发自检；"
            "达到 60 次且未满足完成门禁时进入 blocked 或 waiting_for_user。\n"
            "- 不得连续抛出 3 次以上单选；否则将触发状态机告警。\n"
            "- 当前模式的可用能力见上方工具列表，具体工具名称和参数由系统动态提供。\n"
            "\n"
            "## 当前阶段应使用的工具\n"
            "\n"
            "根据 `当前 PlanStage` 选择对应的推进方式，**不要反复读取目录**——目录内容不会自行变化。\n"
            "- **discover_direction** → 提交需求摘要（方向 + 目标用户必填）\n"
            "- **discover_scope** → 补充提交需求摘要；完成后提交项目检查记录\n"
            "- **inspect_existing_project** → 提交项目检查记录（已检查则填 evidence_files，新项目填 not_applicable）\n"
            "- **技能选择阶段** → 提交技能选择\n"
            "- **propose 设计** → 提交 6 个维度的设计方案\n"
            "- **confirm阶段** → 先用结构化提问展示方案、等用户回答，再提交确认\n"
            "- **实施计划生成** → 提交实施计划\n"
        )


class ImplementWorkflowModule(PromptModule):
    """implement 模式工作流指令。"""

    id = "implement_workflow"
    category = "strategic"

    # 与 ProjectRulesModule 保持一致的强制产物清单，作为阶段完成的硬门禁
    _REQUIRED_ARTIFACTS: dict[str, list[str]] = {
        "single_file": ["index.html"],
        "multi-file": ["index.html", "style.css", "script.js"],
    }

    def enabled(self, context: Any, state: Any) -> bool:
        return getattr(state, "mode", "") == "implement"

    def _build_artifact_progress(self, code_gen_type: str, state: Any) -> str:
        """根据项目类型和已写入文件构建进度提示。"""
        required = list(self._REQUIRED_ARTIFACTS.get(code_gen_type, []))
        written = list(getattr(state, "implement_phase_files", []) or [])

        if not required:
            return ""

        written_set = set(written)
        lines = ["### 必须生成的文件清单\n"]
        for f in required:
            marker = "[已完成]" if f in written_set else "[待生成]"
            lines.append(f"- {marker} {f}")

        remaining = [f for f in required if f not in written_set]
        if remaining:
            lines.append(f"\n下一个待生成文件：{remaining[0]}")
        else:
            lines.append("\n所有必须文件已生成，应提交完成结果。")

        return "\n".join(lines) + "\n"

    def render(self, context: Any, state: Any) -> str:
        outline_text = "暂无实现规划"
        outline = getattr(state, "implementation_outline", None)
        if outline:
            if isinstance(outline, dict):
                outline_text = outline.get("text", str(outline))
            else:
                outline_text = str(outline)

        code_gen_type = _get_effective_type(state, context)

        is_vue = code_gen_type == "vue_project"
        dependency_step = ""
        if is_vue:
            dependency_step = (
                "\n- 项目类型为 Vue 工程：所有文件写入后，如果终端工具可用，应安装依赖包；如果终端工具不可用，跳过此步。\n"
            )

        artifact_progress = self._build_artifact_progress(code_gen_type, state)

        parts = [
            "你处于实现模式（Implement Mode）。你的职责是按照实施计划将项目代码写入工作区。\n",
            "\n**重要：进入 implement 模式后，专注于代码生成，不要再反复分析或重复读取已有文件。**\n",
            f"\n## 实施计划\n\n{outline_text}\n",
            "\n## 工作流 —— 新建\n",
            "\n- 按实施计划中列出的文件顺序逐一创建文件。\n",
            "- 每个文件一次性写入完整内容，不省略、不使用占位符。\n",
            "- 文件路径使用正斜杠 /。\n",
            "- 不需要为了确认空工作区而反复读取目录。\n",
            dependency_step,
            "- 所有计划文件创建完成后，提交完成结果并说明完成了什么。\n",
            "\n## 工作流 —— 修改\n",
            "\n- 先了解当前工作区的目录结构和已有文件。\n",
            "- 再读取需要修改的文件当前内容。\n",
            "- 只修改与当前需求直接相关的内容，保持未授权文件和既有行为不变。\n",
            "- 每次修改都写入完整的文件内容。\n",
            "- 修改完成后，提交完成结果并说明修改了什么。\n",
            "\n## 阶段完成门禁\n",
            "\n完成当前阶段前必须满足：\n",
            "- 已生成项目规则要求的全部文件，且每个文件内容完整可运行；\n",
            "- 不得在同一文件上反复重写（同一文件连续写入超过一次即视为已完成，应继续下一个文件）；\n",
            "- 未生成全部必须文件前，不得提交完成结果。\n",
            f"\n{artifact_progress}",
            "\n## 计划不完整时的处理\n",
            "\n如果实施计划缺少以下关键信息，不能继续实现：\n",
            "- 缺少架构决策（框架选择、路由方案、状态管理模式等）；\n",
            "- 缺少交互定义（页面跳转关系、表单行为、数据流向等）；\n",
            "- 缺少文件范围（需要哪些文件、每个文件的职责）；\n",
            "- 其他可能影响产品行为、结构或交互的未明确内容。\n",
            "\n遇到上述情况时，不得自行补全后继续实现，也不得提交完成结果。应提交重新规划请求并说明具体缺失内容，由编排层决定下一阶段。\n",
            "\n## 实现细节补全的边界\n",
            "\n- 只能在用户已确认的需求、项目规则和已批准的实施计划范围内补充实现细节。\n",
            "- 允许补全的非关键细节：配色微调、间距数值、字重选择等不影响功能和结构的视觉细节。\n",
            "- 任何可能影响产品行为、架构、交互、权限、文件范围或视觉方向的内容都必须先确认，不得自行决定。\n",
            "\n## 注意事项\n",
            "\n- 当前模式的可用能力见上方工具列表，具体工具名称和参数由系统动态提供。\n",
            "- 每个文件写入完整可运行的代码，不要在文件之间拆分不完整的片段。\n",
            "- 不要伪造工具执行结果。\n",
            "- 生成过程直奔主题，3-5 个文件内完成。\n",
            "- **不要在回复中复述 Skill 原文内容**，只引用关键规则和约束，对用户可见的回复必须是简洁的中文摘要。\n",
        ]

        return "".join(parts)


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
                status = r.get("status", "?")
                icon = "✓" if status == "pass" else ("✗" if status == "fail" else "⚠")
                severity = r.get('severity', '')
                if status == "pass":
                    lines.append(f"{icon} {r.get('id', '?')}: {r.get('message', '')}")
                else:
                    lines.append(f"{icon} [{severity}] {r.get('id', '?')}: {r.get('message', '')}")
            check_results_text = "\n".join(lines)

        parts = [
            "你处于校验模式（Validate Mode）。你的职责是检查已生成的代码是否符合项目结构要求。\n",
            "\n",
            "## 工作流\n",
            "\n",
            "1. 首先执行项目结构校验，获取检查结果。\n",
            "2. 根据检查结果，如有必要可查看文件内容进一步了解详情。\n",
            "3. 综合判断后输出校验结论。\n",
            "\n",
            "## 校验判断规则\n",
            "\n",
            "- 如果存在 error 级别的失败（如入口文件缺失）：输出失败结论，列出问题和修复建议\n",
            "- 如果仅有 warning 级别的提醒（如占位符文本）：可接受，输出通过结论\n",
            "- 如果全部通过：输出通过结论\n",
            "\n",
            "**注意：3 步内必须输出校验结论。**",
        ]

        if check_results_text:
            parts.append(f"\n\n## 已缓存的检查结果\n\n{check_results_text}\n\n（已执行过结构校验，无需重复执行）")

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

    def __init__(self, tools: list | tuple | None = None) -> None:
        super().__init__()
        self._tools: tuple = tuple(tools) if tools else ()

    def enabled(self, context: Any, state: Any) -> bool:
        return len(self._tools) > 0

    def render(self, context: Any, state: Any) -> str:
        from app.prompts.tool_summary import format_tool_summary

        return format_tool_summary(self._tools)


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
            "请严格按照以下规范编写实现计划并写入状态。\n"
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
        if caps is not None and getattr(caps, "skill", None) is not None:
            return True
        index = getattr(state, "_asset_index", None)
        if index is None:
            return False
        skills = index.skill_registry.all()
        return bool(skills)

    def render(self, context: Any, state: Any) -> str:
        caps = getattr(state, "selected_capabilities", None)
        skill = getattr(caps, "skill", None) if caps is not None else None
        if skill is None:
            index = getattr(state, "_asset_index", None)
            if index is not None:
                skills = index.skill_registry.all()
                if skills:
                    lines = ["## 可用 Skill 列表\n", "\n你可以选择一个适合当前任务的 Skill。\n"]
                    for s in skills:
                        lines.append(f"- **{s.id}**: {s.description}")
                    return "\n".join(lines)
            return ""

        skill_dir = str(skill.source_path.parent)
        parts = [
            "## 已选择的 Skill\n",
            f"\n**{skill.name}** (ID: {skill.id}): {skill.description}\n",
            f"\nSkill 目录：`{skill_dir}`\n",
        ]

        if skill.body:
            parts.append(f"\n### Skill 规则（已加载，无需再读取 SKILL.md）\n\n{skill.body.strip()}\n")

        if skill.references:
            parts.append("\n### Skill 可用参考资源\n")
            parts.append("\n如需参考布局/清单，按需读取以下文件：")
            for ref in skill.references:
                parts.append(f"\n  - {ref}")
            parts.append("\n\n**注意：不要逐个读取所有参考文件，只按需读取最相关的。**")

        return "".join(parts)
