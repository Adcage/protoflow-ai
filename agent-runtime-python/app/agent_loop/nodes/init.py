import logging

from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import ArtifactTypeState
from app.capabilities.common.asset_index import AssetIndex
from app.modeling.roles import ModelRole
from app.runtime.context import ExecutionContext
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.agent_loop.nodes.init")


def _model_config_incomplete(resolved_model: dict | None) -> bool:
    if not resolved_model:
        return True
    return not all(
        resolved_model.get(key)
        for key in ("provider", "modelName", "apiKey")
    )


class InitNode:
    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        # 从 context 传播 is_test 到 state
        if self._context.is_test and not state.is_test:
            state.is_test = True

        if state.iteration > 0 or state.selected_skill_id is not None:
            logger.info(
                "init | resuming from paused state, skipping full init | iteration=%d skill_id=%s",
                state.iteration,
                state.selected_skill_id,
            )
            asset_manager = self._services.asset_manager
            if asset_manager is not None and state._asset_index is None:
                try:
                    state._asset_index = asset_manager.get_index()
                except Exception as e:
                    logger.warning("init | asset loading failed on resume: %s", e)

            if self._services.model_resolver is not None and _model_config_incomplete(state.resolved_model):
                try:
                    await self._services.model_resolver.load_bundle(self._context)
                    model_config = self._services.model_resolver.resolve(ModelRole.PRIMARY)
                    state.resolved_model = {
                        "provider": model_config.provider,
                        "modelName": model_config.model_name,
                        "baseUrl": model_config.base_url,
                        "apiKey": model_config.api_key,
                    }
                except Exception as e:
                    logger.warning("init | model resolution failed on resume: %s", e)

            if state.selected_skill_id and state._asset_index is not None and state.selected_capabilities is None:
                try:
                    index = state._asset_index
                    skill_def = index.skill_registry.get(state.selected_skill_id)
                    if skill_def is not None:
                        from app.capabilities.common.loader_result import SelectedCapabilities
                        from app.capabilities.common.capability_selection import CapabilitySelection
                        selection = CapabilitySelection(
                            skill_ids=(state.selected_skill_id,),
                            selection_source="agent_loop_resume",
                            reason="从暂停状态恢复",
                        )
                        state.selected_capabilities = SelectedCapabilities(
                            selection=selection,
                            skills=[skill_def],
                        )
                        logger.info("init | rebuilt selected_capabilities for skill_id=%s", state.selected_skill_id)
                except Exception as e:
                    logger.warning("init | failed to rebuild selected_capabilities: %s", e)

            return state

        state.mode = "plan"
        state.status = "running"

        code_gen_type_str = getattr(self._context.code_gen_type, "value", str(self._context.code_gen_type))
        state.artifact_type_state = ArtifactTypeState(
            requested=code_gen_type_str,
            effective=code_gen_type_str,
        )

        generation_mode = getattr(self._context, "generation_mode", None)
        if generation_mode is None:
            from app.runtime.context import _CODE_GEN_TYPE_TO_GENERATION_MODE
            generation_mode = _CODE_GEN_TYPE_TO_GENERATION_MODE.get(code_gen_type_str, "application")

        envelope = getattr(state, "_state_envelope", None)
        if envelope is not None:
            envelope.workflow.generation_mode = generation_mode

        asset_manager = self._services.asset_manager
        if asset_manager is not None:
            try:
                index: AssetIndex = asset_manager.get_index()
                state._asset_index = index
                logger.info(
                    "init | assets loaded: skills=%d seeds=%d templates=%d ds=%d crafts=%d",
                    len(index.skill_registry.all()),
                    len(index.seed_registry.all()),
                    len(index.template_registry.all()),
                    len(index.design_system_registry.all()),
                    len(index.craft_registry.all()),
                )
            except Exception as e:
                logger.warning("init | asset loading failed: %s", e)

        if self._services.model_resolver is not None:
            try:
                await self._services.model_resolver.load_bundle(self._context)
                model_config = self._services.model_resolver.resolve(ModelRole.PRIMARY)
                state.resolved_model = {
                    "provider": model_config.provider,
                    "modelName": model_config.model_name,
                    "baseUrl": model_config.base_url,
                    "apiKey": model_config.api_key,
                }
                logger.info(
                    "init | model resolved: %s/%s", model_config.provider, model_config.model_name
                )
            except Exception as e:
                logger.warning("init | model resolution failed: %s", e)

        return state
