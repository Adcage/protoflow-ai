"""Agent Loop 链路构建策略。

每种 generation_mode 对应一个 LoopStrategy 子类，负责完整定义一条
agent loop 链路（system prompt、tools、RuntimeServices）如何构建。
"""

from app.agent_loop_vnext.loops.base import LoopStrategy, get_loop_strategy
from app.agent_loop_vnext.loops.implement_loop import ImplementorLoop
from app.agent_loop_vnext.loops.playground_loop import PlaygroundLoop

__all__ = ["LoopStrategy", "get_loop_strategy", "ImplementorLoop", "PlaygroundLoop"]