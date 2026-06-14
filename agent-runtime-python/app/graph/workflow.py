import logging
import time

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.state import ExecutionState, NodeResult
from app.runtime.services import RuntimeServices
from app.registries.node_registry import NodeRegistry

logger = logging.getLogger("app.graph.workflow")

_CRITICAL_NODES = {"prepare_context", "resolve_model", "call_model", "execute_tools"}


class WorkflowEngine:
    def __init__(self, node_registry: NodeRegistry) -> None:
        self._registry = node_registry

    async def execute(
        self,
        definition: list[str],
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
    ) -> ExecutionState:
        for node_id in definition:
            node = self._registry.get(node_id)

            if not node.can_run(context, state):
                logger.info("skipped node | id=%s reason=can_run_false", node_id)
                continue

            await services.event_bus.emit(
                RuntimeEvent(RuntimeEventType.NODE_STARTED, {"node_id": node_id, "node_name": node.metadata.name})
            )

            start_ms = _now_ms()
            try:
                state = await node.run(context, state, services)
                elapsed = _now_ms() - start_ms
                result = NodeResult(node_id=node_id, status="success", latency_ms=elapsed)
                state.node_results.append(result)
                logger.info("node completed | id=%s latency_ms=%d", node_id, elapsed)
            except AgentRuntimeError as e:
                elapsed = _now_ms() - start_ms
                result = NodeResult(node_id=node_id, status="error", latency_ms=elapsed, error=str(e))
                state.node_results.append(result)
                state.errors.append(f"[{node_id}] {e}")
                logger.error("node error | id=%s error=%s", node_id, e)

                await services.event_bus.emit(
                    RuntimeEvent(RuntimeEventType.RUNTIME_ERROR, {"message": str(e), "code": int(e.code)})
                )

                if node_id in _CRITICAL_NODES:
                    logger.error("critical node failed, terminating | id=%s", node_id)
                    break
            except Exception as e:
                elapsed = _now_ms() - start_ms
                result = NodeResult(node_id=node_id, status="error", latency_ms=elapsed, error=str(e))
                state.node_results.append(result)
                state.errors.append(f"[{node_id}] {e}")
                logger.error("node unexpected error | id=%s error=%s", node_id, e, exc_info=True)

                await services.event_bus.emit(
                    RuntimeEvent(RuntimeEventType.RUNTIME_ERROR, {"message": str(e), "code": AgentErrorCode.INTERNAL_ERROR})
                )

                if node_id in _CRITICAL_NODES:
                    break

            await services.event_bus.emit(
                RuntimeEvent(RuntimeEventType.NODE_COMPLETED, {"node_id": node_id})
            )

        return state


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
