import logging

from app.nodes.base import RuntimeNode

logger = logging.getLogger("app.registries.node_registry")


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, RuntimeNode] = {}

    def register(self, node: RuntimeNode) -> None:
        node_id = node.metadata.id
        if node_id in self._nodes:
            raise ValueError(f"Duplicate runtime node id: {node_id}")
        self._nodes[node_id] = node
        logger.info("registered runtime node | id=%s name=%s", node_id, node.metadata.name)

    def get(self, node_id: str) -> RuntimeNode:
        if node_id not in self._nodes:
            raise KeyError(f"Runtime node not registered: {node_id}")
        return self._nodes[node_id]

    def ids(self) -> list[str]:
        return list(self._nodes.keys())
