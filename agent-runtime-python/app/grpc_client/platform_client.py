import logging

from grpc import aio

from app.grpc import platform_service_pb2
from app.grpc import platform_service_pb2_grpc
from app.grpc_client.channel import get_channel

logger = logging.getLogger("app.grpc_client.platform_client")


class GrpcPlatformClient:
    def __init__(self):
        self._stub: platform_service_pb2_grpc.PlatformServiceStub | None = None

    async def _get_stub(self) -> platform_service_pb2_grpc.PlatformServiceStub:
        if self._stub is None:
            channel = await get_channel()
            self._stub = platform_service_pb2_grpc.PlatformServiceStub(channel)
        return self._stub

    async def get_model_config(self, model_config_id: int, config_version: int) -> dict:
        stub = await self._get_stub()
        request = platform_service_pb2.GetModelConfigRequest(
            model_config_id=model_config_id,
            config_version=config_version,
        )
        response = await stub.GetModelConfig(request)
        return {
            "provider": response.provider,
            "modelName": response.model_name,
            "baseUrl": response.base_url,
            "apiKey": response.api_key,
        }

    async def build_vue_project(self, app_id: int) -> dict:
        stub = await self._get_stub()
        request = platform_service_pb2.BuildVueProjectRequest(app_id=app_id)
        response = await stub.BuildVueProject(request)
        return {
            "success": response.success,
            "distPath": response.dist_path,
            "installLog": response.install_log,
            "buildLog": response.build_log,
            "errorMessage": response.error_message,
        }

    async def deploy_app(self, app_id: int, user_id: int) -> dict:
        stub = await self._get_stub()
        request = platform_service_pb2.DeployAppRequest(app_id=app_id, user_id=user_id)
        response = await stub.DeployApp(request)
        return {"success": response.success, "url": response.url, "errorMessage": response.error_message}

    async def complete_agent_run(
        self,
        agent_run_id: int,
        success: bool,
        workspace_path: str = "",
        latency_ms: int = 0,
        error_message: str = "",
    ) -> bool:
        stub = await self._get_stub()
        request = platform_service_pb2.CompleteAgentRunRequest(
            agent_run_id=agent_run_id,
            success=success,
            workspace_path=workspace_path,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        response = await stub.CompleteAgentRun(request)
        return response.ok

    async def create_app_version(
        self, app_id: int, agent_run_id: int, source_path: str, build_path: str
    ) -> int:
        stub = await self._get_stub()
        request = platform_service_pb2.CreateAppVersionRequest(
            app_id=app_id,
            agent_run_id=agent_run_id,
            source_path=source_path,
            build_path=build_path,
        )
        response = await stub.CreateAppVersion(request)
        return response.version_id

    async def get_chat_history(self, session_id: int, limit: int = 50) -> list[dict]:
        stub = await self._get_stub()
        request = platform_service_pb2.GetChatHistoryRequest(session_id=session_id, limit=limit)
        response = await stub.GetChatHistory(request)
        return [{"id": e.id, "role": e.role, "content": e.content} for e in response.entries]

    async def get_app_detail(self, app_id: int) -> dict:
        stub = await self._get_stub()
        request = platform_service_pb2.GetAppDetailRequest(app_id=app_id)
        response = await stub.GetAppDetail(request)
        return {
            "id": response.id,
            "name": response.name,
            "description": response.description,
            "codeGenType": response.code_gen_type,
            "userId": response.user_id,
        }
