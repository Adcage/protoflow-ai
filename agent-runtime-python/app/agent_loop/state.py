import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from app.runtime.state import ToolCallRecord
from app.agent_loop.tool_history import compact_tool_records
from app.core.config import settings

logger = logging.getLogger("app.agent_loop.state")

_PERSIST_FIELDS = (
    "mode", "status", "iteration", "mode_switches",
    "selected_skill_id", "implementation_outline", "clarification_questions",
    "files_touched", "implement_phase_files",
    "implement_replan_requested", "implement_replan_reason",
    "executed_tool_calls", "conversation_messages",
    "resolved_model", "plan_iterations",
    # 前置路由
    "route_decided", "route_decision", "route_iterations",
    "recommended_code_gen_type",
    # 校验循环
    "validate_iterations", "validation_failures", "validation_check_results",
    "validation_status", "implement_just_finished", "validate_just_finished",
    "plan_just_finished",
    # 测试模式
    "is_test",
    # 提示词追踪
    "prompt_modules_applied",
    # AI 完成总结
    "final_summary",
)


@dataclass
class AgentLoopState:
    mode: Literal["plan", "implement", "validate", "finish"] = "plan"
    status: Literal["running", "completed", "failed", "waiting_for_user"] = "running"

    iteration: int = 0
    max_iterations: int = 50
    mode_switches: int = 0
    max_mode_switches: int = 6

    selected_capabilities: Any | None = None
    implementation_outline: dict | None = None
    clarification_questions: list[dict] = field(default_factory=list)

    files_touched: list[str] = field(default_factory=list)
    implement_phase_files: list[str] = field(default_factory=list)
    implement_replan_requested: bool = False
    implement_replan_reason: str = ""
    executed_tool_calls: list[ToolCallRecord] = field(default_factory=list)
    model_response_text: str = ""

    resolved_model: dict[str, Any] | None = None

    conversation_messages: list[dict] = field(default_factory=list)
    skill_context: dict | None = None

    _asset_index: Any = None
    selected_skill_id: str | None = None
    plan_iterations: int = 0
    max_plan_iterations: int = 15

    # 前置路由
    route_decided: bool = False
    route_decision: dict | None = None   # {"mode": "plan", "code_gen_type": "", "reason": ""}
    route_iterations: int = 0
    recommended_code_gen_type: str | None = None

    # 校验循环
    validate_iterations: int = 0
    max_validate_iterations: int = 3
    validation_failures: list[dict] = field(default_factory=list)
    validation_check_results: list[dict] | None = None
    validation_status: Literal["pending", "passed", "failed"] = "pending"

    # 阶段标记（用于 route_step 提示词模块判断）
    plan_just_finished: bool = False
    implement_just_finished: bool = False
    validate_just_finished: bool = False

    # 测试模式
    is_test: bool = False

    # 提示词追踪
    prompt_modules_applied: list[str] = field(default_factory=list)

    # AI 完成总结（由 finish 工具写入，finish 节点在 DONE 事件中发出）
    final_summary: str = ""

    def serialize(self) -> str:
        data = {}
        for f in _PERSIST_FIELDS:
            val = getattr(self, f)
            if f == "executed_tool_calls":
                records = compact_tool_records(
                    val,
                    max_total_chars=settings.agent_tool_history_max_chars,
                    max_result_chars=settings.agent_tool_result_max_chars,
                )
                val = [
                    {
                        "id": r.id,
                        "name": r.name,
                        "arguments": r.arguments,
                        "result": r.result,
                        "error": r.error,
                    }
                    for r in records
                ]
            if f == "resolved_model" and isinstance(val, dict):
                val = {k: v for k, v in val.items() if k != "apiKey"}
            if f == "route_decision" and isinstance(val, dict):
                val = val  # 保留完整路由决策
            data[f] = val
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_graph_result(
        cls,
        result: "AgentLoopState | dict[str, Any]",
    ) -> "AgentLoopState":
        if isinstance(result, cls):
            return result
        if not isinstance(result, dict):
            raise TypeError(f"Unsupported graph result type: {type(result).__name__}")

        state = cls()
        for key, value in result.items():
            if not hasattr(state, key):
                continue
            if key == "executed_tool_calls":
                value = [
                    record
                    if isinstance(record, ToolCallRecord)
                    else ToolCallRecord(
                        id=record["id"],
                        name=record["name"],
                        arguments=record.get("arguments", {}),
                        result=record.get("result"),
                        error=record.get("error"),
                    )
                    for record in value
                ]
            setattr(state, key, value)
        return state

    @classmethod
    def deserialize(cls, json_str: str) -> "AgentLoopState":
        data = json.loads(json_str)
        executed = data.pop("executed_tool_calls", [])
        data["executed_tool_calls"] = [
            ToolCallRecord(
                id=r["id"], name=r["name"],
                arguments=r["arguments"], result=r.get("result"), error=r.get("error"),
            )
            for r in executed
        ]
        state = cls()
        for key, val in data.items():
            if hasattr(state, key):
                setattr(state, key, val)
        return state
