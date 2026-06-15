import logging
from typing import Any

from app.prompts.modules import PromptModule

logger = logging.getLogger("app.capabilities.seeds.prompt_module")


class SeedModule(PromptModule):
    id = "seed"

    def enabled(self, context: Any, state: Any) -> bool:
        selected = getattr(state, "selected_capabilities", None)
        if selected is None:
            return False
        seed = getattr(selected, "seed", None)
        return seed is not None

    def render(self, context: Any, state: Any) -> str:
        selected = getattr(state, "selected_capabilities", None)
        if selected is None:
            return ""
        seed = getattr(selected, "seed", None)
        if seed is None:
            return ""

        lines = [
            "## Seed",
            "",
            f"The workspace has been initialized from seed `{seed.id}`.",
            "Preserve the existing project structure unless the user explicitly asks to replace it.",
        ]
        if seed.entry:
            lines.append(f"Entry file: {seed.entry}")

        lines.extend(
            [
                "",
                "### Seed Constraints",
                "",
                "- The seed has already initialized the workspace.",
                "- Keep package.json, src/main.ts and src/App.vue consistent.",
                "- Add components only when they reduce complexity or match the selected template.",
                "- Remove visible placeholder content introduced by the seed before finalizing.",
            ]
        )

        return "\n".join(lines)
