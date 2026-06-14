from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.runtime.context import ExecutionContext
from app.runtime.state import ExecutionState
from app.runtime.services import RuntimeServices


@dataclass(frozen=True)
class NodeMetadata:
    id: str
    name: str
    description: str = ""


class RuntimeNode(ABC):
    metadata: NodeMetadata

    def can_run(self, context: ExecutionContext, state: ExecutionState) -> bool:
        return True

    @abstractmethod
    async def run(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
    ) -> ExecutionState:
        raise NotImplementedError
