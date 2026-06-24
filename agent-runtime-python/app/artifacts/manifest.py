import json
import logging
import os
from pathlib import Path
from typing import Any

from app.artifacts.types import ArtifactManifest

logger = logging.getLogger("app.artifacts.manifest")

_V1_CODE_GEN_TYPE_MAP: dict[str, tuple[str, str]] = {
    "single_file": ("application", "web_single_file"),
    "multi-file": ("application", "web_multi_file"),
    "vue_project": ("application", "vue_project"),
}


class ArtifactCollector:
    def __init__(self) -> None:
        self._artifacts: list[ArtifactManifest] = []

    def add(self, artifact: ArtifactManifest) -> None:
        self._artifacts.append(artifact)

    def artifacts(self) -> list[ArtifactManifest]:
        return list(self._artifacts)

    @staticmethod
    def infer_entry(
        artifact_format: str,
        files_touched: list[str],
        skill_preview_entry: str = "",
        seed_entry: str = "",
        workspace_root: str = "",
    ) -> str:
        if skill_preview_entry:
            return skill_preview_entry
        if seed_entry:
            return seed_entry
        if artifact_format == "vue_project":
            for f in ("src/App.vue", "index.html"):
                if workspace_root:
                    abs_path = Path(workspace_root) / f
                    if abs_path.exists():
                        return f
                elif f in files_touched:
                    return f
            return "src/App.vue"
        if artifact_format == "web_single_file":
            return "index.html"
        if artifact_format == "web_multi_file":
            return "index.html"
        return "index.html"

    def build_manifest(
        self,
        generation_mode: str = "application",
        artifact_format: str = "",
        code_gen_type: str = "",
        files_touched: list[str] | None = None,
        title: str = "",
        skill_preview_entry: str = "",
        seed_entry: str = "",
        source_skill_id: str = "",
        source_skill_ids: list[str] | None = None,
        source_seed_id: str = "",
        source_template_id: str = "",
        source_template_ids: list[str] | None = None,
        design_system_id: str = "",
        craft_ids: list[str] | None = None,
        selection_source: str = "",
        project_mode: str = "",
        metadata: dict[str, Any] | None = None,
        workspace_root: str = "",
    ) -> ArtifactManifest:
        if files_touched is None:
            files_touched = []

        effective_format = artifact_format
        if not effective_format and code_gen_type:
            mapped = _V1_CODE_GEN_TYPE_MAP.get(code_gen_type)
            if mapped:
                effective_format = mapped[1]

        entry = self.infer_entry(
            artifact_format=effective_format,
            files_touched=files_touched,
            skill_preview_entry=skill_preview_entry,
            seed_entry=seed_entry,
            workspace_root=workspace_root,
        )
        manifest = ArtifactManifest(
            version=2,
            kind=effective_format or generation_mode,
            title=title or effective_format or generation_mode,
            entry=entry,
            generation_mode=generation_mode,
            artifact_format=effective_format,
            code_gen_type="",
            supporting_files=list(files_touched),
            source_skill_id=source_skill_id,
            source_skill_ids=source_skill_ids or [],
            source_seed_id=source_seed_id,
            source_template_id=source_template_id,
            source_template_ids=source_template_ids or [],
            design_system_id=design_system_id,
            craft_ids=craft_ids or [],
            selection_source=selection_source,
            project_mode=project_mode,
            metadata=metadata or {},
        )
        self.add(manifest)
        return manifest

    @classmethod
    def read_v1_manifest(cls, workspace_root: str) -> ArtifactManifest | None:
        manifest_path = os.path.join(workspace_root, ".acai", "artifact-manifest.json")
        if not os.path.exists(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("read_v1_manifest | failed to read %s", manifest_path)
            return None

        version = data.get("version", 1)
        if version >= 2:
            return None

        old_code_gen_type = data.get("codeGenType", data.get("code_gen_type", ""))
        mapped = _V1_CODE_GEN_TYPE_MAP.get(old_code_gen_type)
        if mapped is None:
            logger.warning(
                "read_v1_manifest | unknown code_gen_type=%s, cannot map to v2",
                old_code_gen_type,
            )
            return None

        generation_mode, artifact_format = mapped
        return ArtifactManifest(
            version=2,
            kind=data.get("kind", artifact_format),
            title=data.get("title", ""),
            entry=data.get("entry", ""),
            generation_mode=generation_mode,
            artifact_format=artifact_format,
            code_gen_type=old_code_gen_type,
            supporting_files=data.get("supportingFiles", data.get("supporting_files", [])),
            status=data.get("status", "complete"),
            source_skill_id=data.get("sourceSkillId", data.get("source_skill_id", "")),
            source_skill_ids=data.get("sourceSkillIds", data.get("source_skill_ids", [])),
            source_seed_id=data.get("sourceSeedId", data.get("source_seed_id", "")),
            source_template_id=data.get("sourceTemplateId", data.get("source_template_id", "")),
            source_template_ids=data.get("sourceTemplateIds", data.get("source_template_ids", [])),
            design_system_id=data.get("designSystemId", data.get("design_system_id", "")),
            craft_ids=data.get("craftIds", data.get("craft_ids", [])),
            selection_source=data.get("selectionSource", data.get("selection_source", "")),
            project_mode=data.get("projectMode", data.get("project_mode", "")),
            checks=[],
            metadata=data.get("metadata", {}),
        )
