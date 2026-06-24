from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CodeGenType(str, Enum):
    SINGLE_FILE = "single_file"
    MULTI_FILE = "multi-file"
    VUE_PROJECT = "vue_project"


_CODE_GEN_TYPE_TO_GENERATION_MODE: dict[str, str] = {
    "single_file": "application",
    "multi-file": "application",
    "vue_project": "application",
}


class RunMode(str, Enum):
    GENERATE = "generate"
    MODIFY = "modify"
    ROUTE = "route"


@dataclass(frozen=True)
class AppContext:
    id: int
    name: str
    description: str
    code_gen_type: CodeGenType
    user_id: int


@dataclass(frozen=True)
class ChatHistoryEntry:
    id: int
    role: str
    content: str


@dataclass(frozen=True)
class ExecutionContext:
    agent_run_id: int
    app_id: int
    session_id: int
    user_id: int
    prompt: str
    code_gen_type: CodeGenType
    workspace_path: str
    run_mode: RunMode
    app: AppContext | None = None
    chat_history: tuple[ChatHistoryEntry, ...] = ()
    original_content: str = ""
    runtime_options: dict[str, Any] = field(default_factory=dict)
    is_test: bool = False
    is_resume: bool = False
    generation_mode: str | None = None
