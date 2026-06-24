"""Phase 3 Skill 选择工具。

旧版 ``select_skill`` 工具仅设置 ``selected_skill_id`` 字符串；Phase 3 后该工具改为
薄兼容入口，委托 ``ChooseSkillTool`` 通过状态机写入结构化 CapabilityBundleRef，
包括 digest 和 loaded_resources。Seed/Craft 永远不可启用。
"""

import logging
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("app.agent_loop.tools.select_skill")


class SelectSkillInput(BaseModel):
    skill_id: str = Field(
        description="要选择的 Skill ID，如 dashboard、landing-page、web-prototype、frontend-design"
    )
    reason: str = Field(default="", description="选择原因")
    loaded_resources: list[str] = Field(
        default_factory=list,
        description="本次会话内已加载的资源相对路径列表",
    )


class SelectSkillTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "select_skill"
    description: str = (
        "从可用 Skill 列表中选择一个最适合当前任务的 Skill。"
        "Phase 3 流程：选择会同时写入 CapabilityBundleRef（含 content_digest），"
        "并把当前 PlanStage 推进到下一阶段。"
    )
    args_schema: Type[BaseModel] = SelectSkillInput

    _state: object | None = None
    _delegate: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def set_delegate(self, delegate: object) -> None:
        self._delegate = delegate

    def _run(self, skill_id: str, reason: str = "", loaded_resources: list[str] | None = None) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        skill_id: str,
        reason: str = "",
        loaded_resources: list[str] | None = None,
    ) -> str:
        if self._state is None:
            return "错误：未绑定 AgentLoopState"

        if self._delegate is None:
            return "错误：未配置 ChooseSkillTool delegate，请先通过 init 节点注入"

        # delegate 已是绑定到 ChooseSkillTool 实例的 _arun
        # 显式按 kwargs 转发以避免 self/state 重复传入
        return await self._delegate(
            skill_id=skill_id,
            reason=reason,
            loaded_resources=loaded_resources or [],
        )
