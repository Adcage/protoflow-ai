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

    terminal_allowed_commands: str = "npm,npx,pip,python,node"
    terminal_readonly_commands: str = "ls,cat,git,head,tail,find,wc,type,python"
    terminal_default_timeout: int = 30
    terminal_max_timeout: int = 120
    terminal_max_output_bytes: int = 10240

    agent_loop_max_iterations: int = 50
    agent_loop_max_mode_switches: int = 6
    agent_tool_history_max_chars: int = 40_000
    agent_tool_result_max_chars: int = 8_000

    llm_audit_enabled: bool = True
    llm_audit_dir: str = "../storage/llm_audit"


settings = Settings()
