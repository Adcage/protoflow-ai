import logging
from uuid import uuid4

from langchain_core.tools import BaseTool

from app.agent_loop.nodes.step_base import _execute_single_step
from app.agent_loop.progress import ProgressDetector, ProgressSnapshot
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ModeToolResolver
from app.agent_loop.tools.decide_route import (
    DecideRouteTool,
    _resolve_route_source,
    apply_route_decision,
    apply_v2_route_decision,
)
from app.agent_loop.transition_guard import (
    RouteContext,
    RouteDecision,
    RouteSource,
    RouteTarget,
    TransitionGuard,
)
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.prompts.composer import PromptComposer
from app.prompts.profiles import PROMPT_PROFILES
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
from app.tools.file_tools import Workspace, FileTools
from app.tools.langchain_tools import create_file_tools

logger = logging.getLogger("app.agent_loop.nodes.route_step")


def _resolve_source_v2(state: AgentLoopState) -> RouteSource:
    legacy = _resolve_route_source(state)
    if legacy == "initial":
        return "user"
    return legacy


def _build_route_context(
    state: AgentLoopState, progress_detector: ProgressDetector
) -> RouteContext:
    source = _resolve_source_v2(state)
    envelope = getattr(state, "_state_envelope", None)
    plan_state = getattr(envelope.workflow, "plan", None) if envelope else None

    plan_has_confirmed_design = False
    plan_has_implementation_plan = False
    plan_has_unresolved = False

    if plan_state is not None:
        design = getattr(plan_state, "design_specification", None)
        if design is not None and getattr(design, "confirmed", False):
            plan_has_confirmed_design = True
        if getattr(plan_state, "implementation_plan", None) is not None:
            plan_has_implementation_plan = True
        questions = getattr(plan_state, "clarification_questions", []) or []
        plan_has_unresolved = any(
            not q.get("answered", False) for q in questions if isinstance(q, dict)
        )

    has_pending_questions = bool(getattr(state, "clarification_questions", []))
    validation_has_repair_issues = False
    validation_passed = False
    validation_has_return_plan_issues = False
    validation_has_open_issues = False

    if source == "validate":
        validation_status = getattr(state, "validation_status", "pending")
        validation_passed = validation_status == "passed"
        failures = getattr(state, "validation_failures", []) or []
        validation_has_repair_issues = len(failures) > 0 and not validation_passed
        validation_has_open_issues = len(failures) > 0
        for f in failures:
            disposition = f.get("disposition", "")
            if disposition == "return_plan":
                validation_has_return_plan_issues = True

    execution_has_pending_tasks = False
    execution_completion_passed = False
    if source == "implement":
        execution_completion_passed = getattr(
            state, "implement_just_finished", False
        )
        execution_has_pending_tasks = not execution_completion_passed

    revision = 0
    if envelope is not None:
        revision = getattr(envelope.workflow, "revision", 0)

    stagnation = progress_detector.detect_stagnation()
    cycle = progress_detector.detect_cycle()

    return RouteContext(
        source_mode=source,
        state_revision=revision,
        plan_has_confirmed_design=plan_has_confirmed_design,
        plan_has_implementation_plan=plan_has_implementation_plan,
        plan_has_unresolved=plan_has_unresolved,
        execution_has_pending_tasks=execution_has_pending_tasks,
        execution_completion_passed=execution_completion_passed,
        validation_has_open_issues=validation_has_open_issues,
        validation_has_repair_issues=validation_has_repair_issues,
        validation_has_return_plan_issues=validation_has_return_plan_issues,
        validation_passed=validation_passed,
        has_pending_questions=has_pending_questions,
        progress_stagnation=stagnation,
        progress_cycle=cycle,
    )


class RouteStepNode:
    """统一路由决策节点。

    每次图显式进入 Route 时都产生当前来源的新决策，禁止跳过并复用 stale route_decision。
    实现两次决策尝试协议：首次模型决策 → Guard 校验 → 如被拒绝则带纠正信息二次尝试 → 安全回退。
    """

    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services
        self._guard = TransitionGuard()
        self._progress_detector = ProgressDetector()

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        await self._services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.STATUS, {"message": "Route step"})
        )

        state.route_decided = False
        state.route_decision = None

        workspace = Workspace(self._context.workspace_path)
        file_tools = FileTools(workspace)
        file_lc_tools = create_file_tools(file_tools)

        decide_route = DecideRouteTool()
        decide_route.set_state(state)

        all_tools: list[BaseTool] = list(file_lc_tools) + [decide_route]
        toolset = ModeToolResolver.resolve(AgentMode.ROUTE, all_tools)

        context = _build_route_context(state, self._progress_detector)

        self._record_progress(state, context)

        system_prompt = self._compose_prompt(state, toolset)

        state.route_iterations += 1
        logger.info(
            "route_step | route_iterations=%d mode=%s route_decided=%s source=%s",
            state.route_iterations,
            state.mode,
            state.route_decided,
            context.source_mode,
        )

        result = await _execute_single_step(
            state,
            self._context,
            self._services,
            system_prompt,
            toolset,
            file_tools,
        )

        if result.route_decided:
            decision = self._extract_decision(result, context)
            if decision is not None:
                rejection = self._guard.evaluate(context, decision)
                if rejection is not None:
                    logger.warning(
                        "route_step | guard rejected first decision: target=%s failed=%s",
                        decision.target,
                        rejection.failed_rules,
                    )
                    decision2 = await self._corrective_attempt(
                        result, context, rejection, decide_route, toolset, file_tools
                    )
                    if decision2 is not None:
                        rejection2 = self._guard.evaluate(context, decision2)
                        if rejection2 is None:
                            apply_v2_route_decision(
                                result, decision2, self._get_code_gen_type(result)
                            )
                            return result
                        logger.warning(
                            "route_step | guard rejected second decision: target=%s failed=%s",
                            decision2.target,
                            rejection2.failed_rules,
                        )
                    self._apply_safe_fallback(result, context)
                    return result
            return result

        self._apply_safe_fallback(result, context)
        return result

    def _extract_decision(
        self, state: AgentLoopState, context: RouteContext
    ) -> RouteDecision | None:
        rd = state.route_decision
        if rd is None:
            return None
        if not isinstance(rd, dict):
            return None

        target_str = rd.get("target") or rd.get("mode", "plan")
        target_map: dict[str, RouteTarget] = {
            "plan": "plan",
            "implement": "implement",
            "validate": "validate",
            "finish": "finished",
            "finished": "finished",
            "wait_user": "wait_user",
            "blocked": "blocked",
        }
        target = target_map.get(target_str)
        if target is None:
            return None

        reason_code_str = rd.get("reason_code", "")
        from app.agent_loop.transition_guard import RouteReasonCode

        if reason_code_str:
            valid_codes: set[str] = set(RouteReasonCode.__args__)
            reason_code = reason_code_str if reason_code_str in valid_codes else "insufficient_info"
        else:
            reason_code = "insufficient_info"

        return RouteDecision(
            target=target,
            reason_code=reason_code,
            rationale=rd.get("reason", ""),
            evidence_refs=rd.get("evidence_refs", []),
            active_issue_ids=rd.get("active_issue_ids", []),
        )

    async def _corrective_attempt(
        self,
        state: AgentLoopState,
        context: RouteContext,
        rejection,
        decide_route_tool: DecideRouteTool,
        toolset,
        file_tools: FileTools,
    ) -> RouteDecision | None:
        correction_prompt = (
            f"\n\n## 路由纠正\n\n"
            f"上次路由决策被 Guard 拒绝：\n"
            f"- 尝试目标：{rejection.attempted_target}\n"
            f"- 失败规则：{', '.join(rejection.failed_rules)}\n"
            f"- 缺失证据：{', '.join(rejection.missing_evidence)}\n"
            f"- 允许目标：{', '.join(rejection.safe_targets)}\n\n"
            f"请重新做出路由决策，确保满足上述约束。\n"
        )
        if not state.conversation_messages:
            state.conversation_messages = []
        state.conversation_messages.append(
            {"role": "system", "content": correction_prompt}
        )

        decide_route_tool.set_state(state)
        system_prompt = self._compose_prompt(state, toolset)

        state.route_decided = False
        state.route_decision = None

        result = await _execute_single_step(
            state,
            self._context,
            self._services,
            system_prompt,
            toolset,
            file_tools,
        )

        if result.route_decided:
            return self._extract_decision(result, context)
        return None

    def _record_progress(
        self, state: AgentLoopState, context: RouteContext
    ) -> None:
        envelope = getattr(state, "_state_envelope", None)
        plan_stage = None
        if envelope is not None:
            plan_state = getattr(envelope.workflow, "plan", None)
            if plan_state is not None:
                plan_stage = getattr(plan_state, "plan_stage", None)

        phase_files = getattr(state, "implement_phase_files", []) or []
        workspace_fp = ",".join(sorted(phase_files)) if phase_files else ""

        failures = getattr(state, "validation_failures", []) or []
        val_fp = str(len(failures))

        tool_calls = getattr(state, "executed_tool_calls", []) or []
        last_tool_fp = ""
        if tool_calls:
            last = tool_calls[-1]
            last_tool_fp = f"{getattr(last, 'name', '')}:{'ok' if not getattr(last, 'error', '') else 'err'}"

        semantic_fp = (
            f"{context.source_mode}:"
            f"plan_stage={plan_stage}:"
            f"wf={workspace_fp}:"
            f"val={val_fp}:"
            f"tool={last_tool_fp}"
        )

        snapshot = ProgressSnapshot(
            snapshot_id=uuid4().hex[:8],
            source_mode=context.source_mode,
            state_revision=context.state_revision,
            plan_stage=plan_stage,
            workspace_fingerprint=workspace_fp,
            validation_issue_fingerprint=val_fp,
            last_tool_outcome_fingerprint=last_tool_fp,
            semantic_progress_fingerprint=semantic_fp,
            created_at="",
        )
        self._progress_detector.record(snapshot)

    def _compose_prompt(self, state: AgentLoopState, toolset) -> str:
        registry = getattr(self._services, "prompt_module_registry", None)
        if registry is None:
            raise AgentRuntimeError(
                "PromptModuleRegistry 不可用",
                code=AgentErrorCode.STATE_ERROR,
            )

        profile_id = self._resolve_profile_id(state)
        profile_module_ids = PROMPT_PROFILES.get(profile_id)
        if profile_module_ids is None:
            raise AgentRuntimeError(
                f"Profile {profile_id} 不存在",
                code=AgentErrorCode.STATE_ERROR,
            )

        modules = registry.require_many(profile_module_ids)
        composer = PromptComposer(modules)
        messages = composer.compose(self._context, state, toolset)
        if messages and messages[0].get("role") == "system":
            return messages[0]["content"]

        raise AgentRuntimeError(
            "PromptComposer 未能生成系统提示词",
            code=AgentErrorCode.STATE_ERROR,
        )

    def _resolve_profile_id(self, state: AgentLoopState) -> str:
        if getattr(state, "plan_just_finished", False):
            return "route_after_plan"
        if getattr(state, "implement_just_finished", False):
            return "route_after_implement"
        if getattr(state, "validate_just_finished", False):
            return "route_after_validate"
        return "route_initial"

    def _apply_safe_fallback(
        self, state: AgentLoopState, context: RouteContext
    ) -> None:
        """安全回退路由，必须走 apply_route_decision。"""
        source = _resolve_route_source(state)
        target: str

        if context.progress_cycle:
            target = "plan"
            apply_route_decision(
                state,
                source=source,
                mode=target,
                code_gen_type="",
                reason="循环检测：检测到重复模式，回退到规划",
            )
            logger.warning(
                "route_step | safe_fallback: cycle detected, routing to plan"
            )
            return

        if context.progress_stagnation:
            target = "plan"
            apply_route_decision(
                state,
                source=source,
                mode=target,
                code_gen_type="",
                reason="停滞检测：连续无进展，回退到规划",
            )
            logger.warning(
                "route_step | safe_fallback: stagnation detected, routing to plan"
            )
            return

        if context.has_pending_questions:
            target = "plan"
            apply_route_decision(
                state,
                source=source,
                mode=target,
                code_gen_type="",
                reason="有未回答的澄清问题，回退到规划",
            )
            return

        if source == "initial":
            target = "plan"
        elif source == "plan":
            target = "implement"
        elif source == "implement":
            target = (
                "plan"
                if getattr(state, "implement_replan_requested", False)
                else "validate"
            )
        elif source == "validate":
            if getattr(state, "validation_status", "pending") == "passed":
                target = "finish"
            else:
                target = "implement"
        else:
            target = "plan"

        apply_route_decision(
            state,
            source=source,
            mode=target,
            code_gen_type="",
            reason="默认路由",
        )
        logger.warning(
            "route_step | applied default route: source=%s target=%s",
            source,
            target,
        )

    def _get_code_gen_type(self, state: AgentLoopState) -> str:
        artifact_type = getattr(state, "artifact_type_state", None)
        if artifact_type is not None and getattr(artifact_type, "effective", None):
            return artifact_type.effective
        rec = getattr(state, "recommended_code_gen_type", None)
        if rec:
            return rec
        return ""
