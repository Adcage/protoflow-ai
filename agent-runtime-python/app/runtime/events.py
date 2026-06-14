from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeEventType(str, Enum):
    STATUS = "status"
    TEXT_DELTA = "text_delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    MODEL_SELECTED = "model_selected"
    RUNTIME_ERROR = "runtime_error"
    DONE = "done"


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: RuntimeEventType
    data: dict[str, Any] = field(default_factory=dict)
