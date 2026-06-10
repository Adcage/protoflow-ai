import logging

from grpc import aio

from app.grpc import common_pb2
from app.grpc import tool_service_pb2
from app.grpc import tool_service_pb2_grpc
from app.grpc_client.channel import get_channel

logger = logging.getLogger("app.grpc_client.tool_client")


def _map_code_gen_type(code_gen_type: str) -> int:
    mapping = {
        "single_file": common_pb2.SINGLE_FILE,
        "multi-file": common_pb2.MULTI_FILE,
        "vue_project": common_pb2.VUE_PROJECT,
    }
    return mapping.get(code_gen_type, common_pb2.VUE_PROJECT)


class GrpcToolClient:
    def __init__(self, app_id: int, code_gen_type: str):
        self._app_id = app_id
        self._code_gen_type = code_gen_type
        self._stub: tool_service_pb2_grpc.ToolServiceStub | None = None

    async def _get_stub(self) -> tool_service_pb2_grpc.ToolServiceStub:
        if self._stub is None:
            channel = await get_channel()
            self._stub = tool_service_pb2_grpc.ToolServiceStub(channel)
        return self._stub

    async def read_file(self, relative_path: str) -> str:
        stub = await self._get_stub()
        request = tool_service_pb2.ReadFileRequest(
            app_id=self._app_id,
            code_gen_type=_map_code_gen_type(self._code_gen_type),
            relative_path=relative_path,
        )
        response = await stub.ReadFile(request)
        return response.content

    async def write_file(self, relative_path: str, content: str) -> str:
        stub = await self._get_stub()
        request = tool_service_pb2.WriteFileRequest(
            app_id=self._app_id,
            code_gen_type=_map_code_gen_type(self._code_gen_type),
            relative_path=relative_path,
            content=content,
        )
        response = await stub.WriteFile(request)
        return response.message

    async def modify_file(self, relative_path: str, old_content: str, new_content: str) -> str:
        stub = await self._get_stub()
        request = tool_service_pb2.ModifyFileRequest(
            app_id=self._app_id,
            code_gen_type=_map_code_gen_type(self._code_gen_type),
            relative_path=relative_path,
            old_content=old_content,
            new_content=new_content,
        )
        response = await stub.ModifyFile(request)
        return response.message

    async def delete_file(self, relative_path: str) -> str:
        stub = await self._get_stub()
        request = tool_service_pb2.DeleteFileRequest(
            app_id=self._app_id,
            code_gen_type=_map_code_gen_type(self._code_gen_type),
            relative_path=relative_path,
        )
        response = await stub.DeleteFile(request)
        return response.message

    async def read_dir(self, relative_path: str = ".") -> str:
        stub = await self._get_stub()
        request = tool_service_pb2.ReadDirRequest(
            app_id=self._app_id,
            code_gen_type=_map_code_gen_type(self._code_gen_type),
            relative_path=relative_path,
        )
        response = await stub.ReadDir(request)
        return response.entries
