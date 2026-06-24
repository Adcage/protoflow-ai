import logging

from app.agent_loop.state import AgentLoopState
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.agent_loop.nodes.finish")


class FinishNode:
    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        if state.status == "running":
            if state.iteration >= state.max_iterations:
                state.status = "failed"
                if not state.final_summary:
                    state.final_summary = "全局迭代上限已到，任务未能完成"
            else:
                state.status = "failed"
                state.final_summary = state.final_summary or "运行异常终止，未产生有效完成证据"

        logger.info(
            "finish | status=%s files=%d iterations=%d switches=%d",
            state.status,
            len(state.files_touched),
            state.iteration,
            state.mode_switches,
        )

        await self._services.event_bus.emit(
            RuntimeEvent(
                RuntimeEventType.AGENT_LOOP_COMPLETED,
                {
                    "status": state.status,
                    "files_touched": len(state.files_touched),
                    "iterations": state.iteration,
                    "mode_switches": state.mode_switches,
                },
            )
        )

        if state.status == "waiting_for_user":
            await self._services.event_bus.emit(
                RuntimeEvent(
                    RuntimeEventType.DONE,
                    {"message": "waiting_for_user", "loop_state_json": state.serialize()},
                )
            )
        else:
            final_summary = getattr(state, "final_summary", "") or ""
            await self._services.event_bus.emit(
                RuntimeEvent(RuntimeEventType.DONE,
                    {"message": final_summary if final_summary else ""})
            )

        return state
