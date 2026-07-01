import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest

from app.api.router import api_router
from app.core.config import settings
from app.core.exception_handlers import (
    agent_runtime_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.core.exceptions import AgentRuntimeError
from app.core.llm_audit import get_llm_audit_writer
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.response import success
from app.grpc_client.channel import close_channel, get_channel
from app.grpc_server.server import create_grpc_server

logger = logging.getLogger("app.main")


def _validate_config() -> None:
    if not settings.agent_internal_secret:
        logger.warning("agent_internal_secret is not set; gRPC calls to Java may fail")
    if not settings.java_grpc_target:
        logger.warning("java_grpc_target is not set; gRPC channel to Java will not work")


async def _check_grpc_channel() -> str:
    try:
        channel = await get_channel()
        state = channel.get_state()
        if state.name == "READY" or state.name == "IDLE":
            return "connected"
        return f"state={state.name}"
    except Exception as e:
        return f"error={e}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_config()

    grpc_server = await create_grpc_server()
    await grpc_server.start()
    logger.info("gRPC server started on port %s", settings.grpc_server_port)

    audit_writer = get_llm_audit_writer()
    audit_writer.start()

    # 启动时初始化 RAG 服务
    from app.runtime.orchestrator import init_rag_service
    await init_rag_service()

    logger.info(
        "application started | runtime=%s env=%s", settings.agent_runtime_name, settings.app_env
    )

    yield

    logger.info("application shutting down...")

    from app.runtime.orchestrator import close_rag_service
    await close_rag_service()

    await audit_writer.stop()
    await grpc_server.stop(grace=5)
    logger.info("gRPC server stopped")
    await close_channel()
    logger.info("gRPC channel closed, shutdown complete")


def create_app() -> FastAPI:
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.add_exception_handler(AgentRuntimeError, agent_runtime_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_router)

    # 知识库管理 API
    try:
        from app.api.knowledge_admin import router as knowledge_admin_router
        app.include_router(knowledge_admin_router)
    except ImportError as e:
        logger.warning("知识库管理 API 注册失败: %s", e)

    @app.get("/health", tags=["health"])
    async def health(request: Request) -> dict:
        grpc_status = await _check_grpc_channel()
        return success(
            data={
                "status": "ok",
                "runtime": settings.agent_runtime_name,
                "grpc_channel": grpc_status,
            },
            request=request,
        )

    @app.get("/health/ready", tags=["health"])
    async def readiness(request: Request):
        checks: dict[str, str] = {}
        ok = True

        grpc_status = await _check_grpc_channel()
        checks["grpc_channel"] = grpc_status
        if grpc_status != "connected":
            ok = False

        if not settings.agent_internal_secret:
            checks["internal_secret"] = "missing"
            ok = False
        else:
            checks["internal_secret"] = "configured"

        if ok:
            return success(data={"status": "ready", "checks": checks}, request=request)
        return JSONResponse(
            status_code=503,
            content={
                "code": 5030,
                "message": "Not Ready",
                "data": {"status": "not_ready", "checks": checks},
            },
        )

    @app.get("/metrics", tags=["monitoring"])
    async def metrics():
        return PlainTextResponse(
            generate_latest(), media_type="text/plain; version=0.0.4; charset=utf-8"
        )

    if settings.app_env != "prod":

        @app.get("/debug/llm-audit/status", tags=["debug"])
        async def llm_audit_status(request: Request):
            base_dir = Path(settings.llm_audit_dir)
            if not base_dir.is_absolute():
                base_dir = base_dir.resolve()
            existing_runs = []
            if base_dir.exists():
                date_dirs = sorted(
                    (d for d in base_dir.iterdir() if d.is_dir()),
                    reverse=True,
                )
                for date_dir in date_dirs[:7]:
                    for run_dir in sorted(date_dir.iterdir(), reverse=True):
                        if run_dir.is_dir():
                            existing_runs.append(f"{date_dir.name}/{run_dir.name}")
                            if len(existing_runs) >= 20:
                                break
                    if len(existing_runs) >= 20:
                        break
            return {
                "llm_audit_enabled": settings.llm_audit_enabled,
                "llm_audit_dir": str(base_dir),
                "recent_runs": existing_runs,
            }

        @app.get("/debug/llm-audit/{agent_run_id}", tags=["debug"])
        async def llm_audit_check(agent_run_id: str, request: Request):
            base_dir = Path(settings.llm_audit_dir)
            if not base_dir.is_absolute():
                base_dir = base_dir.resolve()
            target_dir = None
            if base_dir.exists():
                for date_dir in sorted(base_dir.iterdir(), reverse=True):
                    if not date_dir.is_dir():
                        continue
                    for run_dir in date_dir.iterdir():
                        if run_dir.is_dir() and (
                            run_dir.name == agent_run_id
                            or run_dir.name.endswith(f"_{agent_run_id}")
                        ):
                            target_dir = run_dir
                            break
                    if target_dir:
                        break
            if not target_dir:
                return {"found": False, "agent_run_id": agent_run_id}
            files = []
            for f in sorted(target_dir.iterdir()):
                files.append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size if f.is_file() else 0,
                    }
                )
            return {"found": True, "agent_run_id": agent_run_id, "path": str(target_dir), "files": files}

    return app


app = create_app()
