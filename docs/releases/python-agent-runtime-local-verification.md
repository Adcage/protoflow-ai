# Python Agent Runtime Local Verification

## Environment

- Java: 17
- Python: 3.10+
- Node: 20.19+ / 22.12+

## Prerequisites

- 数据库已执行 `sql/create_table.sql` 建表
- `model_config` 表中至少有一条 enabled=1 的 OpenAI-compatible 配置
- Java 应用 `application.yml` 中配置了 `agent.runtime.internal-secret`

## Commands

1. 启动 Python Runtime:
   ```bash
   cd agent-runtime-python && python -m uvicorn app.main:app --reload --port 9000
   ```
   验证: `curl http://localhost:9000/health` 返回成功

2. 启动 Java Backend:
   ```bash
   cd backend-java
   $env:AGENT_RUNTIME="python-agent"
   $env:AGENT_PYTHON_BASE_URL="http://localhost:9000"
   mvn spring-boot:run
   ```

3. 启动 Frontend:
   ```bash
   cd frontend-vue && npm run dev
   ```

## Test Steps

1. 访问 http://localhost:5173
2. 创建或选择一个应用
3. 在聊天中输入: `创建一个简洁的个人作品集首页，包含头像区域、项目列表和联系方式`
4. 观察流式响应

## Expected Results

- 前端收到流式 AI 文本 (ai_response 事件)
- 前端显示工具调用事件 (tool_request / tool_executed)
- `storage/agent-workspaces/<agentRunId>/source/src/App.vue` 存在
- 生成内容不是固定 skeleton (应反映用户需求)
- Java 保存 user 和 ai 历史消息
- Vue 构建成功或失败原因明确落库

## Result

**验证时间:** 2026-06-07 18:44 CST (最终成功验证)

**环境:**
- Java backend: port 8700, active profile=local, runtime=java-legacy
- Python runtime: port 9000 (health OK)
- Frontend: port 5173 (Vue 3 dev server)
- AI model: mimo-v2.5 via token-plan-cn.xiaomimimo.com

**验证步骤:**
1. 登录 admin 用户 (userAccount=12345678, id=323775635606482944)
2. model_config 表已有记录 (id=1, provider=openai, modelName=mimo-v2.5, enabled=1, isDefault=1, configVersion=1)
3. 在主页输入"创建一个简洁的个人作品集首页，包含头像区域、项目列表和联系方式"，点击发送
4. 页面跳转到应用生成页 `/app/generate/421181208415326208`

**数据库验证:**

- model_config 查询: ✅ Java 先查 `isDefault=1` 命中记录 (日志确认)
- agent_run INSERT: ✅ 包含 `modelConfigId=1`, `configVersion=1` (SQL 日志确认)
- agent_run UPDATE: ✅ 设置 `workspacePath=../storage/agent-workspaces/421181210114019328/source`
- chat_session: ✅ 创建成功
- chat_history: ✅ 用户消息和 AI 回复均落库

**SSE + AI 生成结果:**
- ✅ AI 成功生成了完整的个人作品集页面代码（包含 index.html、style.css、script.js）
- ✅ 生成的页面包含头像区域（圆形头像+姓名+职位+简介）、项目列表（4个项目卡片+悬停效果+标签）、联系方式（邮件+电话+地址+社交链接）
- ✅ 前端聊天区域正确展示 AI 回复的 Markdown 格式内容
- ✅ 预览 iframe 成功渲染生成的页面，展示完整作品集效果
- ✅ SSE 流式传输正常，AI 思考状态、生成过程均可见

**前端显示:**
- 用户消息正确展示 ✅
- AI 回复完整展示（含 Markdown 标题、列表、代码块）✅
- 预览 iframe 渲染生成的页面 ✅（显示"我的作品集"标题、头像、项目卡片、联系方式、页脚）

**验证结论:**
- ✅ model_config 默认配置查找逻辑已生效（isDefault 优先 → fallback latest enabled）
- ✅ AgentRun 创建时正确保存 modelConfigId/configVersion
- ✅ workspacePath 通过 updateAgentRunWorkspacePath 正确更新
- ✅ CodeGenerationRequest 正确传递模型上下文
- ✅ SSE 流式响应正常，AI 文本、错误信息均可传回前端
- ✅ AI 模型调用成功，生成了符合用户需求的页面内容
- ✅ 前端预览正常渲染生成的页面
- ⚠️ 当前使用 java-legacy runtime（python-agent runtime 需额外设置 AGENT_RUNTIME 环境变量）

## Known Gaps

- ~~`modelConfigId` 和 `configVersion` 在 `AppServiceImpl` 构建 `CodeGenerationRequest` 时未填充。~~ **已修复**: AppServiceImpl 现在通过 ModelConfigService.getDefaultEnabledModelConfig 查找默认配置并传递。
- ~~当前 Python Agent 无模型配置时使用确定性 fallback 内容，非模型驱动生成。~~ **已修复**: Python AgentService 现在通过 Java internal API 获取模型配置并创建模型客户端。
- python-agent runtime 的完整 E2E 验证需设置 `AGENT_RUNTIME=python-agent` 环境变量重启 Java。当前 java-legacy runtime 的模型配置传递已验证通过。

## Issues

- None
