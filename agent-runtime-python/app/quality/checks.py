import os
import re
from pathlib import Path
from typing import Callable

from app.artifacts.types import ArtifactManifest
from app.quality.result import CheckResult


def check_entry_exists(workspace_root: str, manifest: ArtifactManifest) -> CheckResult:
    entry_path = os.path.join(workspace_root, manifest.entry)
    if os.path.exists(entry_path):
        return CheckResult(
            id="entry_exists",
            status="pass",
            severity="error",
            message=f"Entry file exists: {manifest.entry}",
        )
    return CheckResult(
        id="entry_exists",
        status="fail",
        severity="error",
        message=f"Entry file missing: {manifest.entry}",
        file_path=manifest.entry,
    )


def check_supporting_files_exist(workspace_root: str, manifest: ArtifactManifest) -> CheckResult:
    missing = []
    for f in manifest.supporting_files:
        if not os.path.exists(os.path.join(workspace_root, f)):
            missing.append(f)
    if not missing:
        return CheckResult(
            id="supporting_files_exist",
            status="pass",
            severity="warning",
            message="All supporting files exist",
        )
    return CheckResult(
        id="supporting_files_exist",
        status="warn",
        severity="warning",
        message=f"Missing supporting files: {', '.join(missing)}",
    )


def check_non_empty_files(workspace_root: str, manifest: ArtifactManifest) -> CheckResult:
    empty = []
    all_files = [manifest.entry] + [f for f in manifest.supporting_files if f != manifest.entry]
    seen = set()
    for f in all_files:
        if f in seen:
            continue
        seen.add(f)
        abs_path = os.path.join(workspace_root, f)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                if len(content.strip()) <= 20:
                    empty.append(f)
            except Exception:
                empty.append(f)
    if not empty:
        return CheckResult(
            id="non_empty_files",
            status="pass",
            severity="error",
            message="All files have sufficient content",
        )
    return CheckResult(
        id="non_empty_files",
        status="fail",
        severity="error",
        message=f"Files with insufficient content (<=20 chars): {', '.join(empty)}",
    )


def check_vue_app_structure(workspace_root: str, manifest: ArtifactManifest) -> CheckResult:
    if manifest.artifact_format != "vue_project":
        return CheckResult(
            id="vue_app_structure",
            status="pass",
            severity="error",
            message="Not a Vue project, skipping Vue structure check",
        )

    issues = []
    app_vue = os.path.join(workspace_root, "src", "App.vue")
    package_json = os.path.join(workspace_root, "package.json")
    main_ts = os.path.join(workspace_root, "src", "main.ts")
    main_js = os.path.join(workspace_root, "src", "main.js")

    if not os.path.exists(app_vue):
        issues.append("src/App.vue missing")
    if not os.path.exists(package_json):
        issues.append("package.json missing")
    if not os.path.exists(main_ts) and not os.path.exists(main_js):
        issues.append("src/main.ts or src/main.js missing")

    if os.path.exists(app_vue):
        try:
            with open(app_vue, "r", encoding="utf-8") as fh:
                content = fh.read()
            if "<template>" not in content:
                issues.append("App.vue missing <template>")
        except Exception:
            issues.append("App.vue unreadable")

    if not issues:
        return CheckResult(
            id="vue_app_structure",
            status="pass",
            severity="error",
            message="Vue project structure is valid",
        )
    return CheckResult(
        id="vue_app_structure",
        status="fail",
        severity="error",
        message=f"Vue structure issues: {'; '.join(issues)}",
    )


_PLACEHOLDER_PATTERNS = [
    re.compile(r"Metric\s+A", re.IGNORECASE),
    re.compile(r"Card\s+\d+", re.IGNORECASE),
    re.compile(r"Lorem\s+ipsum", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
]


def check_placeholder_text(workspace_root: str, manifest: ArtifactManifest) -> CheckResult:
    found = []
    all_files = [manifest.entry] + [f for f in manifest.supporting_files if f != manifest.entry]
    seen = set()
    for f in all_files:
        if f in seen:
            continue
        seen.add(f)
        abs_path = os.path.join(workspace_root, f)
        if not os.path.exists(abs_path):
            continue
        try:
            with open(abs_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            for pattern in _PLACEHOLDER_PATTERNS:
                if pattern.search(content):
                    found.append(f"{f}: {pattern.pattern}")
                    break
        except Exception:
            continue
    if not found:
        return CheckResult(
            id="placeholder_text",
            status="pass",
            severity="warning",
            message="No placeholder text detected",
        )
    return CheckResult(
        id="placeholder_text",
        status="warn",
        severity="warning",
        message=f"Placeholder text found: {'; '.join(found)}",
    )


def check_artifact_tags_removed(workspace_root: str, manifest: ArtifactManifest) -> CheckResult:
    found = []
    all_files = [manifest.entry] + [f for f in manifest.supporting_files if f != manifest.entry]
    seen = set()
    for f in all_files:
        if f in seen:
            continue
        seen.add(f)
        abs_path = os.path.join(workspace_root, f)
        if not os.path.exists(abs_path):
            continue
        try:
            with open(abs_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            if "<artifact" in content.lower():
                found.append(f)
        except Exception:
            continue
    if not found:
        return CheckResult(
            id="artifact_tags_removed",
            status="pass",
            severity="warning",
            message="No <artifact> tags found",
        )
    return CheckResult(
        id="artifact_tags_removed",
        status="warn",
        severity="warning",
        message=f"Unreplaced <artifact> tags in: {', '.join(found)}",
    )


AI_DEFAULT_INDIGO = (
    "#6366f1",
    "#4f46e5",
    "#4338ca",
    "#3730a3",
    "#8b5cf6",
    "#7c3aed",
    "#a855f7",
)


def check_ai_default_indigo(workspace_root: Path, file_paths: list[str]) -> CheckResult:
    for file_path in file_paths:
        path = workspace_root / file_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        for color in AI_DEFAULT_INDIGO:
            if color in content:
                return CheckResult(
                    id="ai_default_indigo",
                    status="fail",
                    severity="warning",
                    message=f"Common AI default accent color found: {color}",
                    file_path=file_path,
                )
    return CheckResult(
        id="ai_default_indigo",
        status="pass",
        severity="warning",
        message="No common AI default indigo colors found",
    )


def check_vue_state_coverage(workspace_root: Path, file_paths: list[str]) -> CheckResult:
    keywords = ("loading", "加载", "empty", "暂无", "error", "错误", "失败", "retry", "重试")
    combined = ""
    for file_path in file_paths:
        path = workspace_root / file_path
        if path.is_file() and path.suffix in {".vue", ".ts", ".js"}:
            combined += path.read_text(encoding="utf-8", errors="ignore").lower()
    if all(keyword.lower() not in combined for keyword in keywords):
        return CheckResult(
            id="vue_state_coverage",
            status="warn",
            severity="warning",
            message="No loading, empty, error, or retry state was detected in generated Vue files",
        )
    return CheckResult(
        id="vue_state_coverage",
        status="pass",
        severity="warning",
        message="Vue state coverage keywords detected",
    )


CHECK_REGISTRY: dict[str, Callable] = {
    "entry_exists": check_entry_exists,
    "supporting_files_exist": check_supporting_files_exist,
    "non_empty_files": check_non_empty_files,
    "vue_app_structure": check_vue_app_structure,
    "no_placeholder_text": check_placeholder_text,
    "artifact_tags_removed": check_artifact_tags_removed,
}
