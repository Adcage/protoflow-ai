import logging
from pathlib import Path
from typing import Any

from app.capabilities.common.asset_index import AssetIndex
from app.capabilities.common.capability_selection import CapabilitySelection
from app.capabilities.common.loader_result import SelectedCapabilities
from app.capabilities.craft.selector import CraftSelector
from app.capabilities.design_systems.selector import DesignSystemSelector
from app.capabilities.seeds.applier import SeedApplier
from app.capabilities.seeds.selector import SeedSelector
from app.capabilities.skills.selector import SkillSelector
from app.capabilities.templates.selector import TemplateSelector
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.nodes.base import NodeMetadata, RuntimeNode
from app.runtime.context import ExecutionContext, RunMode
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.state import ExecutionState
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.nodes.select_capabilities")


class SelectCapabilitiesNode(RuntimeNode):
    metadata = NodeMetadata(
        id="select_capabilities",
        name="选择能力",
        description="根据规划结果或提示词选择技能、种子、模板、设计系统和工艺规则",
    )

    def __init__(self) -> None:
        self._skill_selector = SkillSelector()
        self._design_system_selector = DesignSystemSelector()
        self._seed_selector = SeedSelector()
        self._seed_applier = SeedApplier()
        self._template_selector = TemplateSelector()
        self._craft_selector = CraftSelector()

    async def run(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
    ) -> ExecutionState:
        asset_manager = services.asset_manager
        if asset_manager is None:
            raise AgentRuntimeError(
                "AssetManager 未注入 RuntimeServices",
                code=AgentErrorCode.STATE_ERROR,
            )

        index: AssetIndex = asset_manager.get_index()
        prompt = context.prompt
        code_gen_type = context.code_gen_type.value
        run_mode = context.run_mode.value

        if state.capability_selection is not None and state.capability_selection.selection_source in (
            "planner", "manual", "fallback"
        ):
            return await self._resolve_from_plan(context, state, services, index)

        return await self._select_locally(context, state, services, index, prompt, code_gen_type, run_mode)

    async def _select_locally(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
        index: AssetIndex,
        prompt: str,
        code_gen_type: str,
        run_mode: str,
    ) -> ExecutionState:
        default_config = index.manifest.defaults.get(code_gen_type, {})

        skills = self._skill_selector.select(prompt, index.skill_registry)
        skill = skills[0] if skills else None
        logger.info("skill selected | count=%d first_id=%s", len(skills), skill.id if skill else "none")

        design_system = self._design_system_selector.select(
            prompt,
            code_gen_type,
            index.design_system_registry,
            default_design_system_id=str(default_config.get("designSystem", "")),
        )
        logger.info("design_system selected | id=%s", design_system.id if design_system else "none")

        seed = self._seed_selector.select(
            code_gen_type,
            run_mode,
            index.seed_registry,
            default_seed_id=str(default_config.get("seed", "")),
        )
        logger.info("seed selected | id=%s", seed.id if seed else "none")

        if seed is not None:
            workspace_path = Path(context.workspace_path)
            try:
                self._seed_applier.apply(seed, workspace_path)
            except Exception as e:
                if context.run_mode == RunMode.GENERATE:
                    raise AgentRuntimeError(
                        f"Seed 文件复制失败 (generate 模式关键错误): {e}",
                        code=AgentErrorCode.STATE_ERROR,
                    )
                logger.warning("seed apply failed (non-generate mode, continuing): %s", e)

        template = self._template_selector.select(
            code_gen_type,
            index.template_registry,
            default_template_id=str(default_config.get("template", "")),
        )
        logger.info("template selected | id=%s", template.id if template else "none")

        default_craft_config = default_config.get("craft")
        default_craft_ids: tuple[str, ...] | None = (
            tuple(str(c) for c in default_craft_config)
            if isinstance(default_craft_config, list)
            else None
        )

        craft = self._craft_selector.select(
            code_gen_type,
            index.craft_registry,
            default_craft_ids=default_craft_ids,
        )
        logger.info("craft selected | count=%d ids=%s", len(craft), [c.id for c in craft])

        selection = CapabilitySelection(
            skill_ids=tuple(s.id for s in skills),
            seed_id=seed.id if seed else "",
            template_ids=(template.id,) if template else (),
            design_system_id=design_system.id if design_system else "",
            craft_ids=tuple(c.id for c in craft),
            project_mode=code_gen_type,
            selection_source="selector",
        )
        selected_capabilities = SelectedCapabilities(
            selection=selection,
            skills=list(skills),
            seed=seed,
            templates=[template] if template else [],
            design_system=design_system,
            craft=list(craft),
        )

        self._write_state(state, selection, selected_capabilities, skill, seed, template, design_system, craft)

        await services.event_bus.emit(
            RuntimeEvent(
                RuntimeEventType.CAPABILITY_SELECTED,
                {
                    "selection_source": selection.selection_source,
                    "skill_ids": list(selection.skill_ids),
                    "seed_id": selection.seed_id,
                    "template_ids": list(selection.template_ids),
                    "design_system_id": selection.design_system_id,
                    "craft_ids": list(selection.craft_ids),
                    "project_mode": selection.project_mode,
                    "reason": selection.reason,
                },
            )
        )
        await services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.NODE_COMPLETED, {"node_id": "select_capabilities"})
        )

        return state

    async def _resolve_from_plan(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
        index: AssetIndex,
    ) -> ExecutionState:
        selection = state.capability_selection
        selected_capabilities = self._resolve_selection(selection, index)

        if selected_capabilities.seed is not None:
            workspace_path = Path(context.workspace_path)
            try:
                self._seed_applier.apply(selected_capabilities.seed, workspace_path)
            except Exception as e:
                if context.run_mode == RunMode.GENERATE:
                    raise AgentRuntimeError(
                        f"Seed 文件复制失败 (generate 模式关键错误): {e}",
                        code=AgentErrorCode.STATE_ERROR,
                    )
                logger.warning("seed apply failed (non-generate mode, continuing): %s", e)

        self._write_state(
            state, selection, selected_capabilities,
            selected_capabilities.skill, selected_capabilities.seed,
            selected_capabilities.template, selected_capabilities.design_system,
            selected_capabilities.craft,
        )

        await services.event_bus.emit(
            RuntimeEvent(
                RuntimeEventType.CAPABILITY_SELECTED,
                {
                    "selection_source": selection.selection_source,
                    "skill_ids": list(selection.skill_ids),
                    "seed_id": selection.seed_id,
                    "template_ids": list(selection.template_ids),
                    "design_system_id": selection.design_system_id,
                    "craft_ids": list(selection.craft_ids),
                    "project_mode": selection.project_mode,
                    "reason": selection.reason,
                },
            )
        )
        await services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.NODE_COMPLETED, {"node_id": "select_capabilities"})
        )

        return state

    def _resolve_selection(self, selection: CapabilitySelection, index: AssetIndex) -> SelectedCapabilities:
        skills = []
        for skill_id in selection.skill_ids:
            try:
                skills.append(index.skill_registry.get(skill_id))
            except KeyError:
                logger.warning("selected skill missing: %s", skill_id)

        templates = []
        for template_id in selection.template_ids:
            try:
                templates.append(index.template_registry.get(template_id))
            except KeyError:
                logger.warning("selected template missing: %s", template_id)

        seed = None
        if selection.seed_id:
            try:
                seed = index.seed_registry.get(selection.seed_id)
            except KeyError:
                logger.warning("selected seed missing: %s", selection.seed_id)

        design_system = None
        if selection.design_system_id:
            try:
                design_system = index.design_system_registry.get(selection.design_system_id)
            except KeyError:
                logger.warning("selected design_system missing: %s", selection.design_system_id)

        craft = []
        for craft_id in selection.craft_ids:
            try:
                craft.append(index.craft_registry.get(craft_id))
            except KeyError:
                logger.warning("selected craft missing: %s", craft_id)

        return SelectedCapabilities(
            selection=selection,
            skills=skills,
            seed=seed,
            templates=templates,
            design_system=design_system,
            craft=craft,
        )

    def _write_state(
        self,
        state: ExecutionState,
        selection: CapabilitySelection,
        selected_capabilities: SelectedCapabilities,
        skill: Any,
        seed: Any,
        template: Any,
        design_system: Any,
        craft: list[Any],
    ) -> None:
        state.selected_capabilities = selected_capabilities
        state.selected_skill_id = skill.id if skill else ""
        state.selected_seed_id = seed.id if seed else ""
        state.selected_template_id = template.id if template else ""
        state.selected_design_system_id = design_system.id if design_system else ""
        state.selected_craft_ids = [c.id for c in craft]
        state.capability_selection = selection
        state.selection_source = selection.selection_source
