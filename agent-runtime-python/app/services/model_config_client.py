import httpx

from app.core.exceptions import AgentRuntimeError


class ModelConfigClient:
    """DEPRECATED: Use GrpcPlatformClient instead. This HTTP-based client will be removed in a future version."""

    def __init__(
        self,
        java_platform_base_url: str,
        internal_secret: str,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.java_platform_base_url = java_platform_base_url.rstrip("/")
        self.internal_secret = internal_secret
        self.http_client = http_client

    async def get_runtime_config(self, model_config_id: int, config_version: int) -> dict:
        owns_client = self.http_client is None
        client = self.http_client or httpx.AsyncClient(base_url=self.java_platform_base_url)
        try:
            response = await client.get(
                "/model-config/internal/runtime",
                params={"id": model_config_id, "configVersion": config_version},
                headers={"X-Internal-Secret": self.internal_secret},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                raise AgentRuntimeError(str(payload.get("message", "模型配置获取失败")))
            return payload["data"]
        finally:
            if owns_client:
                await client.aclose()
