import json
import logging

from app.agent_loop.state_v2 import (
    WorkflowState,
    WorkflowStateEnvelope,
)
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.state_codec")

_SENSITIVE_KEYS = frozenset(
    {"apiKey", "authorization", "secret", "token", "password", "credential"}
)


def _strip_sensitive_from_dict(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if key in _SENSITIVE_KEYS or key.lower() in {k.lower() for k in _SENSITIVE_KEYS}:
            continue
        elif isinstance(value, dict):
            result[key] = _strip_sensitive_from_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _strip_sensitive_from_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def sanitize_persisted_state(envelope: WorkflowStateEnvelope) -> WorkflowStateEnvelope:
    data = envelope.workflow.model_dump()
    data = _strip_sensitive_from_dict(data)
    sanitized_workflow = WorkflowState.model_validate(data)
    return WorkflowStateEnvelope(
        schema_version=envelope.schema_version,
        workflow=sanitized_workflow,
    )


def _strip_legacy_codegen_type_keys(data: dict) -> dict:
    """递归移除 v2 遗留的 code_gen_type / codeGenType 键。"""
    result = {}
    for key, value in data.items():
        if "code_gen_type" in key.lower() or "CodeGenType" in key or "codegentype" in key.lower():
            continue
        elif isinstance(value, dict):
            result[key] = _strip_legacy_codegen_type_keys(value)
        elif isinstance(value, list):
            result[key] = [
                _strip_legacy_codegen_type_keys(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def encode_loop_state(envelope: WorkflowStateEnvelope) -> str:
    if envelope.schema_version == 2:
        envelope = _migrate_v2_to_v3(envelope)
    sanitized = sanitize_persisted_state(envelope)
    data = json.loads(sanitized.model_dump_json(exclude_none=False))
    data = _strip_legacy_codegen_type_keys(data)
    return json.dumps(data, ensure_ascii=False)


_CODE_GEN_TYPE_TO_ARTIFACT_FORMAT: dict[str, str] = {
    "single_file": "web_single_file",
    "multi-file": "web_multi_file",
    "vue_project": "vue_project",
}


def _migrate_v2_to_v3(envelope: WorkflowStateEnvelope) -> WorkflowStateEnvelope:
    """将 v2 envelope 迁移为 v3：设置 generation_mode，移除旧的 codeGenType 键。"""
    workflow = envelope.workflow
    if workflow.generation_mode is None:
        artifact_type = workflow.artifact_type
        if artifact_type is not None:
            effective = artifact_type.effective
            mapped = _CODE_GEN_TYPE_TO_ARTIFACT_FORMAT.get(effective)
            if mapped is not None:
                workflow.generation_mode = "application"
            else:
                raise AgentRuntimeError(
                    f"v2→v3: 未知的 code_gen_type={effective}，无法迁移",
                    code=AgentErrorCode.STATE_ERROR,
                )
        else:
            routing = workflow.routing
            rec = getattr(routing, "recommended_code_gen_type", None)
            if rec is not None:
                mapped = _CODE_GEN_TYPE_TO_ARTIFACT_FORMAT.get(rec)
                if mapped is not None:
                    workflow.generation_mode = "application"
                else:
                    raise AgentRuntimeError(
                        f"v2→v3: 未知的 recommended_code_gen_type={rec}，无法迁移",
                        code=AgentErrorCode.STATE_ERROR,
                    )
            else:
                workflow.generation_mode = "application"
    return WorkflowStateEnvelope(schema_version=3, workflow=workflow)


def decode_loop_state(raw: str | dict | None) -> WorkflowStateEnvelope:
    if raw is None or raw == "":
        return WorkflowStateEnvelope(
            workflow=WorkflowState(current_mode="route")
        )

    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise AgentRuntimeError(
                f"loopStateJson 不是合法 JSON: {e}",
                code=AgentErrorCode.STATE_ERROR,
            )
    elif isinstance(raw, dict):
        data = raw
    else:
        raise AgentRuntimeError(
            f"不支持的 loopStateJson 类型: {type(raw).__name__}",
            code=AgentErrorCode.STATE_ERROR,
        )

    version = data.get("schema_version")

    if version == 3:
        try:
            envelope = WorkflowStateEnvelope.model_validate(data)
            return envelope
        except Exception as e:
            raise AgentRuntimeError(
                f"v3 状态校验失败: {e}",
                code=AgentErrorCode.STATE_ERROR,
            )

    if version == 2:
        try:
            envelope = WorkflowStateEnvelope.model_validate(data)
            return _migrate_v2_to_v3(envelope)
        except Exception as e:
            raise AgentRuntimeError(
                f"v2 状态校验失败: {e}",
                code=AgentErrorCode.STATE_ERROR,
            )

    if version is None:
        from app.agent_loop.legacy_state_adapter import adapt_legacy_state
        return adapt_legacy_state(data)

    raise AgentRuntimeError(
        f"未知的 loopStateJson schema_version={version}，无法恢复",
        code=AgentErrorCode.STATE_ERROR,
    )
