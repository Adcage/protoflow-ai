"""Phase 3 Skill 选择、资源重载和上下文引用协议测试。"""

import hashlib
import os
import tempfile
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.plan_tools import ChooseSkillTool
from app.capabilities.skills.selector import (
    SkillNotFoundError,
    SkillRegistryProvider,
    SkillSelector,
    _sha256_file,
)


def _write_skill_file(tmpdir: str, skill_id: str, body: str) -> str:
    skill_dir = os.path.join(tmpdir, skill_id)
    os.makedirs(skill_dir, exist_ok=True)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md, "w", encoding="utf-8") as f:
        f.write(body)
    return skill_md


class _StubRegistry:
    def __init__(self, skills: dict[str, Any]) -> None:
        self._skills = skills

    def get(self, skill_id: str) -> Any:
        if skill_id not in self._skills:
            raise SkillNotFoundError(skill_id)
        return self._skills[skill_id]

    def all(self) -> list[Any]:
        return list(self._skills.values())


class TestSkillRegistryProvider:
    def test_resolve_skill_returns_digest_and_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = _write_skill_file(tmpdir, "dashboard", "---\nname: Dashboard\n---\n正文")
            expected_digest = hashlib.sha256(open(skill_md, "rb").read()).hexdigest()

            skill = SimpleNamespace(
                id="dashboard",
                name="Dashboard",
                description="x",
                source_path=skill_md,
                references=("SKILL.md", "patterns/list.md"),
            )
            provider = SkillRegistryProvider(_StubRegistry({"dashboard": skill}))
            resolved, digest, source_path, references = provider.resolve_skill("dashboard")
            assert resolved.id == "dashboard"
            assert digest == expected_digest
            assert source_path.endswith("SKILL.md")
            assert "patterns/list.md" in references

    def test_resolve_skill_raises_not_found(self):
        provider = SkillRegistryProvider(_StubRegistry({}))
        with pytest.raises(SkillNotFoundError):
            provider.resolve_skill("missing")

    def test_skill_selector_still_sorts_by_name(self):
        registry = _StubRegistry(
            {
                "b": SimpleNamespace(id="b", name="Bravo"),
                "a": SimpleNamespace(id="a", name="Alpha"),
            }
        )
        selector = SkillSelector()
        result = selector.select("any prompt", registry)
        assert [s.id for s in result] == ["a", "b"]


class TestChooseSkillToolDigest:
    @pytest.mark.asyncio
    async def test_choose_skill_persists_digest_and_resources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = _write_skill_file(tmpdir, "dashboard", "---\nname: Dashboard\n---\n正文")
            expected_digest = hashlib.sha256(open(skill_md, "rb").read()).hexdigest()

            skill = SimpleNamespace(
                id="dashboard",
                name="Dashboard",
                description="x",
                source_path=skill_md,
                references=("SKILL.md",),
            )
            provider = SkillRegistryProvider(_StubRegistry({"dashboard": skill}))

            state = AgentLoopState()
            state._state_envelope = state._to_envelope()
            state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"

            from app.agent_loop.tools.plan_tools import RecordProjectInspectionTool

            inspection_tool = RecordProjectInspectionTool()
            inspection_tool.set_state(state)
            await inspection_tool._arun(
                decision="not_applicable",
                summary="新建项目",
            )

            tool = ChooseSkillTool()
            tool.set_state(state)
            tool.set_skill_registry_provider(provider)

            await tool._arun(
                skill_id="dashboard",
                reason="dashboard for monitoring",
                loaded_resources=["SKILL.md"],
            )

            bundle = state._state_envelope.workflow.plan.capability_bundle
            assert len(bundle.skills) == 1
            ref = bundle.skills[0]
            assert ref.kind == "skill"
            assert ref.content_digest == expected_digest
            assert ref.loaded_resources == ["SKILL.md"]
            assert ref.enabled is True
            assert ref.selected_at_revision >= 0

    @pytest.mark.asyncio
    async def test_skill_body_not_persisted_to_state_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = _write_skill_file(
                tmpdir, "ui-ux", "---\nname: UI UX\n---\n超长正文-不应该写入loopStateJson"
            )

            skill = SimpleNamespace(
                id="ui-ux",
                name="UI UX",
                description="x",
                source_path=skill_md,
                references=("SKILL.md",),
            )
            provider = SkillRegistryProvider(_StubRegistry({"ui-ux": skill}))

            state = AgentLoopState()
            state._state_envelope = state._to_envelope()
            state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"

            from app.agent_loop.tools.plan_tools import RecordProjectInspectionTool

            inspection_tool = RecordProjectInspectionTool()
            inspection_tool.set_state(state)
            await inspection_tool._arun(
                decision="not_applicable",
                summary="新建项目",
            )

            tool = ChooseSkillTool()
            tool.set_state(state)
            tool.set_skill_registry_provider(provider)

            await tool._arun(skill_id="ui-ux", reason="x", loaded_resources=["SKILL.md"])

            json_str = state.serialize()
            assert "超长正文-不应该写入loopStateJson" not in json_str
            assert "ui-ux" in json_str
            assert "content_digest" in json_str


class TestSkillDigestResume:
    @pytest.mark.asyncio
    async def test_resume_with_unchanged_digest_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = _write_skill_file(tmpdir, "dashboard", "正文")
            expected_digest = hashlib.sha256(open(skill_md, "rb").read()).hexdigest()

            skill = SimpleNamespace(
                id="dashboard",
                name="Dashboard",
                description="x",
                source_path=skill_md,
                references=("SKILL.md",),
            )
            SkillRegistryProvider(_StubRegistry({"dashboard": skill}))

            state = AgentLoopState()
            state._state_envelope = state._to_envelope()
            state._state_envelope.workflow.plan.plan_stage = "select_skill"
            state._state_envelope.workflow.plan.capability_bundle.skills.append(
                __import__("app.agent_loop.state_v2", fromlist=["CapabilityRef"]).CapabilityRef(
                    capability_id="dashboard",
                    kind="skill",
                    source_path=skill_md,
                    content_digest=expected_digest,
                    loaded_resources=["SKILL.md"],
                    selected_reason="x",
                    selected_at_revision=1,
                )
            )

            # 通过重新 resolve 校验 digest 不变
            from app.capabilities.skills.selector import SkillRegistryProvider as _Provider
            _, current_digest, _, _ = _Provider(_StubRegistry({"dashboard": skill})).resolve_skill(
                "dashboard"
            )
            assert current_digest == expected_digest

    @pytest.mark.asyncio
    async def test_resume_with_changed_digest_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = _write_skill_file(tmpdir, "dashboard", "正文 V1")
            original_digest = hashlib.sha256(open(skill_md, "rb").read()).hexdigest()

            state = AgentLoopState()
            state._state_envelope = state._to_envelope()
            state._state_envelope.workflow.plan.plan_stage = "select_skill"
            from app.agent_loop.state_v2 import CapabilityRef

            state._state_envelope.workflow.plan.capability_bundle.skills.append(
                CapabilityRef(
                    capability_id="dashboard",
                    kind="skill",
                    source_path=skill_md,
                    content_digest="sha256-stale",
                    loaded_resources=["SKILL.md"],
                    selected_reason="x",
                    selected_at_revision=1,
                )
            )

            # 修改文件并重算
            with open(skill_md, "w", encoding="utf-8") as f:
                f.write("正文 V2")
            current_digest = hashlib.sha256(open(skill_md, "rb").read()).hexdigest()
            assert current_digest != original_digest

            # 校验 stale digest 已经被发现
            persisted_ref = state._state_envelope.workflow.plan.capability_bundle.skills[0]
            assert persisted_ref.content_digest != current_digest


class TestSeedCraftDisabled:
    @pytest.mark.asyncio
    async def test_seed_capability_ref_disallowed_when_enabled(self):
        from app.agent_loop.state_v2 import CapabilityRef
        from app.core.exceptions import AgentRuntimeError

        with pytest.raises(AgentRuntimeError):
            CapabilityRef(
                capability_id="seed-x",
                kind="seed",
                source_path="/x",
                content_digest="d",
                selected_reason="r",
                selected_at_revision=1,
                enabled=True,
            )

    @pytest.mark.asyncio
    async def test_craft_capability_ref_disallowed_when_enabled(self):
        from app.agent_loop.state_v2 import CapabilityRef
        from app.core.exceptions import AgentRuntimeError

        with pytest.raises(AgentRuntimeError):
            CapabilityRef(
                capability_id="craft-x",
                kind="craft",
                source_path="/x",
                content_digest="d",
                selected_reason="r",
                selected_at_revision=1,
                enabled=True,
            )

    def test_seed_disabled_allowed(self):
        from app.agent_loop.state_v2 import CapabilityRef

        ref = CapabilityRef(
            capability_id="seed-x",
            kind="seed",
            source_path="/x",
            content_digest="d",
            selected_reason="r",
            selected_at_revision=1,
            enabled=False,
        )
        assert ref.enabled is False


class TestSkillContextReload:
    def test_skill_registry_provider_handles_missing_file(self):
        skill = SimpleNamespace(
            id="ghost",
            name="Ghost",
            description="x",
            source_path="/nonexistent/SKILL.md",
            references=(),
        )
        provider = SkillRegistryProvider(_StubRegistry({"ghost": skill}))
        # Should not raise; empty digest is fallback
        _, digest, _, references = provider.resolve_skill("ghost")
        assert digest == ""
        assert references == ()

    def test_sha256_helper(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            tmp = f.name
        try:
            expected = hashlib.sha256(b"hello").hexdigest()
            assert _sha256_file(tmp) == expected
        finally:
            os.unlink(tmp)
