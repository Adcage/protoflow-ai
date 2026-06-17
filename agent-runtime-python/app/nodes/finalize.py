import json
import logging

from app.nodes.base import NodeMetadata, RuntimeNode
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.state import ExecutionState
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.nodes.finalize")


class FinalizeNode(RuntimeNode):
    metadata = NodeMetadata(id="finalize", name="完成处理", description="汇总运行结果并上报平台")

    async def run(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
    ) -> ExecutionState:
        if state.workflow_route == "clarification":
            planning_json = json.dumps(
                {"questions": state.clarification_questions}, ensure_ascii=False
            )
            state.final_summary = (
                f"需要补充以下信息后再生成：\n<planning type=\"clarification\">{planning_json}</planning>"
            )
            success = True
        elif state.workflow_route == "plan_confirmation":
            outline = state.implementation_outline or {}
            planning_json = json.dumps(
                {
                    "outline": {
                        "title": outline.get("title", ""),
                        "summary": outline.get("summary", ""),
                        "steps": outline.get("steps", []),
                        "risks": outline.get("risks", []),
                        "assumptions": outline.get("assumptions", []),
                    }
                },
                ensure_ascii=False,
            )
            state.final_summary = (
                f"已生成实施计划，请确认是否按此方案执行：\n<planning type=\"plan_confirmation\">{planning_json}</planning>"
            )
            success = True
        elif state.workflow_route == "route_only":
            state.final_summary = f"路由完成：{state.planning_decision}"
            success = True
        else:
            has_error_fail = any(
                r.get("status") == "fail" and r.get("severity") == "error"
                for r in state.quality_results
            )
            has_warnings = any(
                r.get("status") in ("warn", "fail") and r.get("severity") == "warning"
                for r in state.quality_results
            )

            success = len(state.errors) == 0 and not has_error_fail
            summary_parts = []
            if state.model_response_text:
                summary_parts.append(f"模型输出 {len(state.model_response_text)} 字")
            if state.files_touched:
                summary_parts.append(f"写入 {len(state.files_touched)} 个文件")
            if state.executed_tool_calls:
                summary_parts.append(f"执行 {len(state.executed_tool_calls)} 次工具调用")

            if state.quality_results:
                pass_count = sum(1 for r in state.quality_results if r.get("status") == "pass")
                warn_count = sum(1 for r in state.quality_results if r.get("status") == "warn")
                fail_count = sum(1 for r in state.quality_results if r.get("status") == "fail")
                summary_parts.append(
                    f"质量检查: {pass_count} pass, {warn_count} warn, {fail_count} fail"
                )
                if has_warnings and not has_error_fail:
                    summary_parts.append("存在质量警告")

            if state.errors:
                summary_parts.append(f"发生 {len(state.errors)} 个错误")

            state.final_summary = "，".join(summary_parts) if summary_parts else "无操作"

        internal_parts = []
        if state.artifact_manifest_path:
            internal_parts.append(f"Manifest: {state.artifact_manifest_path}")
        if state.capability_selection is not None:
            selection = state.capability_selection
            internal_parts.append(f"能力选择: {selection.selection_source}")
            if selection.skill_ids:
                internal_parts.append(f"Skill: {','.join(selection.skill_ids)}")
            if selection.seed_id:
                internal_parts.append(f"Seed: {selection.seed_id}")
            if selection.template_ids:
                internal_parts.append(f"Template: {','.join(selection.template_ids)}")
            if selection.design_system_id:
                internal_parts.append(f"DesignSystem: {selection.design_system_id}")
            if selection.craft_ids:
                internal_parts.append(f"Craft: {','.join(selection.craft_ids)}")
        elif state.selected_skill_id:
            internal_parts.append(f"Skill: {state.selected_skill_id}")
            if state.selected_design_system_id:
                internal_parts.append(f"Design System: {state.selected_design_system_id}")
        state.internal_summary = "，".join(internal_parts) if internal_parts else ""

        failed_checks = [
            r
            for r in state.quality_results
            if r.get("status") == "fail" and r.get("severity") == "error"
        ]
        error_message_parts = list(state.errors)
        if failed_checks:
            check_summary = "; ".join(
                f"{r.get('id', '?')}: {r.get('message', '')}" for r in failed_checks
            )
            error_message_parts.append(f"结构检查失败: {check_summary}")

        if services.platform_client is not None:
            try:
                latency_ms = sum(r.latency_ms for r in state.node_results)
                await services.platform_client.complete_agent_run(
                    agent_run_id=context.agent_run_id,
                    success=success,
                    workspace_path=context.workspace_path,
                    latency_ms=latency_ms,
                    error_message="; ".join(error_message_parts) if error_message_parts else "",
                )
                logger.info("complete_agent_run | success=%s latency_ms=%d", success, latency_ms)
            except Exception as e:
                logger.error("complete_agent_run failed: %s", e, exc_info=True)
                state.errors.append(f"上报运行结果失败: {e}")

        done_message = (
            state.final_summary if success else f"运行失败: {'; '.join(error_message_parts)}"
        )
        await services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.DONE, {"message": done_message})
        )

        logger.info(
            "finalize | success=%s summary=%s %s",
            success,
            state.final_summary,
            state.internal_summary,
        )
        return state
