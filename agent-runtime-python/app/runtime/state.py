from dataclasses import dataclass, field
from typing import Any

from app.modeling.roles import ModelRole


@dataclass
class ToolCallRecord:
    id: str
    name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None


@dataclass
class NodeResult:
    node_id: str
    status: str
    latency_ms: int
    summary: str = ""
    error: str = ""


@dataclass
class ExecutionState:
    task_type: str = ""
    selected_model_role: ModelRole | None = None
    resolved_model: dict[str, Any] | None = None
    prompt_messages: list[dict[str, str]] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    model_response_text: str = ""
    model_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    pending_tool_calls: list[ToolCallRecord] = field(default_factory=list)
    executed_tool_calls: list[ToolCallRecord] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    node_results: list[NodeResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    final_summary: str = ""
    model_lc_messages: list[Any] = field(default_factory=list)
    model_response_obj: Any = None
