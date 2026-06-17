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
    selected_skill_id: str = ""
    selected_seed_id: str = ""
    selected_template_id: str = ""
    selected_design_system_id: str = ""
    selected_craft_ids: list[str] = field(default_factory=list)
    selected_capabilities: Any | None = None
    capability_selection: Any | None = None
    asset_summaries: list[dict[str, Any]] = field(default_factory=list)
    selection_source: str = ""
    quality_results: list[dict[str, Any]] = field(default_factory=list)
    artifact_manifest_path: str = ""
    asset_counts: dict[str, int] = field(default_factory=dict)
    internal_summary: str = ""
    generation_plan: Any | None = None
    planning_decision: str = ""
    project_mode: str = ""
    workflow_route: str = ""
    planning_required_confirmation: bool = False
    clarification_questions: list[dict[str, Any]] = field(default_factory=list)
    implementation_outline: dict[str, Any] = field(default_factory=dict)
    planning_warnings: list[str] = field(default_factory=list)
