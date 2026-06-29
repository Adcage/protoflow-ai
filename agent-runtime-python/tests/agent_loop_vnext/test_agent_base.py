"""Agent 基类单元测试。"""

import pytest

from app.agent_loop_vnext.base.agent import Agent
from app.agent_loop_vnext.base.state import AgentRunState
from app.agent_loop_vnext.base.result import AgentResult
from app.agent_loop_vnext.shared.tools.base import AgentTool


# ---------------------------------------------------------------------------
# AgentRunState 测试
# ---------------------------------------------------------------------------


def test_agent_state_defaults():
    """AgentRunState 默认值验证。"""
    state = AgentRunState()
    assert state.status == "running"
    assert state.iteration == 0
    assert state.loaded_skills == {}
    assert state.pending_question is None


def test_agent_state_serialize_deserialize():
    """序列化/反序列化往返。"""
    state = AgentRunState(status="waiting_for_user", iteration=3)
    serialized = state.serialize()
    restored = AgentRunState.deserialize(serialized)
    assert restored.status == "waiting_for_user"
    assert restored.iteration == 3


# ---------------------------------------------------------------------------
# AgentResult 测试
# ---------------------------------------------------------------------------


def test_agent_result_defaults():
    """AgentResult 默认值验证。"""
    result = AgentResult(status="completed", iteration=1)
    assert result.status == "completed"
    assert result.message == ""
    assert result.artifacts == {}
    assert result.error is None
    assert result.agent_name == ""


def test_agent_result_with_artifacts():
    """AgentResult 携带 artifacts。"""
    result = AgentResult(
        status="completed",
        iteration=2,
        agent_name="test_agent",
        artifacts={"files": ["a.py"]},
    )
    assert result.agent_name == "test_agent"
    assert result.artifacts["files"] == ["a.py"]


# ---------------------------------------------------------------------------
# Agent ABC 测试
# ---------------------------------------------------------------------------


def test_agent_abstract_class_cannot_be_instantiated():
    """Agent 基类不可直接实例化。"""
    with pytest.raises(TypeError):
        Agent()


class _ConcreteAgent(Agent):
    """测试用 Agent 子类。"""
    name = "test"
    description = "test agent for unit tests"

    def create_tools(self, file_tools, services):
        return []

    def build_system_prompt(self, context, services):
        return "test prompt"


def test_agent_subclass_can_be_instantiated():
    """Agent 子类可实例化。"""
    agent = _ConcreteAgent()
    assert agent.name == "test"
    assert agent.description == "test agent for unit tests"
    assert agent.state.status == "running"
    assert agent.state.iteration == 0


def test_agent_subclass_has_required_methods():
    """Agent 子类必须实现 create_tools 和 build_system_prompt。"""
    agent = _ConcreteAgent()
    # 不调用，只检查方法存在
    assert hasattr(agent, "create_tools")
    assert hasattr(agent, "build_system_prompt")
    assert hasattr(agent, "run")
    assert hasattr(agent, "_stream_model_call")
    assert hasattr(agent, "_execute_tool_calls")
