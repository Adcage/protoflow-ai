from dataclasses import dataclass
from typing import Any


@dataclass
class RuntimeServices:
    platform_client: Any = None
    tool_client: Any = None
    chat_model_factory: Any = None
    model_policy: Any = None
    model_resolver: Any = None
    prompt_composer: Any = None
    tool_registry: Any = None
    prompt_module_registry: Any = None
    event_bus: Any = None
    node_registry: Any = None
