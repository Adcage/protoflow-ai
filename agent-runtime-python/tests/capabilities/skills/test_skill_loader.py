from pathlib import Path

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.skills.loader import SkillLoader
from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.types import SkillDefinition


DASHBOARD_SKILL_MD = """\
---
name: dashboard
description: Dashboard screen.
---

# Dashboard Skill

Build a dashboard with real data and complete functionality.
"""


class TestSkillLoader:
    def test_load_dashboard_skill(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "dashboard"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(DASHBOARD_SKILL_MD, encoding="utf-8")

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SkillLoader()
        registry = loader.load(config)

        skill = registry.get("dashboard")
        assert isinstance(skill, SkillDefinition)
        assert skill.name == "dashboard"
        assert skill.description == "Dashboard screen."
        assert "Build a dashboard" in skill.body

    def test_load_skips_skill_without_name(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "broken"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\ndescription: no name\n---\nBody", encoding="utf-8")

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SkillLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_load_skips_directory_without_skill_md(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "empty"
        skill_dir.mkdir(parents=True)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SkillLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_load_no_skills_dir(self, tmp_path: Path):
        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SkillLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_duplicate_id_across_roots_skips_lower_priority(self, tmp_path: Path):
        root_project = tmp_path / "project"
        root_bundled = tmp_path / "bundled"
        for root in (root_project, root_bundled):
            skill_dir = root / "skills" / "dashboard"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(DASHBOARD_SKILL_MD, encoding="utf-8")

        config = AssetPathConfig(bundled_root=root_bundled, project_root=root_project)
        loader = SkillLoader()
        registry = loader.load(config)

        skill = registry.get("dashboard")
        assert skill.name == "dashboard"
        assert len(registry.all()) == 1

    def test_higher_priority_root_overrides(self, tmp_path: Path):
        root_project = tmp_path / "project"
        root_bundled = tmp_path / "bundled"

        for root in (root_project, root_bundled):
            skill_dir = root / "skills" / "dashboard"
            skill_dir.mkdir(parents=True)

        project_md = """\
---
name: dashboard-custom
description: Custom dashboard.
---

# Custom Dashboard
"""
        (root_project / "skills" / "dashboard" / "SKILL.md").write_text(
            project_md, encoding="utf-8"
        )
        (root_bundled / "skills" / "dashboard" / "SKILL.md").write_text(
            DASHBOARD_SKILL_MD, encoding="utf-8"
        )

        config = AssetPathConfig(bundled_root=root_bundled, project_root=root_project)
        loader = SkillLoader()
        registry = loader.load(config)

        skill = registry.get("dashboard")
        assert skill.name == "dashboard-custom"

    def test_load_scans_references(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "web-prototype"
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(parents=True)
        skill_md = """\
---
name: web-prototype
description: Web prototype skill.
---

# Web Prototype Skill
"""
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
        (refs_dir / "layouts.md").write_text("# Layouts", encoding="utf-8")
        (refs_dir / "checklist.md").write_text("# Checklist", encoding="utf-8")

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SkillLoader()
        registry = loader.load(config)

        skill = registry.get("web-prototype")
        assert skill.references
        assert "references/layouts.md" in skill.references
        assert "references/checklist.md" in skill.references


class TestSkillRegistry:
    def test_all_returns_registered_skills(self):
        registry = SkillRegistry()
        skill = SkillDefinition(
            id="test",
            name="Test",
            description="Test skill",
            body="Body",
            source_path=Path("/test"),
        )
        registry.register(skill)
        result = registry.all()
        assert len(result) == 1
        assert result[0].id == "test"

    def test_all_returns_empty_tuple_when_no_skills(self):
        registry = SkillRegistry()
        assert registry.all() == ()
