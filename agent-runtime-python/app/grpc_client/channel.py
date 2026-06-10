import grpc
from grpc import aio

from app.core.config import settings

_channel: aio.Channel | None = None


async def get_channel() -> aio.Channel:
    global _channel
    if _channel is None:
        options = []
        if settings.agent_internal_secret:
            options.append(("grpc.default_authority", settings.agent_internal_secret))
        _channel = aio.insecure_channel(settings.java_grpc_target, options=options)
    return _channel


async def close_channel():
    global _channel
    if _channel is not None:
        await _channel.close()
        _channel = None
