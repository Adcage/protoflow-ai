from dataclasses import dataclass, field
from typing import Any

from app.agent_loop_vnext.base.state import AgentRunState


@dataclass
class AgentResult:
    """Agent 执行结果。

    status: completed / failed / waiting_for_user
    iteration: 完成时的总迭代次数
    message: Agent 最终回复摘要
    artifacts: 结构化产出（供下游 Pipeline Agent 消费）
    state: 暂停时保存的完整状态（AskUser resume 用）
    agent_name: 执行此结果的 Agent 名称
    error: 失败时的错误信息
    """

    status: str
    iteration: int = 0
    message: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    state: AgentRunState | None = None
    agent_name: str = ""
    error: str | None = None


@dataclass
class PipelineResult:
    """Pipeline 执行结果（Phase 3）。"""

    status: str  # completed / failed / paused
    results: list[AgentResult] = field(default_factory=list)
    failed_at: str | None = None  # 失败的 Agent 名
    paused_at: str | None = None  # 暂停的 Agent 名
