from app.modeling.roles import ModelRole

DEFAULT_NODE_MODEL_ROLES: dict[str, ModelRole] = {
    "classify_task": ModelRole.LIGHT,
    "resolve_model": ModelRole.LIGHT,
    "compose_prompt": ModelRole.LIGHT,
    "call_model": ModelRole.PRIMARY,
    "finalize": ModelRole.LIGHT,
}


class ModelPolicy:
    def role_for_node(self, node_id: str) -> ModelRole:
        return DEFAULT_NODE_MODEL_ROLES.get(node_id, ModelRole.PRIMARY)
