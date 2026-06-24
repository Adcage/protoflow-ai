from pathlib import Path

from app.capabilities.common.loader_result import SelectedCapabilities
from app.capabilities.skills.prompt_module import SelectedSkillModule
from app.capabilities.skills.types import SkillDefinition
from app.prompts.asset_modules import ArtifactOutputContractModule
from app.runtime.state import ExecutionState


class TestArtifactOutputContractModule:
    def test_id(self):
        m = ArtifactOutputContractModule()
        assert m.id == "artifact_output_contract"

    def test_always_enabled(self):
        m = ArtifactOutputContractModule()
        assert m.enabled(None, None) is True

    def test_render_content(self):
        m = ArtifactOutputContractModule()
        result = m.render(None, None)
        assert "Artifact Output Contract" in result
        assert "write_file" not in result


class TestSelectedSkillModule:
    def test_id(self):
        m = SelectedSkillModule()
        assert m.id == "selected_skill"

    def test_disabled_without_capabilities(self):
        m = SelectedSkillModule()
        state = ExecutionState()
        assert m.enabled(None, state) is False

    def test_disabled_without_skill(self):
        m = SelectedSkillModule()
        state = ExecutionState()
        state.selected_capabilities = SelectedCapabilities()
        assert m.enabled(None, state) is False

    def test_enabled_with_skill(self):
        m = SelectedSkillModule()
        skill = SkillDefinition(
            id="dashboard",
            name="dashboard",
            description="Dashboard skill",
            body="Build a dashboard.",
            source_path=Path("."),
        )
        state = ExecutionState()
        state.selected_capabilities = SelectedCapabilities(skills=[skill])
        assert m.enabled(None, state) is True

    def test_render_with_skill(self):
        m = SelectedSkillModule()
        skill = SkillDefinition(
            id="dashboard",
            name="dashboard",
            description="Dashboard skill",
            body="Build a dashboard.",
            source_path=Path("."),
        )
        state = ExecutionState()
        state.selected_capabilities = SelectedCapabilities(skills=[skill])
        result = m.render(None, state)
        assert "## Selected Skill: dashboard" in result
        assert "Build a dashboard." in result
        assert "Use this workflow for the current generation." in result

    def test_render_returns_empty_without_caps(self):
        m = SelectedSkillModule()
        state = ExecutionState()
        assert m.render(None, state) == ""
