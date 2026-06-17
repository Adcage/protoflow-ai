import logging
import os

from app.artifacts.manifest import ArtifactCollector
from app.capabilities.common.loader_result import SelectedCapabilities
from app.nodes.base import NodeMetadata, RuntimeNode
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.state import ExecutionState
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.nodes.collect_artifacts")


class CollectArtifactsNode(RuntimeNode):
    metadata = NodeMetadata(
        id="collect_artifacts",
        name="收集产物",
        description="收集生成的文件并生成 Artifact Manifest",
    )

    async def run(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
    ) -> ExecutionState:
        code_gen_type = context.code_gen_type.value
        workspace_root = context.workspace_path

        skill_preview_entry = ""
        seed_entry = ""
        source_skill_id = state.selected_skill_id
        source_skill_ids: list[str] = []
        seed_entry = ""
        source_skill_id = state.selected_skill_id
        source_seed_id = state.selected_seed_id
        source_template_id = state.selected_template_id
        source_template_ids: list[str] = []
        design_system_id = state.selected_design_system_id
        craft_ids = list(state.selected_craft_ids)
        selection_source = state.selection_source
        project_mode = code_gen_type

        if state.selected_capabilities is not None:
            cap: SelectedCapabilities = state.selected_capabilities
            if cap.seed is not None:
                seed_entry = cap.seed.entry

        if state.capability_selection is not None:
            selection = state.capability_selection
            source_skill_ids = list(selection.skill_ids)
            source_template_ids = list(selection.template_ids)
            project_mode = selection.project_mode or code_gen_type
            selection_source = selection_source or selection.selection_source

        collector = ArtifactCollector()
        manifest = collector.build_manifest(
            code_gen_type=code_gen_type,
            files_touched=list(state.files_touched),
            title=context.prompt[:80] if context.prompt else code_gen_type,
            skill_preview_entry=skill_preview_entry,
            seed_entry=seed_entry,
            source_skill_id=source_skill_id,
            source_skill_ids=source_skill_ids,
            source_seed_id=source_seed_id,
            source_template_id=source_template_id,
            source_template_ids=source_template_ids,
            design_system_id=design_system_id,
            craft_ids=craft_ids,
            selection_source=selection_source,
            project_mode=project_mode,
            metadata={
                "agentRunId": context.agent_run_id,
                "appId": context.app_id,
            },
            workspace_root=workspace_root,
        )

        artifact_writer = services.artifact_writer
        if artifact_writer is not None:
            manifest_path = artifact_writer.write(workspace_root, manifest)
            state.artifact_manifest_path = manifest_path
        else:
            acai_dir = os.path.join(workspace_root, ".acai")
            os.makedirs(acai_dir, exist_ok=True)
            state.artifact_manifest_path = os.path.join(acai_dir, "artifact-manifest.json")

        state.artifacts = [
            {
                "entry": manifest.entry,
                "kind": manifest.kind,
                "supporting_files": manifest.supporting_files,
                "status": manifest.status,
            }
        ]

        logger.info(
            "collect_artifacts done | entry=%s files=%d manifest=%s",
            manifest.entry,
            len(manifest.supporting_files),
            state.artifact_manifest_path,
        )

        await services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.NODE_COMPLETED, {"node_id": "collect_artifacts"})
        )

        return state
