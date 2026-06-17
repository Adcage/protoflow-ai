import logging
from dataclasses import dataclass

from app.modeling.roles import ModelRole

logger = logging.getLogger("app.modeling.resolver")


@dataclass(frozen=True)
class ResolvedModelConfig:
    role: ModelRole
    provider: str
    model_name: str
    base_url: str
    api_key: str
    model_config_id: int = 0
    config_version: int = 0
    source: str = ""
    billing_mode: str = ""


class ModelResolver:
    def __init__(self, platform_client) -> None:
        self._platform_client = platform_client
        self._bundle: dict[ModelRole, ResolvedModelConfig] = {}

    async def load_bundle(self, context) -> None:
        if self._bundle:
            return
        try:
            bundle = await self._platform_client.resolve_runtime_model_bundle(
                user_id=context.user_id,
                app_id=context.app_id,
                agent_run_id=context.agent_run_id,
                code_gen_type=context.code_gen_type.value,
            )
            self._bundle = bundle
            logger.info("model bundle loaded | roles=%s", list(self._bundle.keys()))
        except Exception as e:
            logger.warning(
                "resolve_runtime_model_bundle failed, falling back to get_model_config: %s", e
            )
            await self._load_fallback(context)

    async def _load_fallback(self, context) -> None:
        model_config_id = context.runtime_options.get("model_config_id", 0)
        config_version = context.runtime_options.get("config_version", 0)
        if model_config_id <= 0:
            raise RuntimeError("No model_config_id provided for fallback")
        config = await self._platform_client.get_model_config(model_config_id, config_version)
        resolved = ResolvedModelConfig(
            role=ModelRole.PRIMARY,
            provider=config.get("provider", ""),
            model_name=config.get("modelName", ""),
            base_url=config.get("baseUrl", ""),
            api_key=config.get("apiKey", ""),
            model_config_id=model_config_id,
            config_version=config_version,
            source="FALLBACK",
            billing_mode="",
        )
        for role in ModelRole:
            self._bundle[role] = resolved

    def resolve(self, role: ModelRole) -> ResolvedModelConfig:
        if role in self._bundle:
            return self._bundle[role]
        if ModelRole.PRIMARY in self._bundle:
            return self._bundle[ModelRole.PRIMARY]
        raise RuntimeError("No runtime model config resolved")
