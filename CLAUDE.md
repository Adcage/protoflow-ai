# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

protoflow-ai 是基于 Spring Boot 3.5.5 + Vue 3 + Python Agent Runtime 的 AI 驱动的创意创作平台。三层架构通过 gRPC 互连：

- **Java 后端**（端口 8700 HTTP / 9090 gRPC）：平台控制层 — 用户、应用、会话、模型配置、AgentRun、AppVersion、权限、限流、构建部署、文件工具、gRPC bridge
- **Python Agent Runtime**（端口 8000 HTTP / 9091 gRPC）：所有 AI 核心能力 — 模型调用、Agent Loop、提示词增强、代码生成、工具调用决策、AI 路由
- **Vue 3 前端**（端口 5173）：Ant Design Vue + Pinia + Axios，SSE 流式接收 AI 响应

## AI Runtime 边界（强制）

### vNext 引擎优先（强制）

Python Agent Runtime 当前维护**两套** Agent Loop 引擎，但以下规则必须遵守：

- **所有新增 AI 逻辑必须在 `agent_loop_vnext/` 中实现**，包括新节点、新工具、新 agent、状态变更
- `agent_loop/`（legacy 引擎）仅作**参考用途**，禁止在其上新增功能或修改现有逻辑
- 新增功能的入口点应在 `agent_loop_vnext/runner.py`（`SingleImplementLoopRunner`）中扩展，而非创建新的独立引擎
- 如果新增功能需要与 legacy 引擎共享代码（如工具定义、事件模型），应提取到 `agent_loop_vnext/shared/` 或 `tools/`、`events/` 等公共目录，而非 `agent_loop/`

### Python 负责所有 AI 核心能力

所有新增或维护的 AI 核心功能必须放在 `agent-runtime-python/` 中，并优先在 `agent_loop_vnext/` 中开发，包括：

- 模型调用、模型流式响应、AI 路由、提示词增强、Agent Loop、工具调用决策
- 代码生成、代码修改、对话式生成、工作流式 AI 编排
- 需要 `SystemMessage`、`UserMessage`、LLM function/tool calling、LangGraph/LangChain 推理的能力

### Java 只保留平台层和 Python 需要调用的能力

Java 后端可以继续维护：

- 用户、应用、会话、模型配置、AgentRun、AppVersion、权限、限流、日志、缓存
- 文件读写、目录读取、项目构建、部署、截图、对象存储、工作区路径管理
- `GrpcPythonAgentRuntime`、`GrpcPlatformService`、`GrpcToolService`、`GrpcInternalAuthInterceptor`
- SSE/API 入口和 gRPC bridge，但实际 AI 推理必须委托 Python
- `ai/model/message` 这类 SSE/协议 DTO，只要不负责模型推理，可以继续使用

### Java AI legacy 禁止新增入口

- 禁止新增 Java LangChain4j `AiServices`、`@SystemMessage`、`@UserMessage`、模型推理 Bean、Java agent workflow
- 禁止让 `java-agent`、`WorkflowCodeGeneratorService`、Java prompt enhancer 或 Java AI routing 成为可用入口或 fallback
- 旧 Java AI 文件在 `legacy/` 包中，标记 `@Deprecated`，不得新增调用方
- 如需恢复或新增 AI 能力，必须在 Python Runtime 实现，再由 Java 通过 gRPC bridge 调用

## 构建/测试/开发命令

### 后端（backend-java/ 目录执行）

```bash
mvn spring-boot:run                    # 启动开发服务器
mvn clean package                      # 构建项目
mvn test                               # 运行所有测试
mvn test -Dtest=UserServiceTest        # 运行单个测试类
mvn test -Dtest=UserServiceTest#testUserRegister  # 运行单个测试方法
mvn clean package -DskipTests          # 跳过测试构建
```

### 前端（frontend-vue/ 目录执行）

```bash
npm install                            # 安装依赖
npm run dev                            # 启动开发服务器 (http://localhost:5173)
npm run build                          # 类型检查 + 构建
npm run build-only                     # 仅构建（不进行类型检查）
npm run type-check                     # TypeScript 类型检查 (vue-tsc)
npm run lint                           # ESLint 检查并自动修复
npm run format                         # Prettier 格式化 src/ 目录
npm run openapi                        # 从后端 OpenAPI 生成 TypeScript 类型和 API 函数
```

### Python Agent Runtime（agent-runtime-python/ 目录执行）

```bash
pip install -e ".[dev]"              # 安装依赖（含开发依赖）
uvicorn app.main:app --reload --port 8000  # 启动开发服务器（FastAPI + gRPC）
pytest                              # 运行所有测试
pytest tests/test_xxx.py            # 运行单个测试文件
ruff check .                        # lint 检查
ruff format .                       # 格式化
python scripts/generate_grpc.py     # 从 proto 文件重新生成 gRPC 代码
```

## 核心架构

### 双引擎 Agent Loop（vNext 是唯一活跃开发引擎）

Python Agent Runtime 有两套 Agent Loop 引擎，通过 `agent_loop_engine` 配置切换（默认 `vnext`）：

**vNext 引擎**（`agent_loop_vnext/`）— **当前默认引擎，所有新功能在此开发**：
- `SingleImplementLoopRunner`：单循环体，model → tool_calls → execute → feedback → loop
- `SingleImplementState`：最小状态（status + iteration count）
- 4 个文件工具：View、Create、StrReplace、Insert；通过 `shared/tools/base.py` 的 `AgentTool` 基类扩展
- `shared/history.py`：消息历史构建器，提供 `HistoryBuilder` 将事件历史格式化为 LLM 消息
- 架构极简，职责清晰：runner 控制循环 → agent 生成响应 → tools 执行操作 → state 记录进度
- 适用于单文件/多文件/项目级代码生成场景

**Legacy 引擎**（`agent_loop/`）— **冻结，仅作参考，禁止新增功能**：
- 6 个图节点：init → route_step → plan_step/implement_step/validate_step → finish
- `AgentLoopState`（21KB 复杂状态）+ transition guards + phase reporting
- 13 个工具文件（decide_route、plan_tools、run_checks 等）
- 当前保留为稳态参考，不在此目录新增或修改代码

### Capabilities 资产系统

`capabilities/` 目录实现了一套文件驱动的资产发现与加载系统，5 种资产类型遵循统一模式（loader → registry → selector → prompt_module → types）：

| 资产类型 | 用途 |
|---------|------|
| `craft/` | 工艺定义（applies_to + priority 匹配） |
| `design_systems/` | 设计系统资产 |
| `seeds/` | 种子能力（含 applier 应用逻辑） |
| `skills/` | 技能定义 |
| `templates/` | 模板资产 |

`common/` 提供共享基础设施：frontmatter 解析、资产索引、manifest 处理、路径工具。

### gRPC 双向通信

**Java → Python**（gRPC Server，4 个 RPC 方法）：

| RPC 方法 | 类型 | 说明 |
|---------|------|------|
| `StreamGenerate` | unary-stream | 代码生成流式主入口 |
| `StreamModify` | unary-stream | 代码修改流式入口 |
| `ValidatePrompt` | unary-unary | 提示词校验（空值、长度≤2000、注入检测） |
| `EnhancePrompt` | unary-unary | 提示词增强 |

**Python → Java**（gRPC Client）：

| 客户端 | 目标服务 | 用途 |
|-------|---------|------|
| `GrpcPlatformClient` | Java PlatformService :9090 | 模型配置、构建、部署、AgentRun 完成、AppVersion、聊天历史 |
| `GrpcToolClient` | Java ToolService :9090 | 文件读写删改（Python 本地文件工具不可用时的降级方案） |

- 所有 gRPC 调用必须携带 `x-internal-secret` metadata 认证
- `get_model_config` 自动重试 2 次（间隔 1s），构建/部署操作不重试
- 流式方法的每个事件必须携带 `agent_run_id` 和递增 `seq`

### 工具执行架构

| 工具类型 | 执行位置 | 说明 |
|---------|---------|------|
| 文件操作（read_file, write_file, modify_file, delete_file, read_dir） | Python 直接执行 | Workspace 类提供路径穿越保护 |
| 终端命令（terminal_tools） | Python 直接执行 | 受 `terminal_allowed_commands` 白名单限制 |
| 构建/部署（build_vue_project, deploy_app） | gRPC → Java | 涉及 Node.js 环境、对象存储、权限管理 |
| 平台状态（complete_agent_run, create_app_version） | gRPC → Java | 数据库持久化由 Java 统一管理 |

### 数据存储规范

- **Python 不直接连接数据库**，所有持久化通过 gRPC 桥接到 Java
- **AI 对话记录**：Python 通过 `GrpcPlatformClient.get_chat_history()` 读取历史，通过 `CompleteAgentRun` 上报运行结果
- **业务指标**（token 用量、模型名、耗时）：请求完成后通过 `CompleteAgentRun` 上报，Java 存入 `agent_run` 表
- **运维指标**（QPS、延迟 P99、错误率）：Python 暴露 `/metrics` 端点，Prometheus 直接抓取

### 模型配置获取

Java 发起 gRPC 请求时携带 `model_config_id` + `config_version`，Python 通过 `GrpcPlatformClient.get_model_config()` 回调 Java 获取完整配置（provider, modelName, baseUrl, apiKey），再用 `ChatModelFactory.create()` 构建模型实例。Python 不存储模型配置，只消费。

## 后端代码风格（Java 17 + Spring Boot）

### 目录结构

```
backend-java/src/main/java/com/adcage/acaicodefree/
├── ai/              # SSE/协议 DTO（仅 model/message，禁止新增 AI 推理入口）
├── annotation/      # 自定义注解 (@AuthCheck, @RateLimit)
├── aop/             # AOP 切面 (AuthInterceptor, LogInterceptor, RateLimitAspect)
├── common/          # 通用类 (BaseResponse, ErrorCode, ResultUtils, PageRequest, DeleteRequest)
├── config/          # 配置类 (CorsConfig, JsonConfig, WebMvcConfig)
├── constant/        # 常量接口 (UserConstant, AppConstant)
├── controller/      # 控制器层
├── core/            # 核心业务编排（Facade + 策略 + 模板方法模式）
│   ├── build/       # 项目构建服务 (VueProjectBuildService)
│   ├── handler/     # 流处理器策略 (SimpleTextStreamHandler, JsonMessageStreamHandler)
│   ├── memory/      # AI 聊天记忆加载 (ChatMemoryLoader)
│   ├── parser/      # 代码解析策略 (SingleFileParser, MultiFileParser)
│   └── saver/       # 文件保存模板方法 (AbstractCodeFileSaver 及子类)
├── exception/       # 异常 (BusinessException, GlobalExceptionHandler, ThrowUtils)
├── generator/       # MyBatis-Flex 代码生成器（独立 main 方法）
├── grpc/            # Java <-> Python gRPC bridge、PlatformService、ToolService
├── legacy/          # 已弃用 Java AI 代码（@Deprecated，禁止新增调用方）
│   ├── ai/          # 旧 AI 服务工厂、路由、代码生成器
│   ├── config/      # 旧模型配置
│   ├── core/        # 旧 Facade、解析器、记忆
│   ├── runtime/     # 旧运行时实现
│   └── workflow/    # 旧工作流（node/state/tool/controller）
├── manager/         # 管理器 (CosManager)
├── mapper/          # MyBatis-Flex Mapper 接口（继承 BaseMapper）
├── model/
│   ├── dto/         # 请求 DTO（按领域分子包: app/, chat/, user/）
│   ├── entity/      # 数据库实体 (@Table, @Id, @Column)
│   ├── enums/       # 枚举 (CodeGenTypeEnum, UserRoleEnum)
│   └── vo/          # 响应 VO（按领域分子包）
├── ratelimit/       # 限流（@RateLimit 注解 + AOP 切面）
├── runtime/         # 代码生成运行时路由（默认 python-agent，java-agent 已禁用）
├── scheduler/       # 定时任务 (CoverGenerationScheduler)
├── service/         # 服务层接口 + impl/ 实现
├── storage/         # 文件存储策略（FileStorageStrategy → COS/Local 实现）
└── utils/           # 工具类 (CacheKeyUtils, WebDriverFactory, WebScreenshotUtils)
```

### 命名与编码规范

- **类名** PascalCase：`UserController`, `BusinessException`
- **方法/变量** camelCase：`userRegister`, `loginUser`
- **常量** UPPER_SNAKE_CASE：`ADMIN_ROLE`, `DEFAULT_PASSWORD`
- **常量类** 使用 `interface` 而非 `class`：`public interface UserConstant { String ADMIN_ROLE = "admin"; }`
- **包名** 全小写：`com.adcage.acaicodefree`

### API 响应格式

所有接口返回 `BaseResponse<T>`（code=0 表示成功）：

```java
return ResultUtils.success(data);                                       // 成功
throw new BusinessException(ErrorCode.PARAMS_ERROR);                    // 错误（无消息）
throw new BusinessException(ErrorCode.NOT_FOUND_ERROR, "自定义消息");    // 错误（带消息）
ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);                    // 条件抛异常
```

### 错误码

| code  | 含义         |     | code  | 含义           |
| ----- | ------------ | --- | ----- | -------------- |
| 0     | 成功         |     | 40101 | 无权限         |
| 40000 | 请求参数错误 |     | 40300 | 禁止访问       |
| 40100 | 未登录       |     | 40400 | 请求数据不存在 |
| 50000 | 系统内部异常 |     | 50001 | 操作失败       |

### Controller 模式

```java
@RestController @RequestMapping("/app")
public class AppController {
    @Resource private AppService appService;
    @Resource private UserService userService;

    @PostMapping("/add")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)    // 管理员权限
    public BaseResponse<Long> addApp(@RequestBody AppAddRequest request) { ... }

    @PostMapping("/list/page/vo")                      // 分页查询返回 VO
    public BaseResponse<Page<AppVO>> listAppVOByPage(@RequestBody AppQueryRequest request) { ... }

    @PostMapping("/delete")                             // 删除使用共享 DeleteRequest
    public BaseResponse<Boolean> deleteApp(@RequestBody DeleteRequest request) { ... }
}
```

### Service 模式

- 接口继承 `IService<Entity>`，实现类继承 `ServiceImpl<Mapper, Entity>`
- 构造器注入依赖（非 `@Autowired` 字段注入）
- Entity→VO 转换在 Service 层完成：`BeanUtil.copyProperties(entity, vo)` + 关联数据填充
- 校验方法：`void validXxx(Entity entity, boolean add)` 区分新增/更新

### Entity 模式

```java
@Data @Builder @NoArgsConstructor @AllArgsConstructor
@Table("user")
public class User implements Serializable {
    @Id(keyType = KeyType.Generator, value = KeyGenerators.snowFlakeId)
    private Long id;
    @Column(value = "isDelete", isLogicDelete = true)
    private Integer isDelete;
    @Column(value = "updateTime", onUpdateValue = "now()")
    private LocalDateTime updateTime;
}
```

### DTO/VO 约定

| 类型             | 用途                         | 有 ID | 继承          |
| ---------------- | ---------------------------- | ----- | ------------- |
| `*AddRequest`    | 创建操作                     | 否    | 否            |
| `*EditRequest`   | 自助编辑（ID 从 session 取） | 否    | 否            |
| `*UpdateRequest` | 管理员更新                   | 是    | 否            |
| `*QueryRequest`  | 分页查询                     | 可选  | `PageRequest` |
| `DeleteRequest`  | 通用删除                     | 是    | 否            |
| `*VO`            | API 响应                     | 是    | 否            |

### SSE 流式端点

AI 对话生成使用 `Flux<ServerSentEvent<String>>` 返回流式数据，路径 `/app/chat/gen/code/stream`。

## Python Agent Runtime 代码风格（Python 3.11+ / FastAPI / LangGraph）

### 目录结构

```
agent-runtime-python/app/
├── main.py              # FastAPI 入口 + gRPC 生命周期
├── api/                 # HTTP 路由（仅 health，AI 生成走 gRPC）
├── agent_loop/          # ⛔ 冻结 Legacy Agent Loop（禁止新增功能，仅作参考）
│   ├── agents/          # Agent 实现（application.py, base.py）
│   ├── nodes/           # 图节点（init, route_step, plan_step, implement_dispatcher, validate_step, finish）
│   ├── tools/           # 13 个工具（decide_route, plan_tools, run_checks, select_skill 等）
│   ├── graph.py         # LangGraph StateGraph 构建
│   ├── state.py         # AgentLoopState（21KB 复杂状态）
│   ├── transition.py    # 状态转换
│   └── transition_guard.py  # 转换守卫
├── agent_loop_vnext/    # ✅ 活跃开发 vNext Agent Loop（所有新 AI 功能在此实现）
│   ├── agents/implementor/  # 实现者 Agent（prompt.py, tools.py）
│   ├── shared/          # 共享工具（history.py, tools/base.py, tools/file_tools.py）
│   ├── runner.py        # SingleImplementLoopRunner（主循环）
│   └── state.py         # SingleImplementState（最小状态）
├── artifacts/           # 产物处理
├── capabilities/        # 资产发现与加载系统
│   ├── common/          # 共享（frontmatter 解析、资产索引、manifest、路径工具）
│   ├── craft/           # 工艺定义（loader → registry → selector → prompt_module → types）
│   ├── design_systems/  # 设计系统资产
│   ├── seeds/           # 种子能力（含 applier）
│   ├── skills/          # 技能定义
│   └── templates/       # 模板资产
├── core/                # 基础设施
│   ├── config.py        # pydantic-settings 配置（含 agent_loop_engine、terminal 限制等）
│   ├── context.py       # contextvars（trace_id, agent_run_id）
│   ├── error_codes.py   # AgentErrorCode 枚举（6xxxx 范围，详见源码）
│   ├── exceptions.py    # AgentRuntimeError
│   ├── log_utils.py     # AI 链路日志工具（log_prompt, log_response, log_model_call, log_tool_call）
│   ├── logging.py       # 结构化日志 + TraceIdFilter
│   ├── metrics.py       # Prometheus 指标定义（详见源码）
│   └── sse.py           # SSE 格式化
├── generation_modes/    # 生成模式注册
├── graph/               # 图编排辅助
├── grpc/                # protobuf 生成代码（勿手动编辑，由 scripts/generate_grpc.py 生成）
├── grpc_client/         # Python → Java gRPC 客户端
│   ├── channel.py       # gRPC Channel 管理（keepalive + 超时选项）
│   ├── platform_client.py  # 调用 Java PlatformService
│   ├── retry.py         # 异步重试工具
│   └── tool_client.py   # 调用 Java ToolService
├── grpc_server/         # Java → Python gRPC 服务端
│   ├── code_generation_servicer.py  # 4 个 RPC 方法实现
│   ├── interceptors.py  # gRPC Server Interceptor（请求日志 + trace_id + 指标埋点）
│   └── server.py        # gRPC 服务创建与启动
├── runtime/             # 运行时编排
├── services/            # 业务服务
│   ├── chat_model_factory.py  # 模型工厂（provider → ChatOpenAI）
│   └── prompt_enhancer.py     # 提示词增强服务
├── tools/               # LangChain Tool 定义与注册
├── events/              # 事件模型（AgentEvent）
└── schemas/             # Pydantic 请求/响应模型
```

### 命名与编码规范

- **类名** PascalCase：`AgentService`, `ChatModelFactory`
- **函数/方法/变量** snake_case：`build_graph`, `agent_run_id`
- **常量** UPPER_SNAKE_CASE：`SUPPORTED_PROVIDERS`, `RISK_REJECTION_PATTERNS`
- **模块名** 全小写，简短：`graph.py`, `state.py`, `registry.py`
- **Pydantic 模型** PascalCase，字段 camelCase（与 proto/Java 对齐）：`agentRunId`, `codeGenType`
- **类型注解** 必须使用：函数签名、Pydantic 模型、TypedDict 均需完整类型

### 错误码体系

Python Agent Runtime 使用独立的错误码体系（6xxxx 范围），与 Java 端错误码（4xxxx/5xxxx）隔离。Python 错误码通过 gRPC 事件和响应传递给 Java，Java 在 SSE 流中携带 code + message 传给前端，不做映射转换。完整枚举值见 `core/error_codes.py`。

| 范围        | 领域     |
| ----------- | -------- |
| 60000-60999 | AI 模型  |
| 61000-61999 | Agent 图 |
| 62000-62999 | 工具执行 |
| 63000-63999 | 提示词   |
| 64000-64999 | 配置     |

使用方式：

```python
from app.core.exceptions import AgentRuntimeError
from app.core.error_codes import AgentErrorCode

raise AgentRuntimeError("模型调用超时", code=AgentErrorCode.MODEL_TIMEOUT)
```

### 日志规范（强制）

#### 请求追踪

- 每个 gRPC 请求入口生成 `trace_id`（优先从 Java 传入的 `x-trace-id` metadata 取，否则自动生成 UUID）
- 使用 `contextvars` 贯穿整个请求生命周期，所有日志自动携带 `trace_id`
- gRPC Server Interceptor 负责注入 `trace_id` 并记录请求开始/结束日志

#### 日志格式

```
{asctime} | {levelname} | {name} | trace_id={trace_id} | {message}
```

#### AI 链路日志（必须，使用 log_utils 工具函数）

```python
from app.core.log_utils import log_prompt, log_response, log_model_call, log_tool_call

log_prompt(logger, prompt, label="system_prompt")    # INFO 记录长度，DEBUG 记录前 200 字
log_response(logger, response, label="ai_response")  # INFO 记录长度，DEBUG 记录前 200 字
log_model_call(logger, provider, model, duration_ms, input_tokens, output_tokens)
log_tool_call(logger, tool_name, duration_ms, args_length, result_length, status)
```

#### 敏感数据日志策略

| 数据类型                                         | 默认日志级别 | 说明                                       |
| ------------------------------------------------ | ------------ | ------------------------------------------ |
| 请求元数据（appId, modelConfigId, codeGenType）  | INFO         | 始终记录                                   |
| 提示词完整内容                                   | DEBUG        | 默认不输出，DEBUG 时输出前 200 字 + 总长度 |
| AI 完整返回                                      | DEBUG        | 默认不输出，DEBUG 时输出前 200 字 + 总长度 |
| AI 返回摘要（长度、token 数、是否含 tool_calls） | INFO         | 始终记录                                   |
| 工具调用完整参数和结果                           | DEBUG        | 默认不输出                                 |
| 工具调用摘要（name, 耗时, 结果状态）             | INFO         | 始终记录                                   |
| 关联数据 ID（sessionId, messageId, versionId）   | INFO         | 始终记录，方便从数据库查完整内容           |
| 错误详情                                         | ERROR        | 始终完整记录                               |

### 关键配置项

完整配置见 `core/config.py`，以下为开发中常需关注的：

| 配置                     | 默认值                      | 说明                                     |
| ------------------------ | --------------------------- | ---------------------------------------- |
| `agent_loop_engine`      | `vnext`                     | Agent Loop 引擎选择（`vnext` / `legacy`）|
| `agent_loop_max_iterations` | `50`                     | Agent Loop 最大迭代次数                  |
| `agent_loop_max_mode_switches` | `6`                    | 最大模式切换次数（legacy 引擎）          |
| `terminal_allowed_commands` | `npm,npx,pip,python,node` | 终端允许执行的命令白名单                 |
| `terminal_readonly_commands` | `ls,cat,git,head,tail,find,wc,type,python` | 终端只读命令白名单 |
| `terminal_default_timeout` | `30`                      | 终端命令默认超时（秒）                   |
| `terminal_max_timeout`   | `120`                       | 终端命令最大超时（秒）                   |
| `llm_audit_enabled`      | `true`                      | LLM 审计日志开关                         |
| `llm_audit_dir`          | `../storage/llm_audit`      | LLM 审计日志目录                         |
| `grpc_server_port`       | `9091`                      | Python gRPC 服务端口                     |
| `java_grpc_target`       | `localhost:9090`            | Java gRPC 目标地址                       |
| `model_request_timeout`  | `120`                       | 模型请求超时（秒）                       |

## 前端代码风格（Vue 3 + TypeScript）

### 目录结构

```
frontend-vue/src/
├── access/        # 路由守卫（登录/权限检查）
├── api/           # 自动生成的 API 调用函数及类型（由 openapi2ts 生成，勿手动编辑）
├── assets/        # 静态资源
├── components/    # 可复用组件
├── composables/   # 组合式函数（useSSEChat, useAppPreview 等）
├── layouts/       # 布局组件 (BasicLayout)
├── pages/         # 页面（按领域分目录: admin/, app/, user/）
├── router/        # 路由（自动发现 .ts 文件，每个文件导出 RouteRecordRaw 数组）
├── stores/        # Pinia 状态管理
├── utils/         # 工具函数
├── request.ts     # Axios 实例及拦截器
├── App.vue        # 根组件
└── main.ts        # 入口文件
```

### 格式化配置

- **Prettier**：`semi: false`, `singleQuote: true`, `printWidth: 120`
- **EditorConfig**：缩进 2 空格，行尾 LF，最大行长 100
- **ESLint**：flat config，`eslint-plugin-vue` essential + `@vue/eslint-config-typescript`

### Vue 组件规范

```vue
<template><!-- 模板 --></template>
<script lang="ts" setup>
// 导入 → 响应式数据 → 计算属性 → 函数 → 生命周期钩子
</script>
<style scoped>/* 作用域样式 */</style>
```

- Props 使用 TypeScript 接口 + `withDefaults(defineProps<Props>(), { ... })`
- 暴露方法给父组件：`defineExpose({ open })`
- 所有文本使用中文（无 i18n）

### 状态管理（Pinia）

使用 Composition API 风格 `defineStore`，所有 Store 放在 `src/stores/` 下。

### API 调用模式

- API 函数由 `@umijs/openapi` 自动生成，存放于 `src/api/`，**勿手动编辑**
- 调用返回 Axios 响应，成功判断 `res.data.code === 0`，数据取 `res.data.data`
- 拦截器自动处理 40100（未登录跳转）和网络错误提示
- 认证方式：Cookie-based（`withCredentials: true`）

### 环境变量

| 文件               | 关键变量                                            |
| ------------------ | --------------------------------------------------- |
| `.env.development` | `VITE_API_BASE_URL=/api`（相对路径，Vite 代理到 localhost:8700） |
| `.env.production`  | `VITE_API_BASE_URL=https://your-api-domain.com/api` |

## 端到端测试

使用 **Playwright CLI** 进行端到端测试，通过 `npx playwright` 命令执行浏览器自动化操作。

### 日志排查规则

端到端测试过程中遇到问题时，**应主动读取 `logs/` 目录下的最新日志来排查原因**，而不是向用户询问：

1. 执行端到端操作后，如果页面行为异常或接口返回错误，读取对应日志文件末尾
2. 在日志中查找对应的 ERROR、WARN 或相关请求路径的日志条目
3. 根据日志中的异常堆栈、SQL 错误、业务错误码等信息定位问题
4. 仅当日志信息不足以判断问题时，才向用户询问

日志文件（项目根目录 `logs/` 下，均为 append 模式，读取时关注最新的时间戳）：

| 文件                    | 来源                                        |
| ----------------------- | ------------------------------------------- |
| `logs/backend.log`      | Java 后端（Spring Boot）                    |
| `logs/agent-python.log` | Python Agent Runtime（FastAPI + LangGraph） |

## 开发热重载（至关重要）

开发环境下三个服务均支持代码修改后自动重载，**严禁**手动重启：

- **Java 后端**：Spring Boot DevTools，代码变更后自动重启（LiveReload 端口 35729）
- **Python Agent Runtime**：uvicorn `--reload` 模式，代码变更后自动重载
- **前端**：Vite HMR，代码变更后浏览器自动热更新

修改代码之后出现错误只会是代码问题，要么是代码 bug 导致服务器运行终止，要么代码问题导致功能问题。

## 重要注意事项

1. **Java 版本**：JDK 17 | **Node.js 版本**：`^20.19.0 || >=22.12.0` | **Python 版本**：`>=3.11`
2. **数据库**：MySQL 5.7+，建表脚本 `sql/create_table.sql`
3. **后端 API 文档**：`http://localhost:8700/api/doc.html`（Knife4j）
4. **前端开发服务器**：`http://localhost:5173` | **后端 API 基础路径**：`http://localhost:8700/api`
5. **路径分隔符**：所有文件路径统一使用正斜杠 `/`，禁止反斜杠 `\`
6. **MyBatis-Flex 代码生成**：运行 `generator.MyBatisCodegen` 的 main 方法可从数据库表生成 Entity/Mapper/Service/Controller
7. **API 类型同步**：修改后端接口后，在前端目录执行 `npm run openapi` 重新生成 TypeScript 类型
8. **gRPC 代码生成**：修改 proto 文件后，在 Python 目录执行 `python scripts/generate_grpc.py` 重新生成 gRPC 代码
9. **AI 服务**：AI 核心统一在 Python Agent Runtime 中实现；Java 不再新增 LangChain4j AI 服务，只保留 deprecated legacy 和 Python bridge
10. **运行时路由**：`CodeGenerationRuntimeRouter` 默认选择 `python-agent`，`java-agent` 已硬编码禁用
11. **Agent Loop 引擎选择**：Python 的 `agent_loop_engine` 配置默认 `vnext`，所有新增 AI 功能必须在 `agent_loop_vnext/` 中开发，`agent_loop/` 仅作参考（冻结）
