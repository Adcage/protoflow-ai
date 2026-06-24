"""Prompt Profile 定义：每个模式只加载明确列出的模块。

替代全量组合 + 黑名单过滤，让 Prompt 组合完全可预测。
"""

from __future__ import annotations

from typing import Any

PROMPT_PROFILES: dict[str, tuple[str, ...]] = {
    "route_initial": (
        "runtime_boundary",
        "safety_injection_resistance",
        "production_security",
        "test_mode_info",
        "route_initial",
        "tool_list",
        "anti_roleplay",
    ),
    "route_after_plan": (
        "runtime_boundary",
        "safety_injection_resistance",
        "production_security",
        "test_mode_info",
        "route_after_plan",
        "tool_list",
        "anti_roleplay",
    ),
    "route_after_implement": (
        "runtime_boundary",
        "safety_injection_resistance",
        "production_security",
        "test_mode_info",
        "route_after_implement",
        "tool_list",
        "anti_roleplay",
    ),
    "route_after_validate": (
        "runtime_boundary",
        "safety_injection_resistance",
        "production_security",
        "test_mode_info",
        "route_after_validate",
        "tool_list",
        "anti_roleplay",
    ),
    "plan": (
        "runtime_boundary",
        "safety_injection_resistance",
        "production_security",
        "test_mode_info",
        "project_rules",
        "plan_workflow",
        "plan_spec",
        "skill_context",
        "task_context",
        "tool_list",
        "anti_roleplay",
    ),
    "implement": (
        "runtime_boundary",
        "safety_injection_resistance",
        "production_security",
        "test_mode_info",
        "project_rules",
        "implement_workflow",
        "validate_feedback",
        "artifact_output_contract",
        "output_contract",
        "skill_context",
        "task_context",
        "tool_list",
        "anti_roleplay",
    ),
    "validate": (
        "runtime_boundary",
        "safety_injection_resistance",
        "production_security",
        "test_mode_info",
        "project_rules",
        "validate_workflow",
        "task_context",
        "tool_list",
        "anti_roleplay",
    ),
}


def resolve_profile_module_ids(
    profile_id: str,
    generation_mode: str | None = None,
    mode_registry: Any | None = None,
) -> tuple[str, ...]:
    """根据 profile_id 和 generationMode 动态解析模块 ID 列表。

    保留共享基础 Profile，并按确定的 generationMode 追加对应模式模块。
    顺序为公共基础模块 → 模式特定模块 → task/tool/anti_roleplay。

    generation_mode="unresolved" 时只允许通用 Plan 澄清模块，
    Validate 不接受 unresolved。
    """
    base_ids = PROMPT_PROFILES.get(profile_id)
    if base_ids is None:
        from app.core.error_codes import AgentErrorCode
        from app.core.exceptions import AgentRuntimeError

        raise AgentRuntimeError(
            f"Profile {profile_id} 不存在",
            code=AgentErrorCode.STATE_ERROR,
        )

    if generation_mode == "unresolved":
        if profile_id == "plan":
            base_list = list(base_ids)
            insert_pos = _find_insert_position(base_list)
            base_list.insert(insert_pos, "generation_mode_clarification")
            return tuple(base_list)
        from app.core.error_codes import AgentErrorCode
        from app.core.exceptions import AgentRuntimeError

        raise AgentRuntimeError(
            "Validate 不接受 unresolved generationMode",
            code=AgentErrorCode.STATE_ERROR,
        )

    if generation_mode is None or mode_registry is None:
        return base_ids

    if not mode_registry.is_registered(generation_mode):
        return base_ids

    definition = mode_registry.require(generation_mode)

    if profile_id == "plan":
        mode_module_ids = definition.plan_prompt_module_ids
    elif profile_id == "validate":
        if generation_mode == "unresolved":
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                "Validate 不接受 unresolved generationMode",
                code=AgentErrorCode.STATE_ERROR,
            )
        mode_module_ids = definition.validate_prompt_module_ids
    else:
        return base_ids

    if not mode_module_ids:
        return base_ids

    base_list = list(base_ids)
    insert_pos = _find_insert_position(base_list)
    for mid in mode_module_ids:
        if mid not in base_list:
            base_list.insert(insert_pos, mid)
            insert_pos += 1

    return tuple(base_list)


def _find_insert_position(base_list: list[str]) -> int:
    """找到模式模块的插入位置：在 task_context 之后、tool_list 之前。"""
    try:
        return base_list.index("tool_list")
    except ValueError:
        return len(base_list)
