import logging

from app.prompts.modules import PromptModule

logger = logging.getLogger("app.prompts.registry")


class PromptModuleRegistry:
    """提示词模块注册中心，管理所有 PromptModule 实例的注册和查询。"""

    def __init__(self) -> None:
        self._modules: list[PromptModule] = []

    def register(self, module: PromptModule) -> None:
        """注册一个提示词模块，按注册顺序排列。"""
        existing = self.get_by_id(module.id)
        if existing is not None:
            logger.warning("register | module %s already registered, skipping duplicate", module.id)
            return
        self._modules.append(module)
        logger.debug("register | module=%s category=%s", module.id, module.category)

    def get_by_id(self, module_id: str) -> PromptModule | None:
        """按 ID 查找模块。"""
        for m in self._modules:
            if m.id == module_id:
                return m
        return None

    def modules_by_category(self, category: str) -> list[PromptModule]:
        """按类别筛选模块。"""
        return [m for m in self._modules if m.category == category]

    @property
    def module_ids(self) -> list[str]:
        """返回所有已注册模块的 ID 列表。"""
        return [m.id for m in self._modules]

    def require_many(self, module_ids: tuple[str, ...]) -> list[PromptModule]:
        """按 ID 列表严格解析模块，拒绝缺失或重复。

        返回按 module_ids 顺序排列的模块列表。
        """
        result: list[PromptModule] = []
        seen: set[str] = set()
        for mid in module_ids:
            if mid in seen:
                from app.core.error_codes import AgentErrorCode
                from app.core.exceptions import AgentRuntimeError

                raise AgentRuntimeError(
                    f"Profile 包含重复模块 ID: {mid}",
                    code=AgentErrorCode.STATE_ERROR,
                )
            seen.add(mid)
            module = self.get_by_id(mid)
            if module is None:
                from app.core.error_codes import AgentErrorCode
                from app.core.exceptions import AgentRuntimeError

                raise AgentRuntimeError(
                    f"Profile 引用了不存在的模块: {mid}",
                    code=AgentErrorCode.STATE_ERROR,
                )
            result.append(module)
        return result
