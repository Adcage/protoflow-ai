from pathlib import Path

from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.selector import SkillSelector
from app.capabilities.skills.types import SkillDefinition


def _make_skill(
    id: str,
    name: str,
) -> SkillDefinition:
    return SkillDefinition(
        id=id,
        name=name,
        description=f"{name} skill",
        body=f"# {name}",
        source_path=Path(f"/skills/{id}/SKILL.md"),
    )


class TestSkillSelector:
    def test_select_returns_all_skills_sorted_by_name(self):
        registry = SkillRegistry()
        registry.register(_make_skill("zebra", "Zebra"))
        registry.register(_make_skill("alpha", "Alpha"))
        registry.register(_make_skill("beta", "Beta"))

        selector = SkillSelector()
        result = selector.select("any prompt", registry)

        assert [s.id for s in result] == ["alpha", "beta", "zebra"]

    def test_select_returns_sorted_list(self):
        registry = SkillRegistry()
        registry.register(_make_skill("landing", "Landing"))
        registry.register(_make_skill("dashboard", "Dashboard"))

        selector = SkillSelector()
        result = selector.select("any prompt", registry)

        assert [s.id for s in result] == ["dashboard", "landing"]

    def test_empty_registry_returns_empty_list(self):
        registry = SkillRegistry()
        selector = SkillSelector()
        result = selector.select("any prompt", registry)

        assert result == []
