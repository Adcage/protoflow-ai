import logging
from pathlib import Path
from typing import Callable

from app.artifacts.format_registry import ArtifactFormatRegistry, create_application_format_registry
from app.artifacts.types import ArtifactManifest
from app.quality.checks import (
    check_ai_default_indigo,
    check_entry_exists,
    check_non_empty_files,
    check_placeholder_text,
    check_supporting_files_exist,
    check_vue_app_structure,
    check_vue_state_coverage,
)
from app.quality.result import CheckResult

logger = logging.getLogger("app.quality.structure_checker")

_LEGACY_CODE_GEN_TYPE_MAP: dict[str, str] = {
    "single_file": "web_single_file",
    "multi-file": "web_multi_file",
    "vue_project": "vue_project",
}

_ALWAYS_RUN_CHECKS: list[str] = ["artifact_tags_removed"]

_CHECK_FN_MAP: dict[str, Callable] = {
    "entry_exists": check_entry_exists,
    "supporting_files_exist": check_supporting_files_exist,
    "non_empty_files": check_non_empty_files,
    "vue_app_structure": check_vue_app_structure,
    "no_placeholder_text": check_placeholder_text,
}


class StructureChecker:
    def __init__(self, format_registry: ArtifactFormatRegistry | None = None) -> None:
        self._format_registry = format_registry or create_application_format_registry()

    def run(self, workspace_root: str, manifest: ArtifactManifest) -> list[CheckResult]:
        results: list[CheckResult] = []

        format_id = manifest.artifact_format
        if not format_id and manifest.code_gen_type:
            format_id = _LEGACY_CODE_GEN_TYPE_MAP.get(manifest.code_gen_type)
        handler = self._format_registry.get(format_id) if format_id else None

        check_ids: list[str] = []
        if handler is not None:
            check_ids = list(handler.checks)
        check_ids.extend(_ALWAYS_RUN_CHECKS)

        for check_id in check_ids:
            check_fn = _CHECK_FN_MAP.get(check_id)
            if check_fn is not None:
                try:
                    result = check_fn(workspace_root, manifest)
                    results.append(result)
                except Exception as e:
                    logger.error("check failed | id=%s error=%s", check_id, e, exc_info=True)
                    results.append(
                        CheckResult(
                            id=check_id,
                            status="fail",
                            severity="error",
                            message=f"Check raised exception: {e}",
                        )
                    )

        has_vue = format_id == "vue_project" or any(
            f.endswith(".vue") for f in ([manifest.entry] + manifest.supporting_files)
        )
        if has_vue:
            file_paths = [manifest.entry] + [
                f for f in manifest.supporting_files if f != manifest.entry
            ]
            try:
                results.append(check_ai_default_indigo(Path(workspace_root), file_paths))
            except Exception as e:
                logger.error("check failed | id=check_ai_default_indigo error=%s", e, exc_info=True)
                results.append(
                    CheckResult(
                        id="check_ai_default_indigo",
                        status="fail",
                        severity="error",
                        message=f"Check raised exception: {e}",
                    )
                )

            if format_id == "vue_project":
                try:
                    results.append(check_vue_state_coverage(Path(workspace_root), file_paths))
                except Exception as e:
                    logger.error(
                        "check failed | id=check_vue_state_coverage error=%s", e, exc_info=True
                    )
                    results.append(
                        CheckResult(
                            id="check_vue_state_coverage",
                            status="fail",
                            severity="error",
                            message=f"Check raised exception: {e}",
                        )
                    )

        return results

    @staticmethod
    def determine_manifest_status(results: list[CheckResult]) -> str:
        has_error_fail = False
        has_warning = False
        for r in results:
            if r.status == "fail" and r.severity == "error":
                has_error_fail = True
            elif r.status in ("warn", "fail") and r.severity == "warning":
                has_warning = True
        if has_error_fail:
            return "failed"
        if has_warning:
            return "complete_with_warnings"
        return "complete"
