import logging
import time
import uuid

import grpc
from grpc import aio

from app.core.context import set_trace_id, set_agent_run_id
from app.core.metrics import agent_request_duration_seconds, agent_requests_total

logger = logging.getLogger("app.grpc_server.interceptor")


class RequestLoggingInterceptor(aio.ServerInterceptor):
    async def intercept_service(
        self,
        continuation,
        handler_call_details,
    ):
        method = handler_call_details.method
        method_short = method.split("/")[-1] if "/" in method else method
        start = time.perf_counter()

        incoming_metadata = handler_call_details.invocation_metadata
        trace_id = _extract_metadata(incoming_metadata, "x-trace-id") or str(uuid.uuid4())
        agent_run_id_value = _extract_metadata(incoming_metadata, "x-agent-run-id") or ""

        set_trace_id(trace_id)
        set_agent_run_id(agent_run_id_value)

        logger.info("gRPC request start | method=%s agentRunId=%s", method, agent_run_id_value or "-")

        handler = await continuation(handler_call_details)

        if handler is None:
            _record_completion(method_short, start, "no_handler")
            return handler

        if handler.unary_unary:
            original = handler.unary_unary

            async def wrapped_unary(request, context):
                try:
                    response = await original(request, context)
                    _record_completion(method_short, start, "ok")
                    return response
                except Exception as e:
                    _record_completion(method_short, start, "error")
                    raise

            return _wrap_handler(handler, unary_unary=wrapped_unary)

        if handler.unary_stream:
            original_stream = handler.unary_stream

            async def wrapped_stream(request, context):
                try:
                    async for event in original_stream(request, context):
                        yield event
                    _record_completion(method_short, start, "ok")
                except Exception as e:
                    _record_completion(method_short, start, "error")
                    raise

            return _wrap_handler(handler, unary_stream=wrapped_stream)

        _record_completion(method_short, start, "ok")
        return handler


def _record_completion(method: str, start: float, status: str) -> None:
    elapsed = time.perf_counter() - start
    elapsed_ms = elapsed * 1000

    agent_request_duration_seconds.labels(method=method).observe(elapsed)
    agent_requests_total.labels(method=method, code_gen_type="").inc()

    if status == "ok":
        logger.info("gRPC request end | method=%s duration_ms=%.0f", method, elapsed_ms)
    elif status == "error":
        logger.error("gRPC request error | method=%s duration_ms=%.0f", method, elapsed_ms)
    else:
        logger.info("gRPC request end | method=%s duration_ms=%.0f (%s)", method, elapsed_ms, status)


def _wrap_handler(handler, unary_unary=None, unary_stream=None):
    return _RpcMethodHandler(
        unary_unary=unary_unary or handler.unary_unary,
        unary_stream=unary_stream or handler.unary_stream,
        stream_unary=handler.stream_unary,
        stream_stream=handler.stream_stream,
        request_deserializer=handler.request_deserializer,
        response_serializer=handler.response_serializer,
    )


class _RpcMethodHandler(grpc.RpcMethodHandler):
    def __init__(self, *, unary_unary=None, unary_stream=None,
                 stream_unary=None, stream_stream=None,
                 request_deserializer=None, response_serializer=None):
        self._unary_unary = unary_unary
        self._unary_stream = unary_stream
        self._stream_unary = stream_unary
        self._stream_stream = stream_stream
        self.request_deserializer = request_deserializer
        self.response_serializer = response_serializer

    @property
    def request_streaming(self):
        return self._stream_unary is not None or self._stream_stream is not None

    @property
    def response_streaming(self):
        return self._unary_stream is not None or self._stream_stream is not None

    @property
    def unary_unary(self):
        return self._unary_unary

    @property
    def unary_stream(self):
        return self._unary_stream

    @property
    def stream_unary(self):
        return self._stream_unary

    @property
    def stream_stream(self):
        return self._stream_stream


def _extract_metadata(metadata, key: str) -> str | None:
    if metadata is None:
        return None
    for m in metadata:
        if m.key == key:
            return m.value
    return None
