import logging
from typing import Any

from app.capabilities.skills.types import SkillDefinition
from app.prompts.modules import PromptModule

logger = logging.getLogger("app.capabilities.skills.prompt_module")


class SelectedSkillModule(PromptModule):
    id = "selected_skill"

    def enabled(self, context: Any, state: Any) -> bool:
        caps = getattr(state, "selected_capabilities", None)
        if caps is None:
            return False
        return getattr(caps, "skill", None) is not None

    def _adapt_body(self, body: str) -> str:
        replacements = {
            "Emit between <artifact> tags": "Use file tools to write real project files",
            "single, self-contained HTML": "project files",
            "one self-contained HTML document": "real project files using write_file",
            "<artifact>": "workspace files",
            "</artifact>": "",
        }
        adapted = body
        for source, target in replacements.items():
            adapted = adapted.replace(source, target)
        return adapted

    def _render_output_contract(self, skill: SkillDefinition) -> str:
        contract_lines: list[str] = [
            "### Project Output Contract",
            "- Use file tools (write_file) to write real project files under the workspace.",
            "- Do not wrap output in artifact tags.",
            "- Generate complete, production-quality code with real business content.",
            "- Include loading, empty, error, and normal states for data-dependent views.",
        ]
        if skill.output_contract:
            contract_lines.append(f"- Expected output contract: {skill.output_contract}")
        return "\n".join(contract_lines)

    def render(self, context: Any, state: Any) -> str:
        caps = getattr(state, "selected_capabilities", None)
        if caps is None:
            return ""
        skill: SkillDefinition | None = getattr(caps, "skill", None)
        if skill is None:
            return ""

        sections: list[str] = []
        sections.append(f"## Selected Skill: {skill.name}")
        sections.append("")
        sections.append("Use this workflow for the current generation.")
        sections.append("")
        sections.append(self._adapt_body(skill.body.strip()))
        sections.append("")
        sections.append(self._render_output_contract(skill))

        if skill.preview is not None:
            sections.append("")
            sections.append("Preview target:")
            sections.append(f"- type: {skill.preview.type}")
            sections.append(f"- entry: {skill.preview.entry}")

        return "\n".join(sections)
