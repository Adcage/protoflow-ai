from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ac-ai-code-free-agent-runtime"
    app_env: str = "dev"
    debug: bool = False
    log_level: str = "INFO"

    java_platform_base_url: str = "http://localhost:8700/api"
    agent_runtime_name: str = "python-langgraph"
    redis_url: str = ""
    agent_internal_secret: str = ""

    model_request_timeout: int = 120
    default_model_provider: str = "openai"

    grpc_server_port: int = 9091
    java_grpc_target: str = "localhost:9090"


settings = Settings()
