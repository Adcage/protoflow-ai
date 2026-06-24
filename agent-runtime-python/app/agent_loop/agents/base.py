from abc import ABC, abstractmethod
from typing import Any


class ImplementAgent(ABC):
    """Implement Agent 协议接口。

    所有模式特定的 Implement Agent 必须实现此接口。
    Agent 只消费统一传入的不可变 toolset，不得自行实例化写工具。
    """

    @abstractmethod
    async def execute(
        self,
        state: Any,
        context: Any,
        services: Any,
        contract: Any,
        toolset: Any,
    ) -> Any:
        ...
