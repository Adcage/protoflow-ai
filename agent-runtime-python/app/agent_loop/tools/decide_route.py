import logging
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.tools.decide_route")

RouteSource = Literal["initial", "plan", "implement", "validate"]
RouteTarget = Literal["plan", "implement", "validate", "finish"]
RouteCodeGenType = Literal["", "single_file", "multi-file", "vue_project"]

_ALLOWED_TRANSITIONS: dict[RouteSource, frozenset[RouteTarget]] = {
    "initial": frozenset({"plan", "implement"}),
    "plan": frozenset({"plan", "implement"}),
    "implement": frozenset({"plan", "validate", "finish"}),
    "validate": frozenset({"plan", "implement", "finish"}),
}


def apply_route_decision(
    state,
    *,
    source: RouteSource,
    mode: RouteTarget,
    code_gen_type: RouteCodeGenType,
    reason: str,
) -> None:
    """唯一提交运行时 mode 变化的函数。

    只有此函数可以写入 state.mode、state.route_decision、state.route_decided
    和 state.mode_switches。DecideRouteTool 和 Route 安全回退都必须调用此函数。

    校验失败时不得部分写入任何字段。
    """
    allowed = _ALLOWED_TRANSITIONS.get(source)
    if allowed is None:
        raise AgentRuntimeError(
            f"未知的路由来源: {source}",
            code=AgentErrorCode.TOOL_ARGS_ERROR,
        )
    if mode not in allowed:
        raise AgentRuntimeError(
            f"路由来源 {source} 不允许目标 {mode}，允许目标: {sorted(allowed)}",
            code=AgentErrorCode.TOOL_ARGS_ERROR,
        )

    old_mode = getattr(state, "mode", None)
    if mode == "implement" and old_mode != "implement":
        state.implement_phase_files = []
    state.route_decision = {
        "mode": mode,
        "code_gen_type": code_gen_type,
        "reason": reason,
    }
    state.mode = mode
    if code_gen_type:
        state.recommended_code_gen_type = code_gen_type
    if old_mode != mode:
        state.mode_switches += 1
    state.plan_just_finished = False
    state.implement_just_finished = False
    state.validate_just_finished = False
    state.implement_replan_requested = False
    state.implement_replan_reason = ""
    state.route_decided = True


def _resolve_route_source(state) -> RouteSource:
    """根据状态标记判断路由来源。"""
    if getattr(state, "plan_just_finished", False):
        return "plan"
    if getattr(state, "implement_just_finished", False):
        return "implement"
    if getattr(state, "validate_just_finished", False):
        return "validate"
    return "initial"


class DecideRouteInput(BaseModel):
    mode: Literal["plan", "implement", "validate", "finish"] = Field(
        description="路由目标模式：plan(需规划)、implement(直接实现)、validate(需校验)、finish(直接完成)"
    )
    code_gen_type: RouteCodeGenType = Field(
        default="",
        description="推荐的应用类型，仅在首次路由且 code_gen_type 未确定时填写：single_file / multi-file / vue_project",
    )
    reason: str = Field(
        default="",
        description="路由理由简述",
    )


class DecideRouteTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "decide_route"
    description: str = "判断请求应进入哪种模式后调用此工具输出决策。必须调用。"
    args_schema: type[BaseModel] = DecideRouteInput

    _state: object | None = None

    def set_state(self, state) -> None:
        self._state = state

    def _run(self, **kwargs) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        mode: str = "plan",
        code_gen_type: RouteCodeGenType = "",
        reason: str = "",
    ) -> str:
        if self._state is not None:
            source = _resolve_route_source(self._state)
            apply_route_decision(
                self._state,
                source=source,
                mode=mode,
                code_gen_type=code_gen_type,
                reason=reason,
            )
        type_info = f" 应用类型：{code_gen_type}" if code_gen_type else ""
        return f"路由决策已记录：进入 {mode} 模式。{type_info}"
