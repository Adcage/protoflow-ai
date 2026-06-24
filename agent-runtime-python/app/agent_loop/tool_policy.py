from dataclasses import dataclass
from enum import Enum

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


class AgentMode(str, Enum):
    PLAN = "plan"
    IMPLEMENT = "implement"
    ROUTE = "route"
    VALIDATE = "validate"


PLAN_TOOLS = frozenset(
    {
        "read_file",
        "read_dir",
        "read_asset",
        "run_command",
        "ask_user",
        "select_skill",
        "write_plan",
        "submit_requirement_brief",
        "record_project_inspection",
        "choose_skill",
        "propose_design",
        "confirm_design",
        "write_implementation_plan",
        "plan_stage_guard",
        "confirm_generation_mode",
    }
)

IMPLEMENT_TOOLS = frozenset(
    {
        "read_file",
        "read_dir",
        "read_asset",
        "write_file",
        "run_command",
        "complete_implementation",
        "request_replan",
    }
)

ROUTE_TOOLS = frozenset({"read_file", "read_dir", "decide_route"})

VALIDATE_TOOLS = frozenset(
    {"read_file", "read_dir", "run_checks", "submit_validation_report"}
)

PLAN_REQUIRED_TOOLS: frozenset[str] = frozenset({"write_plan"})
IMPLEMENT_REQUIRED_TOOLS: frozenset[str] = frozenset({"write_file", "complete_implementation"})
ROUTE_REQUIRED_TOOLS: frozenset[str] = frozenset({"decide_route"})
VALIDATE_REQUIRED_TOOLS: frozenset[str] = frozenset({"run_checks", "submit_validation_report"})


@dataclass(frozen=True)
class ModeToolPolicy:
    mode: AgentMode
    allowed_tool_names: frozenset[str]
    required_tool_names: frozenset[str] = frozenset()

    def require_allowed(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tool_names:
            raise AgentRuntimeError(
                f"模式 {self.mode.value} 无权调用工具 {tool_name}",
                code=AgentErrorCode.TOOL_CALL_FAILED,
            )


MODE_TOOL_POLICIES: dict[AgentMode, ModeToolPolicy] = {
    AgentMode.PLAN: ModeToolPolicy(
        mode=AgentMode.PLAN,
        allowed_tool_names=PLAN_TOOLS,
        required_tool_names=PLAN_REQUIRED_TOOLS,
    ),
    AgentMode.IMPLEMENT: ModeToolPolicy(
        mode=AgentMode.IMPLEMENT,
        allowed_tool_names=IMPLEMENT_TOOLS,
        required_tool_names=IMPLEMENT_REQUIRED_TOOLS,
    ),
    AgentMode.ROUTE: ModeToolPolicy(
        mode=AgentMode.ROUTE,
        allowed_tool_names=ROUTE_TOOLS,
        required_tool_names=ROUTE_REQUIRED_TOOLS,
    ),
    AgentMode.VALIDATE: ModeToolPolicy(
        mode=AgentMode.VALIDATE,
        allowed_tool_names=VALIDATE_TOOLS,
        required_tool_names=VALIDATE_REQUIRED_TOOLS,
    ),
}
