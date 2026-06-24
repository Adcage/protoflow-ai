# Java 到 Python AI 对话 gRPC 完整测试方案

## 1. 背景与目标

当前项目已将 Java 端到 Python 端的 AI 对话链路改造成 gRPC 通信。该链路不只是 Java 调用 Python，而是双向运行时协作：

- Java 后端作为控制面，负责用户、应用、会话、模型配置、AgentRun、构建部署、聊天历史和前端 SSE。
- Python Agent Runtime 作为执行面，负责模型调用、Agent 编排、工具调用和代码生成。
- Java 通过 gRPC client 调用 Python 暴露的 `CodeGenerationService`。
- Python 通过 gRPC client 反向调用 Java 暴露的 `ToolService` 和 `PlatformService`。
- 前端仍通过 Java 的 `/app/chat/gen/code/stream` 接收 SSE，因此 Java 需要把 Python gRPC stream 转换成前端兼容的 `StreamMessage`。

本测试方案的目标是验证 gRPC 改造后所有核心功能的稳定性、可靠性、可观测性和回归安全性，避免只验证单个接口可用而遗漏跨进程、跨语言、流式传输、状态落库、文件落盘和异常恢复问题。

## 2. 测试结论准入标准

只有同时满足以下条件，才可以认为 gRPC AI 对话链路具备可合入或可发布基础：

1. Java 编译和关键测试通过。
2. Python 单元测试和关键 Agent 测试通过。
3. `proto` 契约和两端生成代码一致。
4. Java gRPC Server `9090` 和 Python gRPC Server `9091` 均可启动，并可互相调用。
5. Java `ToolService` 的读、写、改、删、目录读取、批量写入均可用。
6. Java `PlatformService` 的模型配置、应用详情、用户信息、聊天历史、AgentRun 完成/失败、构建、部署接口均有验证。
7. Python `CodeGenerationService` 的 prompt 校验、代码生成 stream、错误事件、完成事件均有验证。
8. 前端通过 `/app/chat/gen/code/stream` 可收到完整 SSE：`meta`、`message`、`done` 或明确的 `error`。
9. `chat_session`、`chat_history`、`agent_run`、`app_version` 状态一致。
10. 生成文件真实落盘到 `storage/agent-workspaces/<agentRunId>/source` 或项目约定输出目录。
11. 关键异常场景有明确错误反馈，不出现静默失败、一直 loading、空白响应或进程崩溃。
12. 并发生成不会串会话、串用户、串 workspace、串 AgentRun。
13. `logs/backend.log` 和 `logs/agent-python.log` 中没有未解释的 ERROR。

## 3. 测试范围

### 3.1 必测范围

| 模块 | 必测内容 |
|------|----------|
| Proto 契约 | `common.proto`、`code_generation.proto`、`tool_service.proto`、`platform_service.proto` 字段、枚举、服务签名 |
| Java gRPC Client | `GrpcPythonAgentRuntime` 请求构造、stream 消费、错误处理、事件转换 |
| Java gRPC Server | `GrpcToolService`、`GrpcPlatformService`、`GrpcInternalAuthInterceptor` |
| Python gRPC Server | `CodeGenerationServicer`、`StreamGenerate`、`StreamModify`、`ValidatePrompt` |
| Python gRPC Client | `GrpcToolClient`、`GrpcPlatformClient`、channel 管理、鉴权 metadata |
| Agent 编排 | Python Agent 调模型、调用 Java 工具、生成文件、输出事件 |
| Java SSE | `/app/chat/gen/code/stream` 对 gRPC stream 的兼容输出 |
| 数据库 | `chat_session`、`chat_history`、`agent_run`、`app_version` |
| 文件系统 | 生成代码目录、构建目录、下载产物 |
| 前端页面 | 发送消息、流式展示、工具事件展示、预览、下载、部署 |
| 日志 | Java/Python 两端 request id、agentRunId、错误堆栈和完成日志 |

### 3.2 暂不作为通过标准但建议记录的范围

| 范围 | 说明 |
|------|------|
| 真实生产模型长期稳定性 | 可以做抽样，不建议作为每次本地门禁 |
| 大规模压测 | 本阶段以小并发可靠性为主，不要求压测到生产容量 |
| TLS/mTLS | 当前配置是 plaintext，本阶段只测内部密钥鉴权 |
| 跨机器部署 | 本地和单机集成先通过，再扩展到多机 |

## 4. 当前代码入口清单

### 4.1 Proto 契约

- `proto/common.proto`
- `proto/code_generation.proto`
- `proto/tool_service.proto`
- `proto/platform_service.proto`

### 4.2 Java 侧入口

- `backend-java/src/main/java/com/adcage/acaicodefree/grpc/client/GrpcPythonAgentRuntime.java`
- `backend-java/src/main/java/com/adcage/acaicodefree/grpc/server/GrpcToolService.java`
- `backend-java/src/main/java/com/adcage/acaicodefree/grpc/server/GrpcPlatformService.java`
- `backend-java/src/main/java/com/adcage/acaicodefree/grpc/server/GrpcInternalAuthInterceptor.java`
- `backend-java/src/main/resources/application.yml`

### 4.3 Python 侧入口

- `agent-runtime-python/app/grpc_server/server.py`
- `agent-runtime-python/app/grpc_server/code_generation_servicer.py`
- `agent-runtime-python/app/grpc_client/channel.py`
- `agent-runtime-python/app/grpc_client/tool_client.py`
- `agent-runtime-python/app/grpc_client/platform_client.py`
- `agent-runtime-python/app/services/agent_service.py`
- `agent-runtime-python/app/agent/graph.py`
- `agent-runtime-python/app/main.py`

### 4.4 现有测试和脚本

- `backend-java/src/test/java/com/adcage/acaicodefree/controller/PythonAgentE2ETest.java`
- `backend-java/src/test/java/com/adcage/acaicodefree/controller/AppChatE2ETest.java`
- `backend-java/src/test/java/com/adcage/acaicodefree/service/impl/AgentRunServiceImplTest.java`
- `backend-java/src/test/java/com/adcage/acaicodefree/service/impl/ModelConfigServiceImplTest.java`
- `agent-runtime-python/tests/api/test_code_generation_stream.py`
- `agent-runtime-python/tests/services/test_agent_service.py`
- `agent-runtime-python/tests/agent/test_graph.py`
- `agent-runtime-python/scripts/test_grpc_all.py`
- `agent-runtime-python/scripts/test_grpc_platform.py`
- `agent-runtime-python/scripts/test_grpc_data_check.py`

## 5. 测试环境准备

### 5.1 基础环境

| 项 | 要求 |
|----|------|
| OS | Windows + PowerShell |
| Java | JDK 17 |
| Maven | 可正常执行 `mvn test` 和 `mvn spring-boot:run` |
| Python | 3.11+，项目已有历史验证中 3.10+ 可运行，但 gRPC 依赖建议使用当前项目锁定环境 |
| Node.js | `^20.19.0 || >=22.12.0` |
| MySQL | 已执行 `sql/create_table.sql` |
| Redis | Java session 相关功能需要可用 |

### 5.2 端口规划

| 服务 | 默认端口 | 用途 |
|------|----------|------|
| Java HTTP | `8700` | 后端 API 和前端 SSE |
| Java gRPC | `9090` | `ToolService`、`PlatformService` |
| Python HTTP | `9000` | FastAPI health 和兼容 HTTP stream |
| Python gRPC | `9091` | `CodeGenerationService` |
| Frontend | `5173` | Vue 开发服务器 |

启动前先确认端口未被占用：

```powershell
Get-NetTCPConnection -LocalPort 8700,9000,9090,9091,5173 -ErrorAction SilentlyContinue
```

### 5.3 环境变量

Java 后端建议使用：

```powershell
$env:AGENT_RUNTIME="python-agent"
$env:AGENT_RUNTIME_INTERNAL_SECRET="local-test-secret"
$env:AGENT_PYTHON_BASE_URL="http://localhost:9000"
```

Python Runtime 建议使用：

```powershell
$env:AGENT_INTERNAL_SECRET="local-test-secret"
$env:JAVA_GRPC_TARGET="localhost:9090"
$env:GRPC_SERVER_PORT="9091"
$env:JAVA_PLATFORM_BASE_URL="http://localhost:8700/api"
```

注意：如果 Python gRPC client 没有把 `AGENT_INTERNAL_SECRET` 作为 gRPC metadata `x-internal-secret` 发送给 Java，Java 的 `GrpcInternalAuthInterceptor` 会拒绝请求。该点必须作为高优先级测试项。

### 5.4 数据准备

至少准备以下数据：

1. 一个普通用户。
2. 一个管理员用户。
3. 一个 `model_config` 记录：
   - `enabled=1`
   - `isDefault=1`
   - `configVersion` 有明确值
   - `provider/modelName/baseUrl/apiKeyCipher` 非空
4. 一个 `vue_project` 类型应用。
5. 一个 `single_file` 类型应用。
6. 一个 `multi-file` 类型应用。

数据检查 SQL：

```sql
SELECT id, provider, modelName, enabled, isDefault, configVersion
FROM model_config
WHERE isDelete = 0;

SELECT id, appName, codeGenType, userId
FROM app
WHERE isDelete = 0
ORDER BY createTime DESC
LIMIT 10;
```

## 6. 分层测试策略

测试分为 8 层，从低成本到高成本逐层推进。前一层不通过，不进入后一层。

| 层级 | 类型 | 目标 | 失败处理 |
|------|------|------|----------|
| L0 | 静态检查 | 确认文件、配置、生成代码存在 | 先修配置或生成代码 |
| L1 | Proto 契约测试 | 确认两端字段和枚举一致 | 修 proto 或重新生成 |
| L2 | Java 单元测试 | 测 Java gRPC client/server 映射和异常 | 修 Java 映射或服务实现 |
| L3 | Python 单元测试 | 测 Python gRPC server/client 映射和异常 | 修 Python 映射或 client |
| L4 | 本地双服务集成测试 | Java/Python 真实 gRPC 调用 | 查端口、鉴权、日志 |
| L5 | Java SSE E2E | `/app/chat/gen/code/stream` 全链路 | 查 backend.log 和 agent-python.log |
| L6 | 浏览器 E2E | 前端交互、预览、下载、部署 | 查接口、状态和页面 |
| L7 | 稳定性与异常注入 | 并发、重试、断连、超时 | 补超时、错误处理和幂等 |

## 7. L0 静态检查

### 7.1 检查 gRPC 文件完整性

```powershell
rg --files proto
rg --files backend-java/src/main/java/com/adcage/acaicodefree/grpc
rg --files agent-runtime-python/app/grpc
rg --files agent-runtime-python/app/grpc_server
rg --files agent-runtime-python/app/grpc_client
```

期望：

- `proto` 下 4 个 proto 文件存在。
- Java gRPC client/server 实现存在。
- Python `_pb2.py` 和 `_pb2_grpc.py` 生成文件存在。
- Python server/client 封装存在。

### 7.2 检查配置

```powershell
Select-String -Path backend-java/src/main/resources/application.yml -Pattern "grpc:|runtime-internal-secret|python-agent" -Context 2,4
Get-Content agent-runtime-python/app/core/config.py
```

期望：

- Java `grpc.server.port=9090`。
- Java `grpc.client.python-agent.address=static://localhost:9091`。
- Python `grpc_server_port=9091`。
- Python `java_grpc_target=localhost:9090`。
- 两端 internal secret 配置项命名清楚。

### 7.3 检查工作树

```powershell
git status --short
git diff --stat
```

目的：

- 明确当前 gRPC 改动范围。
- 避免测试结果被未确认的无关改动污染。
- 便于失败时回溯具体代码版本。

## 8. L1 Proto 契约测试

### 8.1 代码生成验证

Java：

```powershell
cd E:/Programme/Project/protoflow-ai/backend-java
mvn clean compile
```

Python：

```powershell
cd E:/Programme/Project/protoflow-ai/agent-runtime-python
python scripts/generate_grpc.py
python -c "from app.grpc import code_generation_pb2, platform_service_pb2, tool_service_pb2, common_pb2; print('grpc imports ok')"
```

期望：

- Java protobuf 生成无错误。
- Python protobuf 生成无错误。
- Python import 不报 `ModuleNotFoundError`、`VersionError`、`grpcio` 版本不匹配。

### 8.2 枚举兼容用例

| 用例 | 输入 | 期望 |
|------|------|------|
| CodeGenType single_file | Java `SINGLE_FILE` / Python `SINGLE_FILE` | 映射为业务值 `single_file` |
| CodeGenType multi-file | Java `MULTI_FILE` / Python `MULTI_FILE` | 映射为业务值 `multi-file` |
| CodeGenType vue_project | Java `VUE_PROJECT` / Python `VUE_PROJECT` | 映射为业务值 `vue_project` |
| CodeGenType unspecified | `CODE_GEN_TYPE_UNSPECIFIED` | 默认降级为 `vue_project` 或明确报错，必须统一 |
| EventType agent_start | `AGENT_START` | 前端不展示或展示开始事件，不能破坏 stream |
| EventType ai_response | `AI_RESPONSE` | 转为前端 `AiResponseMessage` |
| EventType tool_request | `TOOL_REQUEST` | 转为前端 `ToolRequestMessage` |
| EventType tool_executed | `TOOL_EXECUTED` | 转为前端 `ToolExecutedMessage` |
| EventType error | `ERROR` | 转为前端可读错误 |
| EventType done | `DONE` | 触发完成收口 |

### 8.3 字段兼容用例

| 请求 | 字段 | 期望 |
|------|------|------|
| `CodeGenerationRequest` | `agent_run_id` | Java Long 到 Python string 不丢失 |
| `CodeGenerationRequest` | `app_id/session_id/user_id` | 非 0，和数据库一致 |
| `CodeGenerationRequest` | `prompt` | 中文、英文、换行、特殊字符不乱码 |
| `CodeGenerationRequest` | `workspace_path` | Windows/Unix 风格路径都不破坏 |
| `CodeGenerationRequest` | `model_config_id/config_version` | 正确传递，版本不匹配时能失败 |
| `CodeGenerationEvent` | `oneof payload` | 每个事件只设置对应 payload |
| `ToolRequestData.arguments` | JSON 字符串 | 前端可解析或可读展示 |

## 9. L2 Java 单元测试

### 9.1 `GrpcPythonAgentRuntime` 请求构造测试

建议新增测试类：

`backend-java/src/test/java/com/adcage/acaicodefree/grpc/client/GrpcPythonAgentRuntimeTest.java`

测试点：

| 用例 | 输入 | 期望 |
|------|------|------|
| 完整请求 | `agentRunId/appId/sessionId/loginUser/message/codeGenType/workspacePath/modelConfigId/configVersion` 全部存在 | gRPC request 字段完整 |
| 空可选字段 | `workspacePath/modelConfigId/configVersion` 为空 | 使用空字符串或 0，不抛 NPE |
| codeGenType 来自 enum | `CodeGenTypeEnum.VUE_PROJECT` | gRPC `VUE_PROJECT` |
| codeGenType 来自 app 字符串 | `app.codeGenType=multi-file` | gRPC `MULTI_FILE` |
| 未知 codeGenType | 非法字符串 | 按项目约定 fallback 到 `VUE_PROJECT` |

### 9.2 `GrpcPythonAgentRuntime` 事件映射测试

| Python gRPC Event | Java 输出 | 前端期望 |
|-------------------|-----------|----------|
| `AI_RESPONSE(text=...)` | `AiResponseMessage` JSON | 聊天流展示文本 |
| `TOOL_REQUEST` | `ToolRequestMessage` JSON | 展示工具准备调用 |
| `TOOL_EXECUTED` | `ToolExecutedMessage` JSON | 展示工具执行结果 |
| `ERROR(message=...)` | 错误 `AiResponseMessage` | 用户看到生成失败 |
| `DONE(message=completed)` | 完成消息或结束信号 | Java stream complete |
| `AGENT_START` | 可忽略 | 不应输出 null 到前端 |
| gRPC `onError` | 错误消息 + complete | 前端不能一直 loading |

### 9.3 `GrpcToolService` 测试

建议新增：

`backend-java/src/test/java/com/adcage/acaicodefree/grpc/server/GrpcToolServiceTest.java`

测试点：

| RPC | 正常用例 | 异常用例 |
|-----|----------|----------|
| `WriteFile` | 写入 `src/App.vue` 成功 | 空路径、非法路径、无权限 |
| `ReadFile` | 读取刚写入文件 | 文件不存在 |
| `ModifyFile` | old content 命中并替换 | old content 不存在 |
| `DeleteFile` | 删除文件成功 | 删除不存在文件 |
| `ReadDir` | 返回目录列表 | 目录不存在 |
| `StreamWriteFiles` | 多文件写入统计成功数 | 部分失败统计 failure_count |

重点断言：

- 不能允许 `../` 逃逸 workspace。
- appId 为空或 0 时不能写到错误目录。
- 异常应返回 gRPC `INTERNAL` 或明确业务错误，不应吞掉。

### 9.4 `GrpcPlatformService` 测试

建议新增：

`backend-java/src/test/java/com/adcage/acaicodefree/grpc/server/GrpcPlatformServiceTest.java`

测试点：

| RPC | 用例 | 期望 |
|-----|------|------|
| `GetModelConfig` | enabled 配置存在 | 返回 provider/model/baseUrl/apiKey |
| `GetModelConfig` | 配置不存在 | 返回空字段 |
| `GetModelConfig` | enabled=0 | 返回空字段 |
| `GetModelConfig` | configVersion 不匹配 | 返回空字段 |
| `BuildVueProject` | app 存在且代码有效 | success=true |
| `BuildVueProject` | app 不存在或构建失败 | success=false + errorMessage |
| `DeployApp` | user 存在 | success=true + url |
| `DeployApp` | user 不存在 | success=false |
| `CompleteAgentRun` | success=true | 调用 completeAgentRun |
| `CompleteAgentRun` | success=false | 调用 failAgentRun |
| `CreateAppVersion` | source/build 有效 | 返回 versionId |
| `GetChatHistory` | session 有历史 | 返回 entries |
| `UpdateAppCodeGenType` | 合法类型 | app.codeGenType 更新 |
| `GetAppDetail` | app 存在 | 返回 app 信息 |
| `GetUserInfo` | user 存在 | 返回用户基础信息 |

### 9.5 `GrpcInternalAuthInterceptor` 测试

这是安全高风险点，必须单独测试。

| 场景 | internalSecret | metadata | 期望 |
|------|----------------|----------|------|
| 未配置密钥 | 空 | 无 | 放行 |
| 配置密钥且正确 | `local-test-secret` | `x-internal-secret=local-test-secret` | 放行 |
| 配置密钥但缺失 | `local-test-secret` | 无 | `UNAUTHENTICATED` |
| 配置密钥但错误 | `local-test-secret` | `x-internal-secret=bad` | `UNAUTHENTICATED` |

## 10. L3 Python 单元测试

### 10.1 `CodeGenerationServicer` 测试

建议新增：

`agent-runtime-python/tests/grpc_server/test_code_generation_servicer.py`

测试点：

| 用例 | 输入 | 期望 |
|------|------|------|
| `ValidatePrompt` 正常 | `Create a Vue todo app` | `valid=True` |
| `ValidatePrompt` 空 | 空字符串 | `valid=False` |
| `ValidatePrompt` 超长 | 2001 字符 | `valid=False` |
| `ValidatePrompt` 注入关键词 | `ignore previous instructions` | `valid=False` |
| `StreamGenerate` 正常 | fake AgentService 输出 4 个事件 | gRPC stream 输出对应事件 |
| `StreamGenerate` 异常 | fake AgentService 抛异常 | 输出 `ERROR` event |
| `StreamModify` 正常 | 带 `original_content` | 输出 stream events |
| `RouteCodeGenType` 未实现 | 任意 prompt | `UNIMPLEMENTED` |

### 10.2 Python gRPC event 构造测试

直接测试 `_build_grpc_event`：

| AgentEvent | 期望 |
|------------|------|
| `eventType=ai_response` 且 data.content 存在 | `AiResponseData.text=content` |
| `eventType=tool_request` 且 arguments 是 dict | arguments 被转成字符串，不能崩 |
| `eventType=tool_executed` | result 正确传递 |
| `eventType=error` | ErrorData.message 正确 |
| `eventType=done` | DoneData.message 正确 |
| 未知 eventType | `EVENT_TYPE_UNSPECIFIED` |

### 10.3 `GrpcToolClient` 测试

建议新增：

`agent-runtime-python/tests/grpc_client/test_tool_client.py`

测试点：

- `single_file` 映射到 `SINGLE_FILE`。
- `multi-file` 映射到 `MULTI_FILE`。
- `vue_project` 映射到 `VUE_PROJECT`。
- 未知类型 fallback 行为明确。
- `write_file/read_file/modify_file/delete_file/read_dir` 请求字段正确。
- gRPC 错误能向上抛出，AgentService 能捕获并转成 error event。

### 10.4 `GrpcPlatformClient` 测试

建议新增：

`agent-runtime-python/tests/grpc_client/test_platform_client.py`

测试点：

- `get_model_config` 返回 dict 字段名和现有 `ChatModelFactory` 兼容。
- `build_vue_project` 返回 success/errorMessage。
- `deploy_app` 返回 success/url。
- `complete_agent_run` 返回 bool。
- `create_app_version` 返回 versionId。
- `get_chat_history` 返回 list。
- `get_app_detail` 返回 app 基础字段。

### 10.5 gRPC metadata 鉴权测试

建议新增：

`agent-runtime-python/tests/grpc_client/test_channel_metadata.py`

测试目标：

- Python 调 Java gRPC 时必须携带 `x-internal-secret` metadata。
- 不应把 internal secret 放到 `grpc.default_authority` 当作鉴权。
- 如果当前实现不支持 metadata，应先记录失败，再修复。

验收标准：

- Java `GrpcInternalAuthInterceptor` 可以读取到 metadata。
- 密钥错误时 Java 拒绝。
- 密钥正确时 Java 放行。

## 11. L4 本地双服务集成测试

### 11.1 启动顺序

1. 启动 Java 后端：

```powershell
cd E:/Programme/Project/protoflow-ai/backend-java
$env:AGENT_RUNTIME="python-agent"
$env:AGENT_RUNTIME_INTERNAL_SECRET="local-test-secret"
mvn spring-boot:run
```

2. 启动 Python Runtime：

```powershell
cd E:/Programme/Project/protoflow-ai/agent-runtime-python
$env:AGENT_INTERNAL_SECRET="local-test-secret"
$env:JAVA_GRPC_TARGET="localhost:9090"
$env:GRPC_SERVER_PORT="9091"
python -m uvicorn app.main:app --reload --port 9000
```

3. 验证端口：

```powershell
Get-NetTCPConnection -LocalPort 8700,9000,9090,9091
```

### 11.2 执行现有 smoke 脚本

```powershell
cd E:/Programme/Project/protoflow-ai/agent-runtime-python
python scripts/test_grpc_all.py
```

当前脚本主要打印 PASS/FAIL。建议后续改造为：

- 任一子项失败时进程 `exit(1)`。
- 输出 JSON 或 junit report。
- 可在 CI 中作为门禁。
- 不依赖固定 `app_id=1/user_id=1/model_config_id=1`，改为启动前自动查询或通过环境变量传入。

### 11.3 ToolService 集成用例

| 编号 | 步骤 | 期望 |
|------|------|------|
| T-01 | Python 调 Java `WriteFile(test_grpc.txt)` | 返回成功消息 |
| T-02 | Python 调 Java `ReadFile(test_grpc.txt)` | 内容等于写入内容 |
| T-03 | Python 调 Java `ModifyFile(test_grpc.txt, old, new)` | 返回成功，读取后内容变化 |
| T-04 | Python 调 Java `ReadDir(.)` | 能看到测试文件 |
| T-05 | Python 调 Java `DeleteFile(test_grpc.txt)` | 返回成功 |
| T-06 | 删除后再次 `ReadFile` | 返回 gRPC 错误 |
| T-07 | `relative_path=../escape.txt` | 必须失败，不能写出 workspace |
| T-08 | `StreamWriteFiles` 批量写 3 个文件 | success_count=3 |
| T-09 | 批量写入中一个非法路径 | success_count/failure_count 正确 |

### 11.4 PlatformService 集成用例

| 编号 | RPC | 数据 | 期望 |
|------|-----|------|------|
| P-01 | `GetModelConfig` | 有效 id + version | 返回 provider/model/baseUrl/apiKey |
| P-02 | `GetModelConfig` | 不存在 id | 返回空字段 |
| P-03 | `GetModelConfig` | 错误 version | 返回空字段 |
| P-04 | `GetAppDetail` | 有效 appId | 返回 app 信息 |
| P-05 | `GetAppDetail` | 不存在 appId | 返回 id=0 |
| P-06 | `GetUserInfo` | 有效 userId | 返回 user 信息 |
| P-07 | `GetUserInfo` | 不存在 userId | 返回 id=0 |
| P-08 | `GetChatHistory` | 有历史 sessionId | 返回 entries |
| P-09 | `CompleteAgentRun` | success=true | agent_run 状态 completed |
| P-10 | `CompleteAgentRun` | success=false | agent_run 状态 failed |
| P-11 | `BuildVueProject` | 有效 Vue app | success=true 或明确构建错误 |
| P-12 | `DeployApp` | 有效 app/user | 返回可访问 URL |
| P-13 | `CreateAppVersion` | 有效 source/build path | 返回 versionId |

### 11.5 CodeGenerationService 集成用例

| 编号 | RPC | 输入 | 期望 |
|------|-----|------|------|
| C-01 | `ValidatePrompt` | 正常 prompt | valid=true |
| C-02 | `ValidatePrompt` | 空 prompt | valid=false |
| C-03 | `ValidatePrompt` | 超长 prompt | valid=false |
| C-04 | `ValidatePrompt` | 注入关键词 | valid=false |
| C-05 | `StreamGenerate` | 无模型配置 | fallback 或明确 error event |
| C-06 | `StreamGenerate` | 有效模型配置 | 输出 ai_response/tool_request/tool_executed/done |
| C-07 | `StreamGenerate` | Java ToolService 不可用 | 输出 error event，不崩溃 |
| C-08 | `StreamModify` | 有 original content | 输出修改相关事件 |
| C-09 | `RouteCodeGenType` | 任意 prompt | 当前如未实现，应返回 UNIMPLEMENTED |

## 12. L5 Java SSE 全链路 E2E

### 12.1 执行目标

验证前端实际依赖的 Java SSE 接口仍然稳定，不因为 gRPC 改造破坏前端协议。

接口：

```http
GET /app/chat/gen/code/stream?appId=<appId>&sessionId=<sessionId>&message=<message>
```

必须验证：

- SSE 响应 HTTP 200。
- 包含 `event:meta`。
- 包含至少一个 `event:message`。
- 成功时包含 `event:done`。
- 失败时包含明确错误消息，且 stream 结束。
- Java 不把 gRPC 内部字段原样泄漏给前端。

### 12.2 后端自动化测试命令

```powershell
cd E:/Programme/Project/protoflow-ai/backend-java
mvn test -Dtest=PythonAgentE2ETest,AppChatE2ETest,AgentRunServiceImplTest,ModelConfigServiceImplTest
```

gRPC 改造完成后，建议新增 gRPC 专用 E2E：

```powershell
mvn test -Dtest=GrpcPythonAgentRuntimeTest,GrpcToolServiceTest,GrpcPlatformServiceTest,GrpcInternalAuthInterceptorTest
```

### 12.3 SSE 内容验收

示例期望片段：

```text
event:meta
data: {"sessionId":...}

event:message
data: {"type":"ai_response",...}

event:message
data: {"type":"tool_request",...}

event:message
data: {"type":"tool_executed",...}

event:done
data: ...
```

### 12.4 数据库验收

每次生成后检查：

```sql
SELECT id, appId, userId, title, messageCount, lastMessageTime
FROM chat_session
WHERE id = <sessionId>;

SELECT id, sessionId, seqNo, messageType, status, LEFT(message, 200) AS message_preview
FROM chat_history
WHERE sessionId = <sessionId>
ORDER BY seqNo;

SELECT id, appId, sessionId, userId, runtime, status, modelConfigId, configVersion, workspacePath, latencyMs, errorMessage
FROM agent_run
WHERE id = <agentRunId>;

SELECT id, appId, agentRunId, sourcePath, buildPath
FROM app_version
WHERE agentRunId = <agentRunId>;
```

验收规则：

- `chat_session.messageCount` 与历史条数一致。
- `chat_history` 至少有 user 和 ai 两条。
- `chat_history.seqNo` 从 1 开始连续。
- 成功生成时 ai 消息 `status=success`。
- 构建失败但生成过程完成时，ai 消息可为 `failed`，但必须有可读失败原因。
- `agent_run.runtime=python-agent`。
- `agent_run.modelConfigId/configVersion` 与请求一致。
- `agent_run.workspacePath` 指向真实目录。

### 12.5 文件系统验收

检查：

```powershell
Get-ChildItem -Recurse E:/Programme/Project/protoflow-ai/storage/agent-workspaces/<agentRunId>/source
```

期望：

- Vue 项目至少包含 `src/App.vue`。
- 多文件生成至少包含约定入口文件。
- 不存在 `.env`、密钥文件、无关临时文件被打包或暴露。
- 文件内容与 prompt 有明显相关性，不是固定 skeleton。

## 13. L6 浏览器 E2E 测试

### 13.1 启动前端

```powershell
cd E:/Programme/Project/protoflow-ai/frontend-vue
npm run dev
```

访问：

```text
http://localhost:5173
```

### 13.2 核心用户流程

| 编号 | 流程 | 验收 |
|------|------|------|
| B-01 | 登录 | 登录态正常，刷新不丢 |
| B-02 | 创建应用 | 应用创建成功，跳转生成页 |
| B-03 | 创建会话 | 会话列表新增，标题不重复 |
| B-04 | 发送 prompt | 输入框进入生成状态 |
| B-05 | 流式展示 | AI 文本逐步出现 |
| B-06 | 工具事件展示 | 能看到写文件等工具事件 |
| B-07 | 生成完成 | loading 结束，done 触发 |
| B-08 | 预览 | iframe 或预览区域展示生成页面 |
| B-09 | 历史恢复 | 刷新页面后消息仍存在 |
| B-10 | 下载 | zip 可下载，且不包含 `.env` |
| B-11 | 部署 | 返回静态访问 URL |

### 13.3 三类生成模式

必须分别验证：

1. `single_file`
   - prompt：`生成一个单文件登录页，包含用户名、密码和登录按钮`
   - 期望：生成 `index.html` 或项目约定单文件输出。

2. `multi-file`
   - prompt：`生成一个多文件待办事项页面，拆分 HTML、CSS、JS`
   - 期望：生成多文件结构，预览正常。

3. `vue_project`
   - prompt：`生成一个 Vue 个人作品集首页，包含头像、项目卡片和联系方式`
   - 期望：写入 `src/App.vue`，构建或预览路径清楚。

### 13.4 前端错误体验

| 异常 | 操作 | 期望 |
|------|------|------|
| Python gRPC 未启动 | 发送生成请求 | 前端显示生成失败，不一直 loading |
| Java gRPC 未启动 | Python 生成中调用工具 | 前端显示工具失败或生成失败 |
| 模型配置无效 | 使用不存在配置 | 前端显示模型配置错误 |
| prompt 为空 | 点击发送 | 前端阻止或后端返回参数错误 |
| stream 中断 | 手动停止 Python | 前端结束 loading 并显示错误 |

## 14. L7 稳定性、并发和异常注入

### 14.1 连续稳定性测试

执行 10 次连续生成：

| 次数 | appId | sessionId | agentRunId | 结果 | 用时 | 日志错误 |
|------|-------|-----------|------------|------|------|----------|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |
| 6 | | | | | | |
| 7 | | | | | | |
| 8 | | | | | | |
| 9 | | | | | | |
| 10 | | | | | | |

通过标准：

- 10 次中至少 10 次都有明确结束状态。
- 不允许出现永远 running 的 `agent_run`。
- 不允许出现空白 ai 历史。
- 不允许出现无法解释的 gRPC channel 泄漏或端口占用。

### 14.2 并发测试

建议并发档位：

| 档位 | 并发数 | 目的 |
|------|--------|------|
| 小并发 | 3 | 验证基本互不干扰 |
| 中并发 | 5 | 验证 channel、数据库和文件写入 |
| 高一点的本地并发 | 10 | 暴露 race condition，不作为首次门禁 |

重点检查：

- 每个请求有独立 `agentRunId`。
- 每个请求写入独立 workspace。
- 不同用户之间不能读写对方应用文件。
- `chat_history.seqNo` 不重复。
- `ToolService` 不发生路径串写。
- Python gRPC server 不出现 event loop blocked。

### 14.3 异常注入矩阵

| 编号 | 注入方式 | 期望 |
|------|----------|------|
| F-01 | Python gRPC server 未启动 | Java 返回可读错误，SSE 完成 |
| F-02 | Java gRPC server 未启动 | Python 输出 error event |
| F-03 | internal secret 错误 | Java 返回 `UNAUTHENTICATED`，日志清楚 |
| F-04 | model_config 不存在 | Python 无法创建模型，返回 error 或 fallback |
| F-05 | model_config disabled | 不允许继续真实模型调用 |
| F-06 | configVersion 不匹配 | 返回空配置或明确版本错误 |
| F-07 | 模型 API Key 为空 | 返回模型配置错误 |
| F-08 | 模型接口超时 | stream error，AgentRun failed |
| F-09 | 写文件路径非法 | ToolService 拒绝 |
| F-10 | 写文件中途失败 | tool_executed 不应伪造成功 |
| F-11 | 构建失败 | chat_history 可读说明失败原因 |
| F-12 | 前端刷新页面 | 历史消息可恢复 |
| F-13 | 用户未登录 | Java 返回未登录，不进入 gRPC |
| F-14 | 用户访问他人 app | Java 拒绝，不进入 Python 执行 |

### 14.4 超时和资源测试

需要验证：

- gRPC 调用有 deadline 或合理超时策略。
- Python 模型请求超时不会永久占用 stream。
- Java Reactor sink 在 gRPC onError 后 complete。
- Python channel 可关闭，服务退出时不残留端口。
- FastAPI lifespan 停止时 gRPC server 执行 `stop(grace=5)`。

## 15. 日志和排障规范

### 15.1 必读日志

每次 E2E 失败先读：

```powershell
Get-Content E:/Programme/Project/protoflow-ai/logs/backend.log -Tail 200
Get-Content E:/Programme/Project/protoflow-ai/logs/agent-python.log -Tail 200
```

### 15.2 关键搜索词

Java：

```powershell
Select-String -Path logs/backend.log -Pattern "gRPC|Grpc|agent_run|modelConfig|workspacePath|/app/chat/gen/code/stream|ERROR|WARN" -Context 2,4
```

Python：

```powershell
Select-String -Path logs/agent-python.log -Pattern "grpc|StreamGenerate|tool_request|tool_executed|agent_run_id|ERROR|WARN" -Context 2,4
```

### 15.3 关联字段

排障时必须把以下字段串起来：

- `appId`
- `sessionId`
- `agentRunId`
- `userId`
- `modelConfigId`
- `configVersion`
- `workspacePath`
- Python request id，如果日志中存在

### 15.4 常见问题定位路径

| 现象 | 优先检查 |
|------|----------|
| 前端一直 loading | Java SSE 是否 complete，gRPC onError 是否 complete sink |
| 前端收到空消息 | `GrpcPythonAgentRuntime` event 映射 |
| 工具事件不显示 | `TOOL_REQUEST/TOOL_EXECUTED` 是否转成前端 JSON |
| 生成文件不存在 | Python 是否调用 `GrpcToolClient.write_file`，Java ToolService 是否成功 |
| 模型配置为空 | `PlatformService.GetModelConfig`、configVersion、enabled |
| Java 拒绝 Python 调用 | `GrpcInternalAuthInterceptor` metadata |
| 数据库字段错误 | `logs/backend.log` 中 SQL exception |
| Python import gRPC 失败 | `grpcio` 和生成代码版本 |
| 端口启动失败 | `Get-NetTCPConnection` 查 9090/9091 |

## 16. 推荐执行命令清单

### 16.1 Java 快速门禁

```powershell
cd E:/Programme/Project/protoflow-ai/backend-java
mvn test -Dtest=ModelConfigServiceImplTest,AgentRunServiceImplTest
mvn test -Dtest=AppChatE2ETest,PythonAgentE2ETest
mvn clean package -DskipTests
```

### 16.2 Python 快速门禁

```powershell
cd E:/Programme/Project/protoflow-ai/agent-runtime-python
python -m pytest tests/services/test_agent_service.py tests/agent/test_graph.py tests/api/test_code_generation_stream.py
python -m pytest
```

### 16.3 gRPC 集成门禁

```powershell
cd E:/Programme/Project/protoflow-ai/agent-runtime-python
python scripts/test_grpc_all.py
python scripts/test_grpc_platform.py
python scripts/test_grpc_data_check.py
```

### 16.4 前端门禁

```powershell
cd E:/Programme/Project/protoflow-ai/frontend-vue
npm run type-check
npm run build
```

### 16.5 代码卫生

```powershell
cd E:/Programme/Project/protoflow-ai
git diff --check
git status --short
```

## 17. 建议新增自动化测试文件

### 17.1 Java

| 文件 | 目的 |
|------|------|
| `backend-java/src/test/java/com/adcage/acaicodefree/grpc/client/GrpcPythonAgentRuntimeTest.java` | Java 调 Python 的请求构造和事件映射 |
| `backend-java/src/test/java/com/adcage/acaicodefree/grpc/server/GrpcToolServiceTest.java` | Java ToolService RPC 行为 |
| `backend-java/src/test/java/com/adcage/acaicodefree/grpc/server/GrpcPlatformServiceTest.java` | Java PlatformService RPC 行为 |
| `backend-java/src/test/java/com/adcage/acaicodefree/grpc/server/GrpcInternalAuthInterceptorTest.java` | gRPC 内部鉴权 |
| `backend-java/src/test/java/com/adcage/acaicodefree/controller/GrpcPythonAgentE2ETest.java` | gRPC runtime 模式下 Java SSE 全链路 |

### 17.2 Python

| 文件 | 目的 |
|------|------|
| `agent-runtime-python/tests/grpc_server/test_code_generation_servicer.py` | Python CodeGenerationService |
| `agent-runtime-python/tests/grpc_client/test_tool_client.py` | Python ToolService client |
| `agent-runtime-python/tests/grpc_client/test_platform_client.py` | Python PlatformService client |
| `agent-runtime-python/tests/grpc_client/test_channel_metadata.py` | internal secret metadata |
| `agent-runtime-python/tests/integration/test_grpc_roundtrip.py` | 双服务真实 roundtrip |

### 17.3 脚本改造

建议把：

- `agent-runtime-python/scripts/test_grpc_all.py`
- `agent-runtime-python/scripts/test_grpc_platform.py`
- `agent-runtime-python/scripts/test_grpc_data_check.py`

逐步改成：

- pytest 集成测试。
- 支持环境变量 `TEST_APP_ID`、`TEST_USER_ID`、`TEST_MODEL_CONFIG_ID`。
- 任一断言失败直接退出非 0。
- 输出明确失败 RPC、请求参数、响应和耗时。

## 18. 风险清单

| 风险 | 严重级别 | 判断依据 | 缓解方式 |
|------|----------|----------|----------|
| gRPC internal secret 没有通过 metadata 发送 | 高 | Java 拦截器读取 `x-internal-secret`，Python channel 当前需要重点确认 | 增加 metadata 测试并修复 client interceptor |
| 现有 E2E 仍覆盖旧 HTTP Python Runtime | 高 | `PythonAgentE2ETest` 历史上使用旧 `PythonAgentRuntime` mock HTTP SSE | 新增 gRPC 专用 E2E |
| smoke 脚本只打印失败不阻断 CI | 中 | `test_grpc_all.py` 当前偏人工检查 | 改 pytest 或失败 exit(1) |
| 固定 appId/userId/modelConfigId 导致环境不稳定 | 中 | 本地数据库数据可能不同 | 测试自动造数或环境变量注入 |
| gRPC stream onError 后 Java SSE 不 complete | 高 | 前端会一直 loading | 单测覆盖 onError complete |
| Python 工具调用写错 workspace | 高 | 双向 gRPC 后路径边界更重要 | 增加路径逃逸和用户隔离测试 |
| configVersion 不匹配仍继续调用模型 | 中 | 会使用旧配置或错误 key | PlatformService 测试版本校验 |
| 模型调用波动影响测试稳定性 | 中 | 外部 API 不稳定 | 自动化测试使用 fake model，人工 E2E 才跑真实模型 |
| 生成代码构建耗时过长 | 中 | Vue build 会拖慢 E2E | 区分快速门禁和完整回归 |

## 19. 推荐测试执行顺序

### 19.1 每次提交前

```powershell
cd backend-java
mvn test -Dtest=ModelConfigServiceImplTest,AgentRunServiceImplTest

cd ../agent-runtime-python
python -m pytest tests/services/test_agent_service.py tests/agent/test_graph.py

cd ..
git diff --check
```

### 19.2 gRPC 改造合入前

```powershell
cd backend-java
mvn test

cd ../agent-runtime-python
python -m pytest

cd ../frontend-vue
npm run build
```

然后启动 Java/Python 双服务，执行：

```powershell
cd E:/Programme/Project/protoflow-ai/agent-runtime-python
python scripts/test_grpc_all.py
```

再做 1 次浏览器完整 E2E。

### 19.3 发布前完整回归

1. `mvn test`
2. `python -m pytest`
3. `npm run build`
4. gRPC 双服务集成测试
5. 浏览器 E2E 三类生成模式
6. 10 次连续生成稳定性
7. 3 路并发生成
8. 异常注入：Python 停服、Java gRPC 停服、密钥错误、模型配置错误
9. 日志复查
10. `git diff --check`

## 20. 测试记录模板

每次完整测试建议记录到 `docs/releases/` 或对应版本验证文档：

```markdown
# gRPC AI 对话验证记录

## 环境

- 日期：
- Git commit：
- Java：
- Python：
- Node：
- MySQL：
- Redis：
- Java HTTP：
- Java gRPC：
- Python HTTP：
- Python gRPC：
- Frontend：

## 数据

- userId：
- appId：
- sessionId：
- agentRunId：
- modelConfigId：
- configVersion：

## 自动化结果

- Java tests：
- Python tests：
- Frontend build：
- gRPC scripts：
- git diff --check：

## 浏览器 E2E

- single_file：
- multi-file：
- vue_project：
- 预览：
- 下载：
- 部署：

## 异常注入

- Python gRPC down：
- Java gRPC down：
- internal secret wrong：
- model config invalid：
- write file failed：

## 日志证据

- backend.log 关键片段：
- agent-python.log 关键片段：

## 结论

- 是否通过：
- 未解决风险：
- 后续动作：
```

## 21. 最终验收清单

- [ ] `proto` 文件是唯一契约源，两端生成代码已更新。
- [ ] Java `mvn test` 通过。
- [ ] Python `python -m pytest` 通过。
- [ ] Frontend `npm run build` 通过。
- [ ] `GrpcPythonAgentRuntime` 请求字段完整。
- [ ] `GrpcPythonAgentRuntime` 能正确处理 `onNext/onError/onCompleted`。
- [ ] `GrpcToolService` 所有工具 RPC 正常。
- [ ] `GrpcPlatformService` 所有平台 RPC 正常。
- [ ] `GrpcInternalAuthInterceptor` 鉴权正常。
- [ ] `CodeGenerationService.StreamGenerate` 正常输出事件流。
- [ ] Python 调 Java gRPC 使用正确 metadata。
- [ ] `/app/chat/gen/code/stream` 前端协议兼容。
- [ ] `chat_history` 落库可读，不保存难读的内部原始事件。
- [ ] `agent_run` 状态准确。
- [ ] 生成文件真实存在。
- [ ] 构建或构建失败原因可追踪。
- [ ] 浏览器端完整生成流程通过。
- [ ] 连续 10 次生成无挂起任务。
- [ ] 3 路并发无串数据。
- [ ] Python 停服、Java gRPC 停服、密钥错误均有明确错误反馈。
- [ ] `logs/backend.log` 和 `logs/agent-python.log` 无未解释 ERROR。

## 22. 当前优先级建议

建议按以下优先级补测试：

1. 先补 `GrpcInternalAuthInterceptor` 和 Python metadata 测试，因为这是安全和可用性的共同风险。
2. 再补 `GrpcPythonAgentRuntime` 单测，锁死 Java 到 Python 的请求字段和事件映射。
3. 再把 `scripts/test_grpc_all.py` 改造成失败即退出的 pytest 集成测试。
4. 再补 Java `GrpcToolService` 和 `GrpcPlatformService` 单测。
5. 最后补浏览器 E2E 和并发稳定性脚本。

这样可以先把最大的不确定性收住，再逐步扩大到完整链路。
