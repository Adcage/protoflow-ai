# AGENTS.md - AI 编程助手指南

## 项目概述

protoflow-ai 是基于 Spring Boot 3.5.5 + Vue 3 + Python Agent Runtime 的 AI 编程辅助平台，前后端分离并通过 gRPC 连接 Java 平台层与 Python AI Runtime。Java 后端负责 API、权限、平台状态、模型配置、会话、构建部署、文件工具和 gRPC bridge；Python Agent Runtime 负责所有 AI 核心能力，包括模型调用、Agent Graph、提示词增强、代码生成、工具调用决策和 AI 路由。前端使用 Ant Design Vue、Pinia、Axios。

## AI Runtime 边界（强制）

### Python 负责所有 AI 核心能力

所有新增或维护的 AI 核心功能必须放在 `agent-runtime-python/` 中，包括：

- 模型调用、模型流式响应、AI 路由、提示词增强、Agent Graph、工具调用决策
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

Java 中原 LangChain4j AI 核心已经遗弃：

- 禁止新增 Java LangChain4j `AiServices`、`@SystemMessage`、`@UserMessage`、模型推理 Bean、Java agent workflow
- 禁止让 `java-agent`、`WorkflowCodeGeneratorService`、Java prompt enhancer 或 Java AI routing 成为可用入口或 fallback
- 旧 Java AI 文件只能作为 deprecated legacy 保留，必须标记 `@Deprecated`，不得新增调用方
- 如果需要恢复或新增智能路由、提示词增强、图片采集规划等 AI 能力，必须在 Python Runtime 实现，再由 Java 通过 gRPC/HTTP bridge 调用

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

## 后端代码风格（Java 17 + Spring Boot）

### 目录结构

```
backend-java/src/main/java/com/adcage/acaicodefree/
├── ai/              # deprecated legacy Java AI 代码（禁止新增入口；协议 DTO 除外）
├── annotation/      # 自定义注解 (@AuthCheck)
├── aop/             # AOP 切面 (AuthInterceptor, LogInterceptor)
├── common/          # 通用类 (BaseResponse, ErrorCode, ResultUtils, PageRequest, DeleteRequest)
├── config/          # 配置类 (CorsConfig, JsonConfig, WebMvcConfig)
├── constant/        # 常量接口 (UserConstant, AppConstant)
├── controller/       # 控制器层
├── core/            # 核心业务编排（Facade + 策略 + 模板方法模式）
│   ├── build/        # 项目构建服务 (VueProjectBuildService)
│   ├── handler/      # 流处理器策略 (SimpleTextStreamHandler, JsonMessageStreamHandler)
│   ├── memory/       # AI 聊天记忆加载 (ChatMemoryLoader)
│   ├── parser/       # 代码解析策略 (SingleFileParser, MultiFileParser)
│   └── saver/        # 文件保存模板方法 (AbstractCodeFileSaver 及子类)
├── exception/       # 异常 (BusinessException, GlobalExceptionHandler, ThrowUtils)
├── generator/       # MyBatis-Flex 代码生成器 (独立 main 方法)
├── grpc/            # Java <-> Python gRPC bridge、PlatformService、ToolService
├── mapper/          # MyBatis-Flex Mapper 接口（继承 BaseMapper）
├── model/
│   ├── dto/          # 请求 DTO（按领域分子包: app/, chat/, user/）
│   ├── entity/       # 数据库实体 (@Table, @Id, @Column)
│   ├── enums/        # 枚举 (CodeGenTypeEnum, UserRoleEnum)
│   └── vo/          # 响应 VO（按领域分子包）
├── runtime/         # 代码生成运行时抽象；默认只能选择 python-agent
└── service/          # 服务层接口 + impl/ 实现
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
├── core/                # 基础设施
│   ├── config.py        # pydantic-settings 配置
│   ├── context.py       # contextvars（trace_id, agent_run_id）
│   ├── error_codes.py   # AgentErrorCode 枚举（6xxxx 范围）
│   ├── exceptions.py    # AgentRuntimeError
│   ├── exception_handlers.py
│   ├── log_utils.py     # AI 链路日志工具（log_prompt, log_response, log_model_call, log_tool_call）
│   ├── logging.py       # 结构化日志 + TraceIdFilter
│   ├── metrics.py       # Prometheus 指标定义
│   ├── middleware.py    # HTTP 请求上下文中间件
│   ├── response.py      # 统一响应封装
│   └── sse.py           # SSE 格式化
├── grpc/                # protobuf 生成代码（勿手动编辑，由 scripts/generate_grpc.py 生成）
├── grpc_client/         # Python → Java gRPC 客户端
│   ├── channel.py       # gRPC Channel 管理（keepalive + 超时选项）
│   ├── platform_client.py  # 调用 Java PlatformService（模型配置、构建、部署、AgentRun 完成）
│   ├── retry.py         # 异步重试工具
│   └── tool_client.py   # 调用 Java ToolService（文件读写删改）
├── grpc_server/         # Java → Python gRPC 服务端
│   ├── code_generation_servicer.py  # 5 个 RPC 方法实现
│   ├── interceptors.py  # gRPC Server Interceptor（请求日志 + trace_id + 指标埋点）
│   └── server.py        # gRPC 服务创建与启动
├── agent/               # Agent Graph 编排（LangGraph StateGraph）
├── services/            # 业务服务
│   ├── chat_model_factory.py  # 模型工厂（provider → ChatOpenAI）
│   └── prompt_enhancer.py     # 提示词增强服务
├── tools/               # LangChain Tool 定义与注册
├── events/              # 事件模型（AgentEvent）
└── schemas/             # Pydantic 请求/响应模型
```

### 构建/测试/开发命令

```bash
# agent-runtime-python/ 目录执行
pip install -e ".[dev]"              # 安装依赖（含开发依赖）
uvicorn app.main:app --reload --port 8000  # 启动开发服务器（FastAPI + gRPC）
pytest                              # 运行所有测试
pytest tests/test_xxx.py            # 运行单个测试文件
ruff check .                        # lint 检查
ruff format .                       # 格式化
python scripts/generate_grpc.py     # 从 proto 文件重新生成 gRPC 代码
```

### 命名与编码规范

- **类名** PascalCase：`AgentService`, `ChatModelFactory`
- **函数/方法/变量** snake_case：`build_graph`, `agent_run_id`
- **常量** UPPER_SNAKE_CASE：`SUPPORTED_PROVIDERS`, `RISK_REJECTION_PATTERNS`
- **模块名** 全小写，简短：`graph.py`, `state.py`, `registry.py`
- **Pydantic 模型** PascalCase，字段 camelCase（与 proto/Java 对齐）：`agentRunId`, `codeGenType`
- **类型注解** 必须使用：函数签名、Pydantic 模型、TypedDict 均需完整类型

### 错误码体系

Python Agent Runtime 使用独立的错误码体系（6xxxx 范围），与 Java 端错误码（4xxxx/5xxxx）隔离。Python 错误码通过 gRPC 事件和响应传递给 Java，Java 在 SSE 流中携带 code + message 传给前端，不做映射转换。

| 范围        | 领域     | 枚举值示例                                                                                                                                                    |
| ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 60000-60999 | AI 模型  | `MODEL_CALL_FAILED(60001)`, `MODEL_TIMEOUT(60002)`, `CONTENT_SAFETY_REJECTED(60003)`, `MODEL_QUOTA_EXCEEDED(60004)`, `MODEL_RESPONSE_EMPTY(60005)`            |
| 61000-61999 | Agent 图 | `GRAPH_EXECUTION_INTERRUPTED(61001)`, `NODE_EXECUTION_ERROR(61002)`, `STATE_ERROR(61003)`, `MAX_ITERATIONS_EXCEEDED(61004)`                                   |
| 62000-62999 | 工具执行 | `TOOL_CALL_FAILED(62001)`, `TOOL_ARGS_ERROR(62002)`, `TOOL_TIMEOUT(62003)`, `PATH_TRAVERSAL_BLOCKED(62004)`                                                   |
| 63000-63999 | 提示词   | `PROMPT_VALIDATION_FAILED(63001)`, `PROMPT_ENHANCE_FAILED(63002)`, `PROMPT_INJECTION_DETECTED(63003)`, `PROMPT_LENGTH_EXCEEDED(63004)`, `PROMPT_EMPTY(63005)` |
| 64000-64999 | 配置     | `MODEL_CONFIG_MISSING(64001)`, `PROVIDER_NOT_SUPPORTED(64002)`, `API_KEY_MISSING(64003)`, `MODEL_NAME_MISSING(64004)`                                         |

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

#### 请求日志（必须）

```python
# gRPC 请求开始 — INFO
logger.info("gRPC request start | method=%s agentRunId=%s", method, agent_run_id)

# gRPC 请求结束 — INFO
logger.info("gRPC request end | method=%s duration_ms=%.0f", method, duration_ms)

# gRPC 请求异常 — ERROR（含堆栈）
logger.error("gRPC request error | method=%s duration_ms=%.0f error=%s", method, duration_ms, e, exc_info=True)
```

#### AI 链路日志（必须，使用 log_utils 工具函数）

```python
from app.core.log_utils import log_prompt, log_response, log_model_call, log_tool_call

# 提示词 — INFO 记录长度，DEBUG 记录前 200 字
log_prompt(logger, prompt, label="system_prompt")

# AI 返回 — INFO 记录长度，DEBUG 记录前 200 字
log_response(logger, response, label="ai_response")

# 模型调用 — INFO 记录 provider/model/耗时/token 数
log_model_call(logger, provider, model, duration_ms, input_tokens, output_tokens)

# 工具调用 — INFO 记录 name/耗时/结果状态
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

### gRPC 交互规范

#### Python → Java（gRPC Client）

| 客户端               | 目标服务                   | 用途                                                                           |
| -------------------- | -------------------------- | ------------------------------------------------------------------------------ |
| `GrpcPlatformClient` | Java PlatformService :9090 | 获取模型配置、构建项目、部署应用、完成 AgentRun、创建 AppVersion、获取聊天历史 |
| `GrpcToolClient`     | Java ToolService :9090     | 文件读写删改（当 Python 本地文件工具不可用时降级使用）                         |

- 所有 gRPC 调用必须携带 `x-internal-secret` metadata 认证
- gRPC 调用失败必须记录 ERROR 日志（含 trace_id、目标方法、错误详情）
- `get_model_config` 自动重试 2 次（间隔 1s），构建/部署操作不重试

#### Java → Python（gRPC Server）

| RPC 方法           | 类型         | 说明                                    |
| ------------------ | ------------ | --------------------------------------- |
| `StreamGenerate`   | unary-stream | 代码生成流式主入口                      |
| `StreamModify`     | unary-stream | 代码修改流式入口                        |
| `RouteCodeGenType` | unary-unary  | AI 路由（根据 prompt 判断 codeGenType） |
| `ValidatePrompt`   | unary-unary  | 提示词校验                              |
| `EnhancePrompt`    | unary-unary  | 提示词增强                              |

- gRPC Server Interceptor 注入 trace_id、记录请求开始/结束日志、埋点 Prometheus 指标
- 流式方法（StreamGenerate/StreamModify）的每个事件必须携带 `agent_run_id` 和递增 `seq`

### 工具执行架构

| 工具类型                                                              | 执行位置        | 说明                                               |
| --------------------------------------------------------------------- | --------------- | -------------------------------------------------- |
| 文件操作（read_file, write_file, modify_file, delete_file, read_dir） | Python 直接执行 | 高频调用、开发迭代快；Workspace 类提供路径穿越保护 |
| 构建/部署（build_vue_project, deploy_app）                            | gRPC → Java     | 涉及 Node.js 环境、对象存储、权限管理              |
| 平台状态（complete_agent_run, create_app_version）                    | gRPC → Java     | 数据库持久化由 Java 统一管理                       |

### 数据存储规范

- **Python 不直接连接数据库**，所有持久化通过 gRPC 桥接到 Java
- **AI 对话记录**：Python 通过 `GrpcPlatformClient.get_chat_history()` 读取历史，通过 `CompleteAgentRun` 上报运行结果
- **业务指标**（token 用量、模型名、耗时）：请求完成后通过 `CompleteAgentRun` 上报，Java 存入 `agent_run` 表
- **运维指标**（QPS、延迟 P99、错误率）：Python 暴露 `/metrics` 端点，Prometheus 直接抓取，不进数据库

### 模型配置获取

Java 发起 gRPC 请求时携带 `model_config_id` + `config_version`，Python 通过 `GrpcPlatformClient.get_model_config()` 回调 Java 获取完整配置（provider, modelName, baseUrl, apiKey），再用 `ChatModelFactory.create()` 构建模型实例。Python 不存储模型配置，只消费。

### 运维指标（Prometheus）

Python 暴露 `/metrics` 端点（Prometheus 格式），定义的指标：

| 指标名                           | 类型      | 说明                                           |
| -------------------------------- | --------- | ---------------------------------------------- |
| `agent_requests_total`           | Counter   | 请求总数（按 method, code_gen_type）           |
| `agent_request_duration_seconds` | Histogram | 请求耗时分布                                   |
| `model_call_duration_seconds`    | Histogram | 模型调用耗时（按 provider, model）             |
| `model_call_tokens_total`        | Counter   | token 使用量（按 model, direction）            |
| `tool_call_duration_seconds`     | Histogram | 工具调用耗时（按 tool_name）                   |
| `tool_call_total`                | Counter   | 工具调用次数（按 tool_name, status）           |
| `grpc_client_calls_total`        | Counter   | Python→Java gRPC 调用次数（按 method, status） |

### 健康检查

| 端点                | 说明                                                                    |
| ------------------- | ----------------------------------------------------------------------- |
| `GET /health`       | 存活探针，返回 status + runtime + gRPC channel 连通性                   |
| `GET /health/ready` | 就绪探针，检查 gRPC channel 连通 + internal_secret 配置，不满足返回 503 |

### 配置项

| 配置                     | 默认值                      | 说明                                     |
| ------------------------ | --------------------------- | ---------------------------------------- |
| `java_platform_base_url` | `http://localhost:8700/api` | Java 平台 HTTP 地址                      |
| `agent_runtime_name`     | `python-langgraph`          | 运行时标识                               |
| `agent_internal_secret`  | `""`                        | gRPC 内部认证密钥（启动时未配置会 WARN） |
| `model_request_timeout`  | `120`                       | 模型请求超时（秒）                       |
| `default_model_provider` | `openai`                    | 默认模型提供商                           |
| `grpc_server_port`       | `9091`                      | Python gRPC 服务端口                     |
| `java_grpc_target`       | `localhost:9090`            | Java gRPC 目标地址                       |

## 前端代码风格（Vue 3 + TypeScript）

### 目录结构

```
frontend-vue/src/
├── access/        # 路由守卫（登录/权限检查）
├── api/           # 自动生成的 API 调用函数及类型（由 openapi2ts 生成，勿手动编辑）
├── assets/        # 静态资源
├── components/    # 可复用组件
├── layouts/       # 布局组件 (BasicLayout)
├── pages/         # 页面（按领域分目录: admin/, app/, user/）
├── router/        # 路由（自动发现 .ts 文件，每个文件导出 RouteRecordRaw 数组）
├── stores/        # Pinia 状态管理
├── request.ts     # Axios 实例及拦截器
├── App.vue         # 根组件
└── main.ts         # 入口文件
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
| `.env.development` | `VITE_API_BASE_URL=http://localhost:8700/api`       |
| `.env.production`  | `VITE_API_BASE_URL=https://your-api-domain.com/api` |

## 端到端测试

### 测试工具

使用 **Playwright CLI** 进行端到端测试，通过 `npx playwright` 命令执行浏览器自动化操作。

### 日志排查规则

端到端测试过程中遇到问题时，**应主动读取 `logs/` 目录下的最新日志来排查原因**，而不是向用户询问。具体做法：

1. 执行端到端操作后，如果页面行为异常或接口返回错误，读取对应日志文件末尾
2. 在日志中查找对应的 ERROR、WARN 或相关请求路径的日志条目
3. 根据日志中的异常堆栈、SQL 错误、业务错误码等信息定位问题
4. 仅当日志信息不足以判断问题时，才向用户询问

日志文件（项目根目录 `logs/` 下，均为 append 模式，读取时关注最新的时间戳）：

| 文件                    | 来源                                        |
| ----------------------- | ------------------------------------------- |
| `logs/backend.log`      | Java 后端（Spring Boot）                    |
| `logs/agent-python.log` | Python Agent Runtime（FastAPI + LangGraph） |

## 开发热重载(至关重要)

开发环境下三个服务均支持代码修改后自动重载，**严禁**手动重启：

- **Java 后端**：Spring Boot DevTools，代码变更后自动重启（LiveReload 端口 35729）
- **Python Agent Runtime**：uvicorn `--reload` 模式，代码变更后自动重载
- **前端**：Vite HMR，代码变更后浏览器自动热更新

修改代码之后出现错误只会是代码问题，要么是代码bug导致服务器运行终止，要么代码问题导致功能问题

## 重要注意事项

1. **Java 版本**：JDK 17 | **Node.js 版本**：`^20.19.0 || >=22.12.0`
2. **数据库**：MySQL 5.7+，建表脚本 `sql/create_table.sql`
3. **后端 API 文档**：`http://localhost:8080/doc.html`（Knife4j）
4. **前端开发服务器**：`http://localhost:5173` | **后端 API 基础路径**：`http://localhost:8700/api`
5. **路径分隔符**：所有文件路径统一使用正斜杠 `/`，禁止反斜杠 `\`
6. **MyBatis-Flex 代码生成**：运行 `generator.MyBatisCodegen` 的 main 方法可从数据库表生成 Entity/Mapper/Service/Controller
7. **API 类型同步**：修改后端接口后，在前端目录执行 `npm run openapi` 重新生成 TypeScript 类型
8. **AI 服务**：AI 核心统一在 Python Agent Runtime 中实现；Java 不再新增 LangChain4j AI 服务，只保留 deprecated legacy 和 Python bridge
