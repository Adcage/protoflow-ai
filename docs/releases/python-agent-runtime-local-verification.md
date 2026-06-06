# Python Agent Runtime Local Verification

## Environment

- Java: 17
- Python:
- Node:

## Commands

- `cd agent-runtime-python && python -m uvicorn app.main:app --reload --port 9000`
- `cd backend-java && AGENT_RUNTIME=python-agent mvn spring-boot:run`
- `cd frontend-vue && npm run dev`

## Result

- Python health:
- Java startup:
- Frontend startup:
- SSE generation:
- Workspace file:
- Chat history:

## Known Gaps

- `modelConfigId` 和 `configVersion` 在 `AppServiceImpl` 构建 `CodeGenerationRequest` 时未填充。`app` 表无此列，`AgentRun` 实体有此字段但 `createAgentRun` 未接受这些参数。待后续从默认模型配置或前端请求参数补充。

## Issues

- None
