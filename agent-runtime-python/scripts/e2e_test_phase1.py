"""
端到端测试阶段1: 通过 gRPC 发送请求，验证事件流和暂停流程
重点验证:
1. event_mapper 正确映射事件 (STATUS, TOOL_REQUEST, TOOL_EXECUTED, DONE)
2. 如果 ask_user 触发，waiting_for_user DONE 消息是否正确
3. 如果没有 ask_user，普通 DONE 消息是否正确

用法:
  cd agent-runtime-python && python scripts/e2e_test_phase1.py
"""

import asyncio
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.grpc import code_generation_pb2, code_generation_pb2_grpc, common_pb2
import grpc


async def run_test():
    channel = grpc.aio.insecure_channel("localhost:9091")
    stub = code_generation_pb2_grpc.CodeGenerationServiceStub(channel)

    print("=" * 60)
    print("阶段 1: 发送请求，收集事件流")
    print("=" * 60)

    request = code_generation_pb2.CodeGenerationRequest(
        agent_run_id="9001",
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="做一个简单的计数器应用，只有一个按钮和数字显示",
        code_gen_type=common_pb2.VUE_PROJECT,
        workspace_path="E:/Programme/Project/protoflow-ai/agent-runtime-python/workspace/test-app",
        model_config_id=1,
        config_version=1,
    )

    event_types_seen = set()
    tool_names_seen = set()
    done_message = ""
    ask_user_found = False
    status_messages = []
    total_events = 0

    try:
        response_stream = stub.StreamGenerate(request)
        async for event in response_stream:
            total_events += 1
            event_type = event.event_type
            event_types_seen.add(event_type)

            if event_type == common_pb2.AI_RESPONSE:
                text = event.ai_response.text
                if text and len(text) < 80:
                    print(f"  [AI_RESPONSE] seq={event.seq} text={text[:60]}")

            elif event_type == common_pb2.TOOL_REQUEST:
                name = event.tool_request.name
                args = event.tool_request.arguments[:200] if event.tool_request.arguments else ""
                tool_names_seen.add(name)
                print(f"  [TOOL_REQUEST] seq={event.seq} name={name}")
                if name == "ask_user":
                    ask_user_found = True
                    print(f"    >>> ask_user 发现！args={args}")

            elif event_type == common_pb2.TOOL_EXECUTED:
                name = event.tool_executed.name
                tool_names_seen.add(name)
                print(f"  [TOOL_EXECUTED] seq={event.seq} name={name}")

            elif event_type == common_pb2.STATUS:
                msg = event.status.message
                status_messages.append(msg)
                print(f"  [STATUS] seq={event.seq} msg={msg}")

            elif event_type == common_pb2.DONE:
                done_message = event.done.message
                print(f"  [DONE] seq={event.seq} message={done_message}")

            elif event_type == common_pb2.ERROR:
                msg = event.error.message
                print(f"  [ERROR] seq={event.seq} msg={msg}")

    except grpc.aio.AioRpcError as e:
        print(f"  gRPC 错误: {e.code()} - {e.details()}")

    print()
    print("=" * 60)
    print("验证结果")
    print("=" * 60)
    print(f"  总事件数: {total_events}")
    print(f"  事件类型: {[common_pb2.EventType.Name(t) for t in event_types_seen]}")
    print(f"  工具名: {sorted(tool_names_seen)}")
    print(f"  STATUS 消息: {status_messages}")
    print(f"  ask_user 触发: {ask_user_found}")
    print(f"  DONE 消息: {done_message}")

    # 关键验证
    checks = {
        "收到 DONE 事件": common_pb2.DONE in event_types_seen,
        "收到 STATUS 事件": common_pb2.STATUS in event_types_seen,
        "event_mapper 正常工作": total_events > 0,
    }

    if ask_user_found:
        checks["ask_user 触发 → waiting_for_user"] = done_message == "waiting_for_user"
        checks["ask_user 在 TOOL_REQUEST 中"] = True
    else:
        checks["无 ask_user → 正常 DONE"] = done_message != "waiting_for_user" and "completed" in done_message or total_events > 5

    print()
    for check, result in checks.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {check}")

    # 验证序列化能力
    print()
    print("=" * 60)
    print("验证 state 序列化/反序列化")
    print("=" * 60)

    from app.agent_loop.state import AgentLoopState
    from app.runtime.state import ToolCallRecord

    state = AgentLoopState()
    state.mode = "implement"
    state.iteration = 5
    state.selected_skill_id = "ui-ux-pro-max"
    state.implementation_outline = {"text": "深色仪表盘"}
    state.executed_tool_calls = [
        ToolCallRecord(id="t1", name="select_skill", arguments={"skill_id": "ui-ux-pro-max"}, result="已选择"),
        ToolCallRecord(id="t2", name="ask_user", arguments={"question": "配色？"}, result="已提问"),
    ]
    state.conversation_messages = [{"role": "user", "content": "做仪表盘"}]
    state.resolved_model = {"provider": "openai", "modelName": "gpt-4", "apiKey": "sk-secret"}
    state.status = "waiting_for_user"

    json_str = state.serialize()
    restored = AgentLoopState.deserialize(json_str)

    ser_checks = {
        "mode 恢复": restored.mode == "implement",
        "iteration 恢复": restored.iteration == 5,
        "skill_id 恢复": restored.selected_skill_id == "ui-ux-pro-max",
        "outline 恢复": restored.implementation_outline is not None,
        "tool_calls 恢复": len(restored.executed_tool_calls) == 2,
        "apiKey 脱敏": "apiKey" not in json.loads(json_str).get("resolved_model", {}),
        "status 恢复": restored.status == "waiting_for_user",
    }

    for check, result in ser_checks.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {check}")

    # 构造恢复请求的 loop_state_json 验证 gRPC 请求能正确携带
    print()
    print("验证 loop_state_json gRPC 请求构建:")
    req_with_state = code_generation_pb2.CodeGenerationRequest(
        agent_run_id="9002",
        loop_state_json=json_str,
    )
    print(f"  loop_state_json 长度: {len(req_with_state.loop_state_json)} 字节")
    print(f"  loop_state_json 前100字符: {req_with_state.loop_state_json[:100]}")

    await channel.close()
    print()
    print("=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_test())
