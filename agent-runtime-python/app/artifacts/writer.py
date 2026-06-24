import json
import logging
import os

from app.artifacts.types import ArtifactCheckResult, ArtifactManifest

logger = logging.getLogger("app.artifacts.writer")

_V2_CAMEL_MAP: dict[str, str] = {
    "generation_mode": "generationMode",
    "artifact_format": "artifactFormat",
    "supporting_files": "supportingFiles",
    "source_skill_id": "sourceSkillId",
    "source_skill_ids": "sourceSkillIds",
    "source_seed_id": "sourceSeedId",
    "source_template_id": "sourceTemplateId",
    "source_template_ids": "sourceTemplateIds",
    "design_system_id": "designSystemId",
    "craft_ids": "craftIds",
    "selection_source": "selectionSource",
    "project_mode": "projectMode",
}

_V2_EXCLUDED_FIELDS: frozenset[str] = frozenset({"code_gen_type"})

_V1_CODE_GEN_TYPE_MAP: dict[str, tuple[str, str]] = {
    "single_file": ("application", "web_single_file"),
    "multi-file": ("application", "web_multi_file"),
    "vue_project": ("application", "vue_project"),
}


def _to_camel(key: str) -> str:
    return _V2_CAMEL_MAP.get(key, key)


def _manifest_to_dict(manifest: ArtifactManifest) -> dict:
    result = {}
    for f in manifest.__dataclass_fields__:
        if f in _V2_EXCLUDED_FIELDS:
            continue
        val = getattr(manifest, f)
        camel_key = _to_camel(f)
        if f == "checks":
            result[camel_key] = [_check_to_dict(c) for c in val]
        else:
            result[camel_key] = val
    return result


def _check_to_dict(check: ArtifactCheckResult) -> dict:
    return {
        "id": check.id,
        "status": check.status,
        "message": check.message,
        "severity": check.severity,
    }


class ArtifactWriter:
    def write(self, workspace_root: str, manifest: ArtifactManifest) -> str:
        acai_dir = os.path.join(workspace_root, ".acai")
        os.makedirs(acai_dir, exist_ok=True)
        manifest_path = os.path.join(acai_dir, "artifact-manifest.json")
        data = _manifest_to_dict(manifest)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("artifact manifest written | path=%s", manifest_path)
        return manifest_path

    @staticmethod
    def read(workspace_root: str) -> ArtifactManifest | None:
        manifest_path = os.path.join(workspace_root, ".acai", "artifact-manifest.json")
        if not os.path.exists(manifest_path):
            return None
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _dict_to_manifest(data)


def _dict_to_manifest(data: dict) -> ArtifactManifest:
    version = data.get("version", 1)
    checks = []
    for c in data.get("checks", []):
        checks.append(
            ArtifactCheckResult(
                id=c.get("id", ""),
                status=c.get("status", ""),
                message=c.get("message", ""),
                severity=c.get("severity", ""),
            )
        )

    generation_mode = data.get("generationMode", data.get("generation_mode", ""))
    artifact_format = data.get("artifactFormat", data.get("artifact_format", ""))
    code_gen_type = data.get("codeGenType", data.get("code_gen_type", ""))

    if version < 2 and code_gen_type and not artifact_format:
        mapped = _V1_CODE_GEN_TYPE_MAP.get(code_gen_type)
        if mapped:
            generation_mode = generation_mode or mapped[0]
            artifact_format = mapped[1]

    return ArtifactManifest(
        version=max(version, 2),
        kind=data.get("kind", ""),
        title=data.get("title", ""),
        entry=data.get("entry", ""),
        generation_mode=generation_mode or "application",
        artifact_format=artifact_format,
        code_gen_type=code_gen_type,
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
        checks=checks,
        metadata=data.get("metadata", {}),
    )
