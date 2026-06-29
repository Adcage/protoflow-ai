"""兼容层：保持现有导入路径可用。

新代码应直接从 app.agent_loop_vnext.base.state 导入。
"""
from app.agent_loop_vnext.base.state import AgentRunState as SingleImplementState
from app.agent_loop_vnext.base.state import LoadedSkill

__all__ = ["SingleImplementState", "LoadedSkill"]
