from pathlib import Path

from app.capabilities.common.capability_selection import CapabilitySelection
from app.capabilities.common.loader_result import SelectedCapabilities
from app.capabilities.skills.prompt_module import SelectedSkillModule
from app.capabilities.skills.types import SkillDefinition


def _make_state(skill: SkillDefinition | None):
    selection = CapabilitySelection(skill_ids=(skill.id,) if skill else ())
    selected = SelectedCapabilities(
        selection=selection,
        skills=[skill] if skill else [],
    )
    state = type("State", (), {})()
    state.selected_capabilities = selected
    return state


def test_skill_prompt_renders_skill_name_and_body():
    skill = SkillDefinition(
        id="dashboard",
        name="dashboard",
        description="Dashboard screen.",
        body="Build a real dashboard with complete functionality.",
        source_path=Path("SKILL.md"),
    )

    rendered = SelectedSkillModule().render(context=None, state=_make_state(skill))

    assert "## Selected Skill: dashboard" in rendered
    assert "Build a real dashboard with complete functionality." in rendered


def test_skill_prompt_enabled_only_when_skill_present():
    module = SelectedSkillModule()

    skill = SkillDefinition(
        id="dashboard",
        name="dashboard",
        description="Dashboard screen.",
        body="Build a dashboard.",
        source_path=Path("SKILL.md"),
    )

    assert module.enabled(context=None, state=_make_state(skill)) is True
    assert module.enabled(context=None, state=_make_state(None)) is False


def test_skill_prompt_returns_empty_when_no_selected_capabilities():
    state = type("State", (), {})()
    state.selected_capabilities = None

    rendered = SelectedSkillModule().render(context=None, state=state)

    assert rendered == ""


def test_skill_prompt_renders_resource_list():
    skill = SkillDefinition(
        id="web-prototype",
        name="web-prototype",
        description="Web prototype skill.",
        body="Build a real web page.",
        source_path=Path("/skills/web-prototype/SKILL.md"),
        references=("references/layouts.md", "references/checklist.md"),
    )

    rendered = SelectedSkillModule().render(context=None, state=_make_state(skill))

    assert "## Skill 可用资源" in rendered
    assert 'read_file(path, scope="skill")' in rendered
    assert "references/layouts.md" in rendered
    assert "references/checklist.md" in rendered


def test_skill_prompt_no_resource_section_when_empty_references():
    skill = SkillDefinition(
        id="dashboard",
        name="dashboard",
        description="Dashboard screen.",
        body="Build a dashboard.",
        source_path=Path("/skills/dashboard/SKILL.md"),
        references=(),
    )

    rendered = SelectedSkillModule().render(context=None, state=_make_state(skill))

    assert "## Skill 可用资源" not in rendered
