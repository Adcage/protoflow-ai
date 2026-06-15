import logging
from pathlib import Path

from app.capabilities.templates.types import TemplateDefinition
from app.prompts.modules import PromptModule

logger = logging.getLogger("app.capabilities.templates.prompt_module")

DEFAULT_FILE_MAX_CHARS = 4000
DEFAULT_REFERENCE_MAX_CHARS = 3000
DEFAULT_CHECKLIST_MAX_CHARS = 3000


class TemplateReferenceModule(PromptModule):
    id = "template_reference"

    def __init__(
        self,
        file_max_chars: int = DEFAULT_FILE_MAX_CHARS,
        reference_max_chars: int = DEFAULT_REFERENCE_MAX_CHARS,
        checklist_max_chars: int = DEFAULT_CHECKLIST_MAX_CHARS,
    ) -> None:
        self._file_max_chars = file_max_chars
        self._reference_max_chars = reference_max_chars
        self._checklist_max_chars = checklist_max_chars

    def enabled(self, context: object, state: object) -> bool:
        caps = getattr(state, "selected_capabilities", None)
        if caps is None:
            return False
        return getattr(caps, "template", None) is not None

    def render(self, context: object, state: object) -> str:
        caps = getattr(state, "selected_capabilities", None)
        if caps is None:
            return ""
        template: TemplateDefinition | None = getattr(caps, "template", None)
        if template is None:
            return ""

        sections: list[str] = []
        sections.append(f"## Reference Template: {template.name}")
        sections.append("")
        sections.append(
            "Use this as a structure reference. Adapt content, labels, states, and styling to the user's request and the active design system."
        )

        self._append_intent(sections, template)
        self._append_reference_files(
            sections, template, "Layout References", template.references, self._reference_max_chars
        )
        self._append_reference_files(
            sections, template, "Checklists", template.checklists, self._checklist_max_chars
        )
        self._append_code_files(sections, template)

        return "\n".join(sections)

    def _append_intent(self, sections: list[str], template: TemplateDefinition) -> None:
        sections.append("")
        sections.append("### Template Intent")
        sections.append(f"- ID: `{template.id}`")
        if template.kind:
            sections.append(f"- Kind: `{template.kind}`")
        sections.append(f"- Description: {template.description or 'No description provided.'}")
        if template.entry:
            sections.append(f"- Entry file: `{template.entry}`")

    def _append_reference_files(
        self,
        sections: list[str],
        template: TemplateDefinition,
        heading: str,
        file_paths: tuple[Path, ...],
        max_chars: int,
    ) -> None:
        if not file_paths:
            return

        sections.append("")
        sections.append(f"### {heading}")

        for file_path in file_paths:
            resolved = template.source_path.parent / file_path
            content = self._read_file(resolved)
            if not content:
                continue

            if len(content) > max_chars:
                content = content[:max_chars] + "\n... [truncated]"

            sections.append("")
            sections.append(f"**{file_path}**")
            sections.append("```")
            sections.append(content)
            sections.append("```")

    def _append_code_files(self, sections: list[str], template: TemplateDefinition) -> None:
        files_to_inject = template.files[: template.max_prompt_files]
        if not files_to_inject:
            return

        sections.append("")
        sections.append("### Reference Files")

        for file_path in files_to_inject:
            resolved = template.source_path.parent / file_path
            content = self._read_file(resolved)
            if not content:
                continue

            if len(content) > self._file_max_chars:
                content = content[: self._file_max_chars] + "\n... [truncated]"

            sections.append("")
            sections.append(f"**{file_path}**")
            sections.append("```")
            sections.append(content)
            sections.append("```")

    def _read_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to read template file %s: %s", path, e)
            return ""
