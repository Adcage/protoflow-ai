from pathlib import Path

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import ArtifactTypeState
from app.agent_loop.tools.run_checks import RunChecksTool
from app.runtime.context import CodeGenType


class CapturingQualityChecker:
    def __init__(self):
        self.manifest = None

    def run(self, workspace_root, manifest):
        self.manifest = manifest
        return []


@pytest.mark.asyncio
async def test_run_checks_uses_injected_code_gen_type(tmp_path: Path):
    state = AgentLoopState(files_touched=["src/App.vue"])
    checker = CapturingQualityChecker()
    tool = RunChecksTool()
    tool.set_state(state)
    tool.set_workspace(str(tmp_path))
    tool.set_quality_checker(checker)
    tool.set_code_gen_type(CodeGenType.VUE_PROJECT)

    await tool._arun()

    assert checker.manifest is not None
    assert checker.manifest.artifact_format == "vue_project"
    assert checker.manifest.entry == "src/App.vue"


class TestArtifactTypeStateSingleSource:
    def test_recommendation_does_not_override_effective_type(self):
        ats = ArtifactTypeState(
            requested="multi-file",
            effective="multi-file",
            recommended="single_file",
            recommendation_reason="目录文件数少于预期",
        )
        assert ats.effective == "multi-file"
        assert ats.recommended == "single_file"

    def test_requested_type_is_immutable(self):
        ats = ArtifactTypeState(
            requested="vue_project",
            effective="vue_project",
        )
        with pytest.raises(Exception):
            ats.requested = "single_file"

    def test_type_mismatch_is_reported(self):
        ats = ArtifactTypeState(
            requested="multi-file",
            effective="multi-file",
            recommended="vue_project",
            recommendation_reason="发现 vue 配置文件",
        )
        assert ats.effective != ats.recommended
        assert ats.recommendation_reason is not None
        assert ats.effective == "multi-file"

    def test_effective_defaults_to_requested(self):
        ats = ArtifactTypeState(requested="single_file", effective="")
        assert ats.effective == "single_file"


@pytest.mark.asyncio
async def test_run_checks_uses_artifact_type_effective(tmp_path: Path):
    state = AgentLoopState(files_touched=["src/App.vue"])
    state.artifact_type_state = ArtifactTypeState(
        requested="vue_project",
        effective="vue_project",
    )
    checker = CapturingQualityChecker()
    tool = RunChecksTool()
    tool.set_state(state)
    tool.set_workspace(str(tmp_path))
    tool.set_quality_checker(checker)
    tool.set_code_gen_type("single_file")

    await tool._arun()

    assert checker.manifest is not None
    assert checker.manifest.artifact_format == "vue_project"


@pytest.mark.asyncio
async def test_build_and_validate_use_same_effective_type(tmp_path: Path):
    state = AgentLoopState(files_touched=["src/App.vue"])
    state.artifact_type_state = ArtifactTypeState(
        requested="vue_project",
        effective="vue_project",
    )
    checker_build = CapturingQualityChecker()
    tool_build = RunChecksTool()
    tool_build.set_state(state)
    tool_build.set_workspace(str(tmp_path))
    tool_build.set_quality_checker(checker_build)
    tool_build.set_code_gen_type("single_file")

    await tool_build._arun()

    assert checker_build.manifest.artifact_format == "vue_project"

    state.validation_check_results = None
    checker_validate = CapturingQualityChecker()
    tool_validate = RunChecksTool()
    tool_validate.set_state(state)
    tool_validate.set_workspace(str(tmp_path))
    tool_validate.set_quality_checker(checker_validate)
    tool_validate.set_code_gen_type("single_file")

    await tool_validate._arun()

    assert checker_validate.manifest.artifact_format == "vue_project"
    assert checker_build.manifest.artifact_format == checker_validate.manifest.artifact_format


@pytest.mark.asyncio
async def test_recommendation_does_not_override_effective_type_in_run(tmp_path: Path):
    state = AgentLoopState(files_touched=["src/App.vue"])
    state.artifact_type_state = ArtifactTypeState(
        requested="multi-file",
        effective="multi-file",
    )
    checker = CapturingQualityChecker()
    tool = RunChecksTool()
    tool.set_state(state)
    tool.set_workspace(str(tmp_path))
    tool.set_quality_checker(checker)
    tool.set_code_gen_type("single_file")

    await tool._arun()

    assert checker.manifest.artifact_format == "web_multi_file"
    assert state.artifact_type_state.effective == "multi-file"
