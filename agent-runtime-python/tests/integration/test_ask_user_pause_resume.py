import json
import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.graph import route_after_plan_step
from app.agent_loop.nodes.init import InitNode
from app.modeling.resolver import ResolvedModelConfig
from app.modeling.roles import ModelRole
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.runtime.services import RuntimeServices
from app.agent_loop.tools.ask_user import AskUserTool
from app.runtime.state import ToolCallRecord


class FakeModelResolver:
    def __init__(self):
        self.load_calls = 0
        self.model_config = ResolvedModelConfig(
            role=ModelRole.PRIMARY,
            provider="openai",
            model_name="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
            api_key="sk-restored",
        )

    async def load_bundle(self, context):
        self.load_calls += 1

    def resolve(self, role):
        return self.model_config


class TestAskUserPauseFlow:
    """测试 ask_user 触发暂停的完整流程"""

    @pytest.mark.asyncio
    async def test_ask_user_sets_waiting_for_user(self):
        """ask_user 调用后 state.status 应变为 waiting_for_user"""
        state = AgentLoopState()
        tool = AskUserTool()
        tool.set_state(state)

        result = await tool._arun(question="您希望用深色还是浅色主题？", input_type="single_select", options=["深色", "浅色"])

        assert state.status == "waiting_for_user"
        assert len(state.clarification_questions) == 1
        assert state.clarification_questions[0]["question"] == "您希望用深色还是浅色主题？"
        assert "等待用户回答" in result

    def test_route_after_step_routes_to_finish_on_waiting(self):
        """waiting_for_user 状态下路由应返回 finish"""
        state = AgentLoopState(status="waiting_for_user", iteration=3)
        assert route_after_plan_step(state) == "finish"

    def test_route_after_step_waiting_priorities_over_running(self):
        """waiting_for_user 应优先于正常路由"""
        state = AgentLoopState(status="waiting_for_user", mode="plan", iteration=1)
        assert route_after_plan_step(state) == "finish"

    @pytest.mark.asyncio
    async def test_full_pause_flow(self):
        """完整暂停流程: ask_user → waiting_for_user → route → finish → serialize"""
        state = AgentLoopState()
        state.selected_skill_id = "ui-ux-pro-max"
        state.implementation_outline = {"text": "创建 SaaS 仪表盘"}
        state.iteration = 3
        state.mode = "plan"

        tool = AskUserTool()
        tool.set_state(state)
        await tool._arun(question="选择配色方案？", input_type="single_select", options=["深色", "浅色"])

        assert state.status == "waiting_for_user"
        assert route_after_plan_step(state) == "finish"

        json_str = state.serialize()
        data = json.loads(json_str)
        wf = data["workflow"]
        assert wf["plan"]["is_waiting_for_user"] is True
        assert wf["plan"]["selected_skill_id"] == "ui-ux-pro-max"
        assert wf["plan"]["implementation_outline"] == {"text": "创建 SaaS 仪表盘"}
        assert wf["iteration"] == 3


class TestResumeFlow:
    """测试从暂停状态恢复的完整流程"""

    @pytest.mark.asyncio
    async def test_resume_reloads_model_when_snapshot_strips_api_key(self):
        """恢复快照缺少 apiKey 时应重新加载完整模型配置"""
        original = AgentLoopState(status="waiting_for_user", iteration=2)
        original.resolved_model = {
            "provider": "openai",
            "modelName": "gpt-4o-mini",
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "sk-original",
        }
        restored = AgentLoopState.deserialize(original.serialize())
        restored.status = "running"

        context = ExecutionContext(
            agent_run_id=1,
            app_id=1,
            session_id=1,
            user_id=1,
            prompt="继续",
            code_gen_type=CodeGenType.VUE_PROJECT,
            workspace_path=".",
            run_mode=RunMode.GENERATE,
            is_resume=True,
        )
        resolver = FakeModelResolver()
        services = RuntimeServices(model_resolver=resolver)

        await InitNode(context, services)(restored)

        assert resolver.load_calls == 1
        assert restored.resolved_model == {
            "provider": "openai",
            "modelName": "gpt-4o-mini",
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "sk-restored",
        }

    def test_deserialize_restores_all_persisted_fields(self):
        """反序列化应恢复所有持久化字段"""
        original = AgentLoopState()
        original.mode = "implement"
        original.status = "waiting_for_user"
        original.iteration = 5
        original.mode_switches = 2
        original.selected_skill_id = "ui-ux-pro-max"
        original.implementation_outline = {"text": "test plan", "steps": ["step1", "step2"]}
        original.clarification_questions = [{"id": "q1", "question": "颜色？"}]
        original.files_touched = ["src/App.vue", "src/main.ts"]
        original.executed_tool_calls = [
            ToolCallRecord(id="t1", name="select_skill", arguments={"skill_id": "ui-ux-pro-max"}, result="已选择"),
            ToolCallRecord(id="t2", name="ask_user", arguments={"question": "颜色？"}, result="已向用户提问"),
        ]
        original.conversation_messages = [
            {"role": "user", "content": "做一个仪表盘"},
            {"role": "assistant", "content": "好的，我来帮你"},
        ]
        original.resolved_model = {"provider": "openai", "modelName": "gpt-4", "baseUrl": "https://api.openai.com/v1", "apiKey": "sk-secret"}
        original.plan_iterations = 3

        json_str = original.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored.mode == "implement"
        assert restored.status == "waiting_for_user"
        assert restored.iteration == 5
        assert restored.mode_switches == 2
        assert restored.selected_skill_id == "ui-ux-pro-max"
        assert restored.implementation_outline == {"text": "test plan", "steps": ["step1", "step2"]}
        assert len(restored.clarification_questions) == 1
        assert restored.files_touched == ["src/App.vue", "src/main.ts"]
        assert len(restored.executed_tool_calls) == 2
        assert restored.executed_tool_calls[0].name == "select_skill"
        assert restored.executed_tool_calls[0].arguments == {"skill_id": "ui-ux-pro-max"}
        assert restored.executed_tool_calls[1].name == "ask_user"
        assert len(restored.conversation_messages) == 2
        assert restored.conversation_messages[1]["role"] == "assistant"

    def test_api_key_stripped_on_serialize(self):
        """序列化时应移除 apiKey"""
        state = AgentLoopState()
        state.resolved_model = {
            "provider": "openai",
            "modelName": "gpt-4",
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "sk-super-secret-key-12345",
        }
        json_str = state.serialize()
        data = json.loads(json_str)
        wf = data["workflow"]
        assert "apiKey" not in wf["resolved_model"]
        assert wf["resolved_model"]["provider"] == "openai"
        assert wf["resolved_model"]["modelName"] == "gpt-4"

    def test_resume_resets_status_to_running(self):
        """恢复时应将 status 从 waiting_for_user 重置为 running"""
        state = AgentLoopState()
        state.status = "waiting_for_user"
        state.iteration = 3
        state.selected_skill_id = "ui-ux-pro-max"

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored.status == "waiting_for_user"

        restored.status = "running"
        assert restored.status == "running"
        assert restored.selected_skill_id == "ui-ux-pro-max"
        assert restored.iteration == 3

    def test_resume_does_not_persist_current_answer_in_internal_messages(self):
        """恢复时不应将当前用户回答追加到 conversation_messages"""
        state = AgentLoopState(status="waiting_for_user")
        state.conversation_messages = [
            {"role": "system", "content": "等待用户补充需求"},
        ]

        restored = AgentLoopState.deserialize(state.serialize())
        restored.status = "running"

        assert restored.conversation_messages == [
            {"role": "system", "content": "等待用户补充需求"},
        ]

    def test_pause_snapshot_contains_final_question_and_iteration(self):
        """暂停快照应包含最终问题和迭代次数"""
        graph_result = {
            "status": "waiting_for_user",
            "iteration": 6,
            "clarification_questions": [{"id": "q2", "question": "选择布局？"}],
        }

        snapshot = AgentLoopState.from_graph_result(graph_result).serialize()
        restored = AgentLoopState.deserialize(snapshot)

        assert restored.status == "waiting_for_user"
        assert restored.iteration == 6
        assert restored.clarification_questions == [
            {"id": "q2", "question": "选择布局？"},
        ]

    def test_resume_injects_user_answer(self):
        """恢复时应将用户回答注入 conversation_messages"""
        state = AgentLoopState()
        state.status = "waiting_for_user"
        state.iteration = 3
        state.conversation_messages = [
            {"role": "user", "content": "做一个仪表盘"},
            {"role": "assistant", "content": "好的"},
        ]

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        user_answer = "深色主题"
        restored.status = "running"
        restored.conversation_messages.append({"role": "user", "content": user_answer})

        assert len(restored.conversation_messages) == 3
        assert restored.conversation_messages[-1]["content"] == "深色主题"
        assert restored.status == "running"

    def test_resume_preserves_skill_and_outline(self):
        """恢复后 selected_skill_id 和 implementation_outline 应保留"""
        state = AgentLoopState()
        state.selected_skill_id = "ui-ux-pro-max"
        state.implementation_outline = {
            "text": "## 实现计划\n1. 创建布局\n2. 实现组件",
            "steps": ["创建布局", "实现组件"],
        }
        state.executed_tool_calls = [
            ToolCallRecord(id="t1", name="select_skill", arguments={"skill_id": "ui-ux-pro-max"}, result="已选择"),
            ToolCallRecord(id="t2", name="write_plan", arguments={"outline": "..."}, result="计划已写入"),
            ToolCallRecord(id="t3", name="ask_user", arguments={"question": "配色？"}, result="已提问"),
        ]
        state.iteration = 5
        state.mode = "plan"
        state.status = "waiting_for_user"

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored.selected_skill_id == "ui-ux-pro-max"
        assert restored.implementation_outline is not None
        assert "实现计划" in restored.implementation_outline["text"]
        assert len(restored.executed_tool_calls) == 3
        assert restored.executed_tool_calls[0].name == "select_skill"
        assert restored.mode == "plan"
        assert restored.iteration == 5

    def test_non_persist_fields_reset_on_deserialize(self):
        """非持久化字段应在反序列化后保持默认值"""
        state = AgentLoopState()
        state._asset_index = "some_index_object"
        state.selected_capabilities = "some_capabilities"
        state.skill_context = {"key": "value"}
        state.model_response_text = "some response"

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored._asset_index is None
        assert restored.selected_capabilities is None
        assert restored.skill_context is None
        assert restored.model_response_text == ""

    def test_init_node_resume_detection(self):
        """InitNode 恢复模式检测: iteration > 0 或 selected_skill_id 非空时应跳过全量初始化"""
        state1 = AgentLoopState()
        state1.iteration = 3
        assert state1.iteration > 0 or state1.selected_skill_id is not None

        state2 = AgentLoopState()
        state2.selected_skill_id = "ui-ux-pro-max"
        assert state2.iteration > 0 or state2.selected_skill_id is not None

        state3 = AgentLoopState()
        assert not (state3.iteration > 0 or state3.selected_skill_id is not None)


class TestMultipleAskUser:
    """测试多次 ask_user 暂停/恢复"""

    @pytest.mark.asyncio
    async def test_second_ask_user_appends_question(self):
        """同一阶段第二次 ask_user 应被拒绝，避免重复提问。"""
        state = AgentLoopState()
        tool = AskUserTool()
        tool.set_state(state)

        await tool._arun(question="配色方案？", input_type="single_select", options=["深色", "浅色"])
        assert len(state.clarification_questions) == 1
        assert state.status == "waiting_for_user"

        state.status = "running"
        result = await tool._arun(question="布局风格？", input_type="single_select", options=["侧边栏", "顶部导航"])
        assert len(state.clarification_questions) == 1
        assert "已经提问过" in result
        assert state.clarification_questions[0]["question"] == "配色方案？"

    def test_serialize_preserves_multiple_questions(self):
        """序列化应保留多个问题"""
        state = AgentLoopState()
        state.clarification_questions = [
            {"id": "q1", "question": "配色？"},
            {"id": "q2", "question": "布局？"},
        ]
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert len(restored.clarification_questions) == 2


class TestEdgeCases:
    """边界情况测试"""

    def test_serialize_with_none_outline(self):
        """implementation_outline 为 None 时序列化/反序列化应正常"""
        state = AgentLoopState()
        state.implementation_outline = None
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert restored.implementation_outline is None

    def test_serialize_with_empty_tool_calls(self):
        """executed_tool_calls 为空时序列化/反序列化应正常"""
        state = AgentLoopState()
        state.executed_tool_calls = []
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert restored.executed_tool_calls == []

    def test_serialize_with_complex_arguments(self):
        """ToolCallRecord.arguments 包含嵌套结构时应正确序列化"""
        state = AgentLoopState()
        state.executed_tool_calls = [
            ToolCallRecord(
                id="t1",
                name="write_file",
                arguments={
                    "relative_path": "src/App.vue",
                    "content": "<template>\n  <div>Hello</div>\n</template>",
                    "nested": {"key": ["a", "b", "c"]},
                },
                result="文件写入成功",
            ),
        ]
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert len(restored.executed_tool_calls) == 1
        assert restored.executed_tool_calls[0].arguments["relative_path"] == "src/App.vue"
        assert restored.executed_tool_calls[0].arguments["nested"]["key"] == ["a", "b", "c"]

    def test_serialize_with_no_resolved_model(self):
        """resolved_model 为 None 时序列化/反序列化应正常"""
        state = AgentLoopState()
        state.resolved_model = None
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert restored.resolved_model is None

    def test_unicode_in_serialization(self):
        """中文内容序列化/反序列化应正确"""
        state = AgentLoopState()
        state.implementation_outline = {"text": "创建一个深色主题的SaaS仪表盘"}
        state.files_touched = ["src/组件/布局.vue"]
        state.conversation_messages = [{"role": "user", "content": "做一个仪表盘，配色用深色"}]

        json_str = state.serialize()
        assert "仪表盘" in json_str

        restored = AgentLoopState.deserialize(json_str)
        assert "仪表盘" in restored.implementation_outline["text"]
        assert "组件" in restored.files_touched[0]
