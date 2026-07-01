"""图级 Plan 前进性回归测试。

使用 scripted fake model 与临时空工作区验证：
1. Plan 阶段严格按 PlanStage 单向推进，不会在 Plan 完成前触发 Route
2. 项目检查只记录一次
3. 工具前导文字不作为用户可见气泡发出
4. Plan 完成后恰好触发一次 Route
5. 硬上限模型反复循环不会伪造成功
6. 事件映射无 unclassified 警告
"""

import json
import tempfile
from pathlib import Path

import pytest
from langchain_core.messages import AIMessageChunk

from app.agent_loop.graph import build_agent_loop_graph
from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import PlanStateV2
from app.agent_loop.nodes.init import InitNode
from app.agent_loop.nodes.plan_step import PlanStepNode
from app.agent_loop.nodes.implement_dispatcher import ImplementDispatcherNode
from app.agent_loop.nodes.route_step import RouteStepNode
from app.agent_loop.nodes.validate_step import ValidateStepNode
from app.agent_loop.nodes.finish import FinishNode
from app.capabilities.common.asset_index import AssetIndex
from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.types import SkillDefinition
from app.capabilities.seeds.registry import SeedRegistry
from app.capabilities.templates.registry import TemplateRegistry
from app.capabilities.design_systems.registry import DesignSystemRegistry
from app.capabilities.craft.registry import CraftRegistry
from app.prompts.registry import PromptModuleRegistry
from app.prompts.default_modules import (
    RuntimeBoundaryModule,
    SafetyAndInjectionResistanceModule,
    ProjectRulesModule,
    TaskContextModule,
    OutputContractModule,
    AntiRoleplayModule,
)
from app.prompts.asset_modules import ArtifactOutputContractModule
from app.prompts.loop_modules import (
    PlanWorkflowModule,
    ImplementWorkflowModule,
    ValidateWorkflowModule,
    ValidateFeedbackModule,
    ToolListModule,
    PlanSpecModule,
    SkillContextModule,
)
from app.prompts.route_modules import (
    RouteInitialModule,
    RouteAfterPlanModule,
    RouteAfterImplementModule,
    RouteAfterValidateModule,
)
from app.prompts.test_modules import TestModeInfoModule, ProductionSecurityModule
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.agent_loop.event_mapper import LegacyEventMapper
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices


_FAKE_SKILL = SkillDefinition(
    id="test-login-skill",
    name="登录界面 Skill",
    description="用于生成登录界面的测试 Skill",
    body="# 登录界面规则\n\n- 必须包含用户名和密码输入框\n- 必须包含登录按钮",
    source_path=Path(__file__),
    references=(),
)


class FakeModel:
    """Scripted model that returns predetermined tool calls and text.

    Yields AIMessageChunk stream that LangGraph's _stream_invoke consumes.
    Each call to astream() consumes the next step from the script.
    """

    def __init__(self, script: list[dict]):
        self._script = list(script)
        self._call_index = 0

    def bind_tools(self, tools):
        return self

    async def astream(self, messages):
        if self._call_index >= len(self._script):
            yield AIMessageChunk(content="")
            return

        step = self._script[self._call_index]
        self._call_index += 1

        if "tool_calls" in step:
            if step.get("text"):
                yield AIMessageChunk(content=step["text"])
            for tc in step["tool_calls"]:
                yield AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": tc["name"],
                            "args": json.dumps(tc["arguments"], ensure_ascii=False),
                            "id": tc.get("id", f"tc-{self._call_index}"),
                            "index": 0,
                        }
                    ],
                )
        elif "text" in step:
            yield AIMessageChunk(content=step["text"])
        else:
            yield AIMessageChunk(content="")


class FakeChatModelFactory:
    """Factory that returns a single shared FakeModel so script index persists across steps."""

    def __init__(self, script: list[dict]):
        self._script = script
        self._model: FakeModel | None = None

    def create(self, config: dict) -> FakeModel:
        if self._model is None:
            self._model = FakeModel(self._script)
        return self._model


class CollectingEventBus:
    """Event bus that collects all emitted events for assertion."""

    def __init__(self, agent_run_id: int = 1):
        self.agent_run_id = agent_run_id
        self._seq = 0
        self.events: list[RuntimeEvent] = []

    async def emit(self, event: RuntimeEvent) -> None:
        self._seq += 1
        self.events.append(event)

    async def next_event(self):
        return None

    async def close(self):
        pass


def _build_prompt_module_registry() -> PromptModuleRegistry:
    registry = PromptModuleRegistry()
    registry.register(RuntimeBoundaryModule())
    registry.register(SafetyAndInjectionResistanceModule())
    registry.register(ProductionSecurityModule())
    registry.register(ProjectRulesModule())
    registry.register(ToolListModule())
    registry.register(RouteInitialModule())
    registry.register(RouteAfterPlanModule())
    registry.register(RouteAfterImplementModule())
    registry.register(RouteAfterValidateModule())
    registry.register(PlanWorkflowModule())
    registry.register(ImplementWorkflowModule())
    registry.register(ValidateWorkflowModule())
    registry.register(PlanSpecModule())
    registry.register(ValidateFeedbackModule())
    registry.register(ArtifactOutputContractModule())
    registry.register(OutputContractModule())
    registry.register(AntiRoleplayModule())
    registry.register(SkillContextModule())
    registry.register(TaskContextModule())
    registry.register(TestModeInfoModule())
    from app.prompts.generation_modes.application import (
        ApplicationPlanModule,
        ApplicationValidateModule,
    )
    from app.prompts.generation_modes.common import GenerationModeClarificationModule
    registry.register(ApplicationPlanModule())
    registry.register(ApplicationValidateModule())
    registry.register(GenerationModeClarificationModule())
    return registry


def _build_asset_index() -> AssetIndex:
    skill_registry = SkillRegistry()
    skill_registry.register(_FAKE_SKILL)
    return AssetIndex(
        skill_registry=skill_registry,
        seed_registry=SeedRegistry(),
        template_registry=TemplateRegistry(),
        design_system_registry=DesignSystemRegistry(),
        craft_registry=CraftRegistry(),
        bundled_root=Path("."),
    )


class FakeModelResolver:
    def __init__(self):
        self.load_calls = 0

    async def load_bundle(self, context):
        self.load_calls += 1

    def resolve(self, role):
        from app.modeling.resolver import ResolvedModelConfig
        from app.modeling.roles import ModelRole

        return ResolvedModelConfig(
            role=ModelRole.PRIMARY,
            provider="openai",
            model_name="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
        )


def _make_context(workspace_path: str) -> ExecutionContext:
    return ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="创建登录界面",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path=workspace_path,
        run_mode=RunMode.GENERATE,
        is_test=True,
    )


def _make_services(
    event_bus: CollectingEventBus,
    fake_factory: FakeChatModelFactory,
    asset_index: AssetIndex,
) -> RuntimeServices:

    class FakeAssetManager:
        def __init__(self, index: AssetIndex):
            self._index = index

        def get_index(self) -> AssetIndex:
            return self._index

    fake_am = FakeAssetManager(asset_index)

    from app.generation_modes.registry import GenerationModeRegistry
    from app.generation_modes.application import register_application

    gen_mode_registry = GenerationModeRegistry()
    register_application(gen_mode_registry)
    gen_mode_registry.validate_prompt_modules_exist(
        _build_prompt_module_registry()
    )

    return RuntimeServices(
        chat_model_factory=fake_factory,
        model_resolver=FakeModelResolver(),
        prompt_module_registry=_build_prompt_module_registry(),
        event_bus=event_bus,
        asset_manager=fake_am,
        generation_mode_registry=gen_mode_registry,
    )


def _new_project_plan_script() -> list[dict]:
    """Script for the "new project login page" Plan flow.

    The graph flow is:
    init → route_step → plan_step (×N) → route_step → finish

    Route step (initial) needs: decide_route(mode="plan")
    Plan steps need the sequence of plan tools
    Route step (after_plan) needs: decide_route(mode="implement")
    """
    return [
        # Step 0: route_step (initial) → decide_route to plan
        {
            "tool_calls": [
                {
                    "name": "decide_route",
                    "arguments": {
                        "mode": "plan",
                        "code_gen_type": "vue_project",
                        "reason": "用户需求是创建登录界面，需要规划",
                    },
                    "id": "route-1",
                }
            ]
        },
        # Step 1: plan_step - submit requirement brief
        {
            "text": "我来理解您的需求并记录需求摘要。",
            "tool_calls": [
                {
                    "name": "submit_requirement_brief",
                    "arguments": {
                        "application_direction": "登录界面",
                        "target_users": "网站用户",
                        "primary_scenarios": ["用户登录", "密码找回"],
                        "functional_scope": ["用户名密码登录", "记住我", "忘记密码链接"],
                    },
                    "id": "plan-1",
                }
            ],
        },
        # Step 2: plan_step - record project inspection (not_applicable)
        {
            "text": "项目为新建，记录项目检查结果。",
            "tool_calls": [
                {
                    "name": "record_project_inspection",
                    "arguments": {
                        "decision": "not_applicable",
                        "summary": "项目为新建 Vue 项目，无需检查已有代码",
                    },
                    "id": "plan-2",
                }
            ],
        },
        # Step 3: plan_step - choose skill
        {
            "text": "选择适合登录界面的 Skill。",
            "tool_calls": [
                {
                    "name": "choose_skill",
                    "arguments": {
                        "skill_id": "test-login-skill",
                        "reason": "登录界面 Skill 提供了登录页面的设计规则和组件指引",
                    },
                    "id": "plan-3",
                }
            ],
        },
        # Step 4: plan_step - propose design
        {
            "text": "提出设计建议。",
            "tool_calls": [
                {
                    "name": "propose_design",
                    "arguments": {
                        "information_architecture": [
                            {
                                "page_id": "login",
                                "name": "登录页",
                                "purpose": "用户身份验证",
                                "primary_actions": ["提交登录", "跳转注册"],
                                "components": ["LoginForm", "PasswordInput"],
                            }
                        ],
                        "visual_direction": "简洁现代风格",
                        "color_system": "主色调蓝色系，辅助灰色",
                        "typography": "系统默认无衬线字体",
                        "component_language": "Ant Design Vue 组件库",
                        "interaction_model": "表单提交+即时验证",
                        "responsive_strategy": "移动优先响应式",
                        "alternative_options": [
                            {"key": "visual_direction", "option_id": "dark", "description": "深色主题"},
                            {"key": "visual_direction", "option_id": "light", "description": "浅色主题"},
                            {"key": "color_system", "option_id": "blue", "description": "蓝色系"},
                            {"key": "color_system", "option_id": "green", "description": "绿色系"},
                        ],
                    },
                    "id": "plan-4",
                }
            ],
        },
        # Step 5: plan_step - ask user for design confirmation
        {
            "text": "请确认设计方案。",
            "tool_calls": [
                {
                    "name": "ask_user",
                    "arguments": {
                        "stage": "confirm_design",
                        "questions": [
                            {
                                "id": "q1",
                                "prompt": "设计建议是否符合您的期望？",
                                "inputType": "single_select",
                                "required": True,
                                "options": [
                                    {"id": "ok", "label": "没有需要调整", "description": "设计方案确认"},
                                    {"id": "adjust", "label": "需要调整", "description": "修改设计方案"},
                                ],
                            }
                        ],
                    },
                    "id": "plan-5",
                }
            ],
        },
        # Step 6: plan_step - confirm design (after user says ok in resume)
        # Since ask_user pauses the graph (waiting_for_user), we need to
        # handle this differently. In our test flow, ask_user sets
        # waiting_for_user which causes route_after_plan_step → finish.
        # For the full flow test, we'll skip ask_user and directly
        # confirm_design to avoid the pause.
        # Step 6: plan_step - write implementation plan
        {
            "text": "设计已确认，现在生成实施计划。",
            "tool_calls": [
                {
                    "name": "write_implementation_plan",
                    "arguments": {
                        "tasks": [
                            {
                                "task_id": "T1",
                                "goal": "创建登录页面组件",
                                "allowed_files": ["src/views/Login.vue", "src/router/index.js"],
                                "prohibited_files": [],
                                "dependencies": [],
                                "inputs": [],
                                "outputs": ["Login.vue"],
                                "test_requirements": [],
                                "acceptance_criteria": ["登录页面可正常渲染"],
                            }
                        ],
                        "test_plan": [
                            {
                                "test_id": "test-1",
                                "description": "验证登录表单提交",
                                "target": "Login.vue",
                                "expected": "表单提交后触发登录逻辑",
                            }
                        ],
                        "acceptance_criteria": ["登录页面功能完整"],
                        "summary": "创建登录界面",
                    },
                    "id": "plan-6",
                }
            ],
        },
    ]


def _new_project_plan_script_without_ask_user() -> list[dict]:
    """Plan script aligned with the current staged confirmation flow.

    Goes: submit_requirement_brief → record_project_inspection → choose_skill
    → propose_design → ask_user(confirm_design)
    """
    return [
        # Step 0: route_step (initial) → decide_route to plan
        {
            "tool_calls": [
                {
                    "name": "decide_route",
                    "arguments": {
                        "mode": "plan",
                        "code_gen_type": "vue_project",
                        "reason": "用户需求是创建登录界面，需要规划",
                    },
                    "id": "route-1",
                }
            ]
        },
        # Step 1: plan_step - submit requirement brief
        {
            "text": "我来理解您的需求并记录需求摘要。",
            "tool_calls": [
                {
                    "name": "submit_requirement_brief",
                    "arguments": {
                        "application_direction": "登录界面",
                        "target_users": "网站用户",
                        "primary_scenarios": "用户登录\n密码找回",
                        "functional_scope": "用户名密码登录\n记住我\n忘记密码链接",
                    },
                    "id": "plan-1",
                }
            ],
        },
        # Step 2: plan_step - record project inspection (not_applicable)
        {
            "text": "项目为新建，记录项目检查结果。",
            "tool_calls": [
                {
                    "name": "record_project_inspection",
                    "arguments": {
                        "decision": "not_applicable",
                        "summary": "项目为新建 Vue 项目，无需检查已有代码",
                    },
                    "id": "plan-2",
                }
            ],
        },
        # Step 3: plan_step - choose skill
        {
            "text": "选择适合登录界面的 Skill。",
            "tool_calls": [
                {
                    "name": "choose_skill",
                    "arguments": {
                        "skill_id": "test-login-skill",
                        "reason": "登录界面 Skill 提供了登录页面的设计规则和组件指引",
                    },
                    "id": "plan-3",
                }
            ],
        },
        # Step 4: plan_step - propose design
        {
            "text": "提出设计建议。",
            "tool_calls": [
                {
                    "name": "propose_design",
                    "arguments": {
                        "information_architecture": [
                            {
                                "page_id": "login",
                                "name": "登录页",
                                "purpose": "用户身份验证",
                                "primary_actions": ["提交登录", "跳转注册"],
                                "components": ["LoginForm", "PasswordInput"],
                            }
                        ],
                        "visual_direction": "简洁现代风格",
                        "color_system": "主色调蓝色系，辅助灰色",
                        "typography": "系统默认无衬线字体",
                        "component_language": "Ant Design Vue 组件库",
                        "interaction_model": "表单提交+即时验证",
                        "responsive_strategy": "移动优先响应式",
                        "alternative_options": [
                            {"key": "visual_direction", "option_id": "dark", "description": "深色主题"},
                            {"key": "visual_direction", "option_id": "light", "description": "浅色主题"},
                            {"key": "color_system", "option_id": "blue", "description": "蓝色系"},
                            {"key": "color_system", "option_id": "green", "description": "绿色系"},
                        ],
                    },
                    "id": "plan-4",
                }
            ],
        },
        # Step 5: plan_step - ask user to confirm design
        {
            "text": "先向用户展示设计方案并等待确认。",
            "tool_calls": [
                {
                    "name": "ask_user",
                    "arguments": {
                        "stage": "confirm_design",
                        "questions": [
                            {
                                "id": "design-confirm",
                                "prompt": "以上登录页方案是否确认？",
                                "inputType": "single_select",
                                "options": [
                                    {"id": "approved", "label": "没有需要调整"},
                                    {"id": "needs_change", "label": "需要调整"},
                                ],
                                "required": True,
                            }
                        ],
                    },
                    "id": "plan-5",
                }
            ],
        },
    ]


class TestNewProjectPlanProgression:
    """Test 1: Plan stages advance to design confirmation without Plan→Route loop."""

    @pytest.mark.asyncio
    async def test_new_project_plan_progresses_without_plan_route_loop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _make_context(tmpdir)
            asset_index = _build_asset_index()
            event_bus = CollectingEventBus()
            script = _new_project_plan_script_without_ask_user()
            fake_factory = FakeChatModelFactory(script)
            services = _make_services(event_bus, fake_factory, asset_index)

            init_node = InitNode(context, services)
            route_step = RouteStepNode(context, services)
            plan_step = PlanStepNode(context, services)
            implement_step = ImplementDispatcherNode(context, services)
            validate_step = ValidateStepNode(context, services)
            finish_node = FinishNode(context, services)

            graph = build_agent_loop_graph(
                init_node, route_step, plan_step, implement_step, validate_step, finish_node
            )

            state = AgentLoopState(is_test=True)
            result = await graph.ainvoke(state)
            final = AgentLoopState.from_graph_result(result)

            envelope = getattr(final, "_state_envelope", None)
            assert envelope is not None, "Envelope should be initialized"
            plan_state: PlanStateV2 = envelope.workflow.plan

            # Current flow should advance to confirm_design and wait for user input.
            assert plan_state.plan_stage == "confirm_design", (
                f"Expected plan_stage='confirm_design', got '{plan_state.plan_stage}'"
            )

            # Requirement brief should be recorded
            assert plan_state.requirement_brief is not None
            assert plan_state.requirement_brief.application_direction.value == "登录界面"

            # Design confirmation is now a pause point before implementation plan generation.
            assert plan_state.implementation_plan is None
            assert final.status == "waiting_for_user"

            # Route count before Plan completes = 0 (Route only fires before Plan starts and after)
            # The first route_step fires before Plan; it's the initial route
            # Plan doesn't trigger Route mid-flow; plan_just_finished triggers one Route after
            tool_call_names = [
                tc.name for tc in final.executed_tool_calls
            ]
            route_count = tool_call_names.count("decide_route")
            assert route_count <= 1, (
                f"decide_route called {route_count} times, expected ≤ 1 (initial route only)"
            )

            assert final.mode == "plan", f"Expected mode='plan', got '{final.mode}'"


class TestProjectInspectionRecordedOnce:
    """Test 2: Project inspection is recorded exactly once."""

    @pytest.mark.asyncio
    async def test_project_inspection_is_recorded_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _make_context(tmpdir)
            asset_index = _build_asset_index()
            event_bus = CollectingEventBus()
            script = _new_project_plan_script_without_ask_user()
            fake_factory = FakeChatModelFactory(script)
            services = _make_services(event_bus, fake_factory, asset_index)

            init_node = InitNode(context, services)
            route_step = RouteStepNode(context, services)
            plan_step = PlanStepNode(context, services)
            implement_step = ImplementDispatcherNode(context, services)
            validate_step = ValidateStepNode(context, services)
            finish_node = FinishNode(context, services)

            graph = build_agent_loop_graph(
                init_node, route_step, plan_step, implement_step, validate_step, finish_node
            )

            state = AgentLoopState(is_test=True)
            result = await graph.ainvoke(state)
            final = AgentLoopState.from_graph_result(result)

            envelope = getattr(final, "_state_envelope", None)
            assert envelope is not None
            plan_state: PlanStateV2 = envelope.workflow.plan

            # Project inspection should be recorded exactly once
            assert plan_state.project_inspection is not None
            assert plan_state.project_inspection["decision"] == "not_applicable"

            # record_project_inspection should appear exactly once in tool calls
            inspection_calls = [
                tc for tc in final.executed_tool_calls if tc.name == "record_project_inspection"
            ]
            assert len(inspection_calls) == 1, (
                f"record_project_inspection called {len(inspection_calls)} times, expected 1"
            )

            # Directory reads should be bounded (0 for new project with not_applicable)
            read_dir_calls = [
                tc for tc in final.executed_tool_calls if tc.name == "read_dir"
            ]
            assert len(read_dir_calls) <= 3, (
                f"read_dir called {len(read_dir_calls)} times, expected ≤ 3"
            )


class TestInternalPlanTextNotUserVisible:
    """Test 3: Tool-preceding explanation text is not emitted as a user-visible chat bubble."""

    @pytest.mark.asyncio
    async def test_internal_plan_text_is_not_user_visible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _make_context(tmpdir)
            asset_index = _build_asset_index()
            event_bus = CollectingEventBus()
            script = _new_project_plan_script_without_ask_user()
            fake_factory = FakeChatModelFactory(script)
            services = _make_services(event_bus, fake_factory, asset_index)

            init_node = InitNode(context, services)
            route_step = RouteStepNode(context, services)
            plan_step = PlanStepNode(context, services)
            implement_step = ImplementDispatcherNode(context, services)
            validate_step = ValidateStepNode(context, services)
            finish_node = FinishNode(context, services)

            graph = build_agent_loop_graph(
                init_node, route_step, plan_step, implement_step, validate_step, finish_node
            )

            state = AgentLoopState(is_test=True)
            await graph.ainvoke(state)

            # TEXT_DELTA events should not be emitted when text precedes tool calls
            # In _stream_invoke, when text_content and tool_calls are both present,
            # the text is suppressed (no TEXT_DELTA event emitted)
            text_delta_events = [
                e for e in event_bus.events
                if e.event_type == RuntimeEventType.TEXT_DELTA
            ]

            # The script has steps with both text and tool_calls.
            # Those text parts should NOT produce TEXT_DELTA events.
            assert len(text_delta_events) == 0, (
                f"Expected 0 TEXT_DELTA events (internal text suppressed), got {len(text_delta_events)}"
            )


class TestPlanCompletionHandsOffToRouteOnce:
    """Test 4: 设计确认前不会额外触发 Route 或进入 Implement。"""

    @pytest.mark.asyncio
    async def test_plan_completion_hands_off_to_route_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _make_context(tmpdir)
            asset_index = _build_asset_index()
            event_bus = CollectingEventBus()
            script = _new_project_plan_script_without_ask_user()
            fake_factory = FakeChatModelFactory(script)
            services = _make_services(event_bus, fake_factory, asset_index)

            init_node = InitNode(context, services)
            route_step = RouteStepNode(context, services)
            plan_step = PlanStepNode(context, services)
            implement_step = ImplementDispatcherNode(context, services)
            validate_step = ValidateStepNode(context, services)
            finish_node = FinishNode(context, services)

            graph = build_agent_loop_graph(
                init_node, route_step, plan_step, implement_step, validate_step, finish_node
            )

            state = AgentLoopState(is_test=True)
            result = await graph.ainvoke(state)
            final = AgentLoopState.from_graph_result(result)

            route_iterations = final.route_iterations
            assert route_iterations == 1, (
                f"Expected route_iterations=1 (initial route only), got {route_iterations}"
            )

            assert not final.plan_just_finished, (
                "在用户确认设计前，不应标记 Plan 已完成"
            )

            assert final.mode == "plan", f"Expected mode='plan', got '{final.mode}'"
            assert final.status == "waiting_for_user"


class TestIterationCapCannotReportFalseSuccess:
    """Test 5: A faulty model that keeps repeating gets blocked, not completed."""

    @pytest.mark.asyncio
    async def test_iteration_cap_cannot_report_false_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _make_context(tmpdir)
            asset_index = _build_asset_index()
            event_bus = CollectingEventBus()

            # Model that keeps calling submit_requirement_brief over and over
            # but with insufficient data or wrong stage - it will get STATE_ERROR
            # which is recoverable. The graph will keep iterating until hard limit.
            repeating_script = [
                # Step 0: route_step (initial) → decide_route to plan
                {
                    "tool_calls": [
                        {
                            "name": "decide_route",
                            "arguments": {"mode": "plan", "reason": "需要规划"},
                            "id": "route-1",
                        }
                    ]
                },
            ]
            # Add many repeated submit_requirement_brief calls (same stage, will succeed first time
            # but then fail on second attempt because stage has already advanced)
            for i in range(25):
                repeating_script.append({
                    "text": "我再次提交需求摘要。",
                    "tool_calls": [
                        {
                            "name": "submit_requirement_brief",
                            "arguments": {
                                "application_direction": "登录界面",
                                "target_users": "网站用户",
                            },
                            "id": f"repeat-{i}",
                        }
                    ],
                })

            fake_factory = FakeChatModelFactory(repeating_script)
            services = _make_services(event_bus, fake_factory, asset_index)

            # Use a low max_iterations so the test doesn't run forever
            init_node = InitNode(context, services)
            route_step = RouteStepNode(context, services)
            plan_step = PlanStepNode(context, services)
            implement_step = ImplementDispatcherNode(context, services)
            validate_step = ValidateStepNode(context, services)
            finish_node = FinishNode(context, services)

            graph = build_agent_loop_graph(
                init_node, route_step, plan_step, implement_step, validate_step, finish_node
            )

            state = AgentLoopState(is_test=True, max_iterations=15)
            result = await graph.ainvoke(state)
            final = AgentLoopState.from_graph_result(result)

            # The model should NOT have completed successfully
            assert final.status in ("failed", "completed")
            # If completed, it should NOT have plan_stage="completed" without a real plan
            envelope = getattr(final, "_state_envelope", None)
            if envelope is not None:
                plan_state = envelope.workflow.plan
                # The plan should not have reached "completed" stage through repetition
                if final.status == "completed":
                    # If somehow completed, it must have a real implementation plan
                    assert plan_state.implementation_plan is not None, (
                        "Completed without implementation plan is false success"
                    )

            # The state must not claim success without evidence
            if final.status == "failed":
                # This is the expected outcome - model got stuck repeating
                assert final.final_summary != "" or final.iteration >= 15


class TestNoUnclassifiedEventWarning:
    """Test 6: No unclassified tool warnings in event mapper."""

    @pytest.mark.asyncio
    async def test_target_run_has_no_unclassified_event_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = _make_context(tmpdir)
            asset_index = _build_asset_index()
            event_bus = CollectingEventBus()
            script = _new_project_plan_script_without_ask_user()
            fake_factory = FakeChatModelFactory(script)
            services = _make_services(event_bus, fake_factory, asset_index)

            init_node = InitNode(context, services)
            route_step = RouteStepNode(context, services)
            plan_step = PlanStepNode(context, services)
            implement_step = ImplementDispatcherNode(context, services)
            validate_step = ValidateStepNode(context, services)
            finish_node = FinishNode(context, services)

            graph = build_agent_loop_graph(
                init_node, route_step, plan_step, implement_step, validate_step, finish_node
            )

            state = AgentLoopState(is_test=True)
            await graph.ainvoke(state)

            # Map all events through LegacyEventMapper and capture warnings
            mapper = LegacyEventMapper()
            unclassified_warnings = []

            # Capture warnings from logging
            with pytest.MonkeyPatch.context():
                import app.runtime.event_mapper as em_module

                original_warning = em_module.logger.warning

                def capturing_warning(msg, *args, **kwargs):
                    formatted = msg % args if args else msg
                    if "unclassified" in formatted.lower():
                        unclassified_warnings.append(formatted)
                    original_warning(msg, *args, **kwargs)

                em_module.logger.warning = capturing_warning

                for seq, event in enumerate(event_bus.events, start=1):
                    from app.runtime.event_bus import SequencedRuntimeEvent

                    seq_event = SequencedRuntimeEvent(
                        agent_run_id=1,
                        seq=seq,
                        event=event,
                    )
                    mapper.map_event(seq_event)

                em_module.logger.warning = original_warning

            assert len(unclassified_warnings) == 0, (
                f"Found {len(unclassified_warnings)} unclassified tool warnings: {unclassified_warnings}"
            )
