from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "protoflow-ai-agent-runtime"
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
    agent_tool_history_max_chars: int = 120_000
    agent_tool_result_max_chars: int = 32_000

    # vNext 链路引擎选择: "vnext" | "legacy"
    agent_loop_engine: str = "vnext"

    llm_audit_enabled: bool = True
    llm_audit_dir: str = "../storage/llm_audit"

    # PostgreSQL (pgvector) — RAG 技术文档库
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "protoflow_rag"
    pg_user: str = "postgres"
    pg_password: str = "123456"

    # Knowledge 知识库目录
    knowledge_dir: str = "../knowledge"

    # RAG 参数
    rag_chunk_max_size: int = 1500  # 超长章节二次切分阈值（字符数）
    rag_chunk_overlap: int = 200  # 二次切分重叠字符数
    rag_search_top_k: int = 5  # 检索返回数量
    rag_search_similarity_threshold: float = 0.3  # 最低相似度


settings = Settings()
