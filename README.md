# 原象 Morpha — AI 驱动的创意创作平台

用对话驱动创意，从网站到幻灯片，让 AI 帮你把想法变成真实可用的作品。

基于 **Spring Boot 3 + Vue 3 + Python LangGraph** 分层架构。用户通过自然语言描述需求，多智能体协作体系自主完成需求分析、架构规划、代码实现、质量校验全流程，实现"描述想法 → AI 协作创作 → 实时预览 → 社区分享 → 一键部署"全链路闭环。

---

## 完整技术栈

### Java 后端（控制面）

| 类别 | 技术 |
|------|------|
| 核心框架 | Spring Boot 3.5.5 / Java 17 |
| ORM | MyBatis-Flex 1.11.0 |
| 数据库 | MySQL 5.7+（HikariCP 连接池） |
| 缓存 | Redis + Redisson 3.45.1 + Caffeine |
| 分布式会话 | Spring Session Data Redis |
| gRPC | grpc-spring-boot-starter 3.1.0 / grpc 1.63.0 / protobuf 3.25.5 |
| 响应式 | Project Reactor（Flux / Sinks） |
| 文档 | Knife4j (Swagger) 4.4.0 |
| 对象存储 | 腾讯云 COS（可选，支持本地回退） |
| 截图 | Selenium 4.33.0 + WebDriverManager 6.1.0 |
| 工具库 | Hutool 5.8.38 / Lombok 1.18.38 |

### Python AI Runtime（执行面）

| 类别 | 技术 |
|------|------|
| 语言运行时 | Python 3.11+ |
| AI 编排 | LangGraph >= 0.2.0（StateGraph） |
| LLM 接口 | langchain-core >= 0.3.0 + langchain-openai >= 0.2.0 |
| Web 框架 | FastAPI >= 0.115.0 + uvicorn >= 0.30.0 |
| 数据验证 | Pydantic + pydantic-settings >= 2.8.0 |
| gRPC | grpcio + grpcio-tools >= 1.81.1 |
| 监控 | prometheus_client >= 0.20.0（/metrics 端点） |
| 代码质量 | ruff >= 0.6.0 |

### 前端

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3（Composition API + `<script setup>`）|
| 语言 | TypeScript ~5.8.0 |
| 构建 | Vite ^7.0.6（HMR）|
| UI 库 | Ant Design Vue ^4.2.6（全站暖色主题，品牌绿 #22C55E）|
| 状态管理 | Pinia ^3.0.3 |
| 路由 | Vue Router ^4.5.1（自动发现路由文件）|
| HTTP | Axios ^1.11.0（Cookie 认证）|
| 图标 | Lucide Vue ^1.18.0 |
| API 生成 | @umijs/openapi ^1.14.1（Swagger → TS 自动生成）|
| 类型检查 | vue-tsc ^3.0.4 |
| E2E | Playwright ^1.60.0 |

---

## 系统架构

```
┌──────────────────────┐      SSE / HTTP       ┌──────────────────────┐       gRPC 双向       ┌──────────────────────────┐
│   Vue 3 前端          │ ◄──────────────────► │  Java 后端            │ ◄───────────────────► │  Python AI Runtime       │
│  (Ant Design 暖色主题) │  EventSource + Axios  │  (Spring Boot 3.5.5)  │ 9090 ↔ 9091         │  (LangGraph + FastAPI)   │
│  端口 5173            │                       │  端口 8700 / 9090     │                       │  端口 8000 / 9091       │
└──────────────────────┘                       └──────────────────────┘                       └──────────────────────────┘
```

项目采用 **Java 控制面 + Python AI 执行面的严格分层架构**，所有 AI 核心能力强制在 Python 层实现，Java 仅保留平台控制和基础设施能力。

### Java 控制面职责

- **API 层**：应用/用户/会话/文件/健康等端点组，`@AuthCheck` 注解 AOP 权限
- **业务层**：AppService / UserService / AgentRunService / ScreenshotService / PythonTitleGenerationService
- **gRPC Server**（被 Python 调用）：GrpcPlatformService（模型配置/构建/部署/AgentRun/聊天历史等）、GrpcToolService（文件读写删改）
- **gRPC Client**（调用 Python）：GrpcPythonAgentRuntime（代码生成流/修改流/标题生成等）
- **基础设施**：Selenium 截图 + COS 存储 + Redisson 分布式限流 + UpdateChain 字段保护

### Python AI 执行面职责

所有 AI 核心能力。禁止在 Java 侧新增任何 AI 推理入口。

- **vNext 多智能体体系**：Conductor（指挥家）→ Planner（规划师）→ Implementor（实现者）→ Validator（校验师）协作流水线
- **Agent Loop**（LangGraph StateGraph）：6 节点 × 4 模式循环编排（Route / Plan / Implement / Validate）
- **Prompt 系统**：7 Profile × 20+ 可组合 PromptModule + 动态工具摘要
- **轻量 AI 服务**：LightweightAiService（标题生成 / 提示词增强），优先使用 LIGHT 模型角色
- **工具系统**：ResolvedToolSet 三合一（模型绑定 + 摘要 + 执行），按模式分派权限，WriteTool allowed_prefix 目录隔离
- **迭代循环 Runner**：流式模型调用 → 文本实时发射 → 工具执行 → 循环，支持 AskUser 暂停恢复

### gRPC 通信协议

| 方向 | 服务 | 方法 |
|------|------|------|
| Java → Python | CodeGenerationService | StreamGenerate、StreamModify、RouteCodeGenType、ValidatePrompt、EnhancePrompt、GenerateAppTitle、GenerateSessionTitle |
| Python → Java | PlatformService | GetModelConfig / ResolveRuntimeModelBundle / BuildVueProject / DeployApp / CompleteAgentRun / CreateAppVersion / GetChatHistory / UpdateAppCodeGenType / GetAppDetail / GetUserInfo |
| Python → Java | ToolService | ReadFile / WriteFile / ModifyFile / DeleteFile / ReadDir / StreamWriteFiles |

所有 gRPC 调用携带 `x-internal-secret` metadata 认证。

---

## 多智能体协作体系

```
用户需求 → Conductor（指挥家）
              ├─ 分析需求（AskUser 对话）
              ├─ 派遣 Planner → 输出 .agent/spec.md
              ├─ 派遣 Implementor → 代码实现 + 构建验证
              └─ 派遣 Validator → 质量校验 + 小问题修复
                    ↓
              汇总结果 → 向用户汇报
```

### Agent 角色

| Agent | 职责 | 工具权限 |
|-------|------|---------|
| **Conductor** | 需求分析、调度子 Agent、汇总结果 | Read + Write（.agent/ only）+ AskUser + DelegateToAgent |
| **Planner** | 技术规划，输出 .agent/spec.md | Read + Write + Glob + Grep |
| **Implementor** | 代码实现与构建验证 | 完整读写 + 终端命令 + Skill 加载 |
| **Validator** | 对照 spec 检查完整性，小问题 Edit 修复 | Read + Edit + Glob + Grep + Bash |

### 迭代循环 Runner

vNext Runner 采用迭代循环模式：

```
创建 Workspace → 构建工具集 → 解析模型 → 构建提示词 → 绑定工具
    ↓
while True:
    流式调用模型 → 文本实时发射(TEXT_DELTA)
    if 无 tool_calls → 退出
    执行工具 → 结果反馈 → 继续循环
    if AskUser 暂停 → 退出等待恢复
```

### AGENT_START 事件流

子 Agent 派遣时发射 AGENT_START 事件，全链路传递：

```
Python DelegateTool → RuntimeEventType.AGENT_START → gRPC ProtoEventType.AGENT_START
→ Java AgentStartMessage → SSE agent_start → 前端 currentAgent 状态更新
```

---

## AI Agent Loop 核心架构

### 四模式职责

| 模式 | 工具权限 | 职责 |
|------|---------|------|
| **Route** | 只读 + decide_route | 路由决策节点，初始分配和方向变更 |
| **Plan** | 只读 + 提问 + 写计划文件 | 7 阶段严格状态机规划 |
| **Implement** | 完整读写 + 终端命令 | 按 generationMode 分派实现 Agent |
| **Validate** | 只读 + run_checks | 8 项确定性检查 → 结构化校验报告 |

### V2 状态模型

5 个独立分区，各自有写权限校验，支持序列化持久化用于暂停/恢复：

| 分区 | 核心字段 |
|------|---------|
| Plan | plan_stage、requirement_brief、implementation_plan |
| Execution | files_touched、implement_phase_files、call_budget |
| Validation | validate_iterations、validation_status、validation_issues |
| Routing | route_decided、route_decision |
| Conversation | conversation_messages |

---

## 运行时模型配置

支持 primary / light / critic / repair 四角色模型配置，通过 `app.ai.runtime-models` 统一管理：

- 轻量任务（标题生成、提示词增强）使用 LIGHT 角色，降低成本
- 代码生成使用 PRIMARY 角色，保证质量
- 各角色支持逐级回退到 PRIMARY
- URL 安全标准化（协议校验、去尾斜杠、折叠重复斜杠）

---

## 前端功能

| 页面 | 功能 |
|------|------|
| 首页 | Hero + 风格模板 + Bento Grid 功能展示 + 精选案例 |
| AI 创作工作台 | 左聊天区（智能体身份 + 工具调用浮层 + 附件上传）+ 右 iframe 实时预览（桌面/移动端切换） |
| 我的作品 | 卡片网格 + 公开/取消公开 + IntersectionObserver 无限滚动 |
| 探索广场 | 分类浏览 + 排序 + Fork 跳转 |
| Token 仪表盘 | 用量统计与可视化 |
| 定价方案 | 免费 / 专业 / 企业三档 |
| 文档中心 | 产品文档 |
| 登录/注册 | AuthShell 认证外壳 + 双栏品牌布局 |

### 核心交互

- **SSE 流式对话**：AI 文本实时渲染 + 工具调用进度浮层 + 智能体身份徽标切换
- **AskUser 暂停恢复**：AI 主动提问 → 用户回答 → 无缝继续生成
- **应用公开与社区**：一键公开到探索广场、Fork 社区作品自动跳转
- **AI 自动命名**：创建应用时 AI 生成标题，首条消息后自动重命名会话

---

## 安全体系

| 层级 | 防护 |
|------|------|
| 网络层 | gRPC x-internal-secret metadata 认证 |
| 路径层 | normalize() + startsWith() 校验，路径穿越拦截 |
| 文件层 | 关键配置文件禁止删除 |
| 命令层 | Shell 链接符拦截 + 白名单 + 只读/写模式分离 |
| API 层 | @AuthCheck 注解 + AOP + 应用所有者校验 |
| 限流层 | Redisson 分布式限流（方法/用户/IP 三级）|
| 注入层 | ValidatePrompt 注入检测 |
| 工具层 | 写文件循环拦截 + ResolvedToolSet 权限 + WriteTool 目录隔离 |
| 状态层 | 序列化敏感数据脱敏 |

---

## 数据库设计

| 表 | 核心字段 |
|----|---------|
| user | userAccount, userPassword(加密), userRole, vipExpireTime |
| app | appName, codeGenType, generationMode, styleTemplate, deployKey, isPublic, forkCount, cover |
| chat_session | appId, userId, title, messageCount, modelName |
| chat_history | sessionId, seqNo, message(MEDIUMTEXT), messageType |
| agent_run | appId, sessionId, runtime, status, workspacePath, loopStateJson(TEXT), latencyMs, inputTokens, outputTokens |
| app_version | appId, agentRunId, versionNo, sourcePath, buildPath |
| app_category | appId, category |

全部雪花算法主键 + 逻辑删除 + 统一时间审计。

---

## 本地开发

三个服务均支持代码修改后自动热重载，**严禁手动重启**。

```bash
# Java 后端（端口 8700 / gRPC 9090）
cd backend-java && mvn spring-boot:run

# Python AI Runtime（FastAPI 8000 / gRPC 9091）
cd agent-runtime-python && uvicorn app.main:app --reload --port 8000

# 前端（端口 5173）
cd frontend-vue && npm install && npm run dev
```

## 测试

```bash
# Python（全量单测 + lint）
cd agent-runtime-python && pytest && ruff check .

# Java
cd backend-java && mvn test

# 前端（类型检查 + lint）
cd frontend-vue && npm run type-check && npm run lint
```
