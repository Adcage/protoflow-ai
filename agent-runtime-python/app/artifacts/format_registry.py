from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


class ArtifactFormatHandler(BaseModel):
    format_id: str
    entry_inference: Callable
    checks: list[str]

    model_config = {"arbitrary_types_allowed": True}


class ArtifactFormatRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ArtifactFormatHandler] = {}

    def register(self, handler: ArtifactFormatHandler) -> None:
        if handler.format_id in self._handlers:
            raise ValueError(f"format handler already registered: {handler.format_id}")
        self._handlers[handler.format_id] = handler

    def get(self, format_id: str) -> ArtifactFormatHandler | None:
        return self._handlers.get(format_id)

    def require(self, format_id: str) -> ArtifactFormatHandler:
        handler = self._handlers.get(format_id)
        if handler is None:
            raise AgentRuntimeError(
                f"unknown artifact format: {format_id}",
                code=AgentErrorCode.STATE_ERROR,
            )
        return handler

    def format_ids(self) -> frozenset[str]:
        return frozenset(self._handlers.keys())


def _infer_web_single_file_entry(
    files_touched: list[str],
    workspace_root: str = "",
) -> str:
    return "index.html"


def _infer_web_multi_file_entry(
    files_touched: list[str],
    workspace_root: str = "",
) -> str:
    if workspace_root:
        for f in ("index.html",):
            if (Path(workspace_root) / f).exists():
                return f
    return "index.html"


def _infer_vue_project_entry(
    files_touched: list[str],
    workspace_root: str = "",
) -> str:
    if workspace_root:
        for f in ("src/App.vue", "index.html"):
            if (Path(workspace_root) / f).exists():
                return f
    elif "src/App.vue" in files_touched:
        return "src/App.vue"
    return "src/App.vue"


def create_application_format_registry() -> ArtifactFormatRegistry:
    registry = ArtifactFormatRegistry()

    registry.register(
        ArtifactFormatHandler(
            format_id="web_single_file",
            entry_inference=_infer_web_single_file_entry,
            checks=["entry_exists", "non_empty_files", "no_placeholder_text"],
        )
    )
    registry.register(
        ArtifactFormatHandler(
            format_id="web_multi_file",
            entry_inference=_infer_web_multi_file_entry,
            checks=["entry_exists", "supporting_files_exist", "non_empty_files", "no_placeholder_text"],
        )
    )
    registry.register(
        ArtifactFormatHandler(
            format_id="vue_project",
            entry_inference=_infer_vue_project_entry,
            checks=[
                "entry_exists",
                "supporting_files_exist",
                "non_empty_files",
                "vue_app_structure",
                "no_placeholder_text",
            ],
        )
    )

    return registry
