"""
端到端测试: 通过 gRPC 直接调用 Python Agent Runtime
1. 发送请求触发 ask_user 暂停
2. 收集事件流，验证 ask_user 事件和 DONE 消息
3. 用 loop_state_json 恢复，验证 state 恢复

用法:
  先启动 Python 服务:
    cd agent-runtime-python && uvicorn app.main:app --reload --port 8000
  
  然后运行测试:
    cd agent-runtime-python && python scripts/e2e_test_ask_user.py
"""

import asyncio
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.grpc import code_generation_pb2, code_generation_pb2_grpc, common_pb2
import grpc


async def run_e2e_test():
    channel = grpc.aio.insecure_channel("localhost:9091")
    stub = code_generation_pb2_grpc.CodeGenerationServiceStub(channel)

    print("=" * 60)
    print("阶段 1: 发送请求，等待 ask_user 或正常完成")
    print("=" * 60)

    request1 = code_generation_pb2.CodeGenerationRequest(
        agent_run_id="9001",
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="帮我做一个简洁的SaaS数据仪表盘，用现代风格，深色主题",
        code_gen_type=common_pb2.VUE_PROJECT,
        workspace_path="E:/Programme/Project/protoflow-ai/agent-runtime-python/workspace/test-app",
        model_config_id=1,
        config_version=1,
    )

    events = []
    loop_state_json = ""
    ask_user_found = False
    done_message = ""

    try:
        response_stream = stub.StreamGenerate(request1)
        async for event in response_stream:
            event_type = event.event_type
            seq = event.seq

            if event_type == common_pb2.AI_RESPONSE:
                text = event.ai_response.text
                if text:
                    print(f"  [AI_RESPONSE] seq={seq} text={text[:100]}...")
                    events.append({"type": "ai_response", "text": text})

            elif event_type == common_pb2.TOOL_REQUEST:
                name = event.tool_request.name
                args = event.tool_request.arguments
                print(f"  [TOOL_REQUEST] seq={seq} name={name} args={args[:200] if args else ''}")
                events.append({"type": "tool_request", "name": name, "args": args})
                if name == "ask_user":
                    ask_user_found = True
                    print(f"  >>> ask_user 触发！工具参数: {args}")

            elif event_type == common_pb2.TOOL_EXECUTED:
                name = event.tool_executed.name
                print(f"  [TOOL_EXECUTED] seq={seq} name={name}")
                events.append({"type": "tool_executed", "name": name})

            elif event_type == common_pb2.STATUS:
                msg = event.status.message
                print(f"  [STATUS] seq={seq} msg={msg}")
                events.append({"type": "status", "message": msg})

            elif event_type == common_pb2.DONE:
                done_message = event.done.message
                print(f"  [DONE] seq={seq} message={done_message}")
                events.append({"type": "done", "message": done_message})

            elif event_type == common_pb2.ERROR:
                msg = event.error.message
                print(f"  [ERROR] seq={seq} msg={msg}")
                events.append({"type": "error", "message": msg})

            else:
                print(f"  [UNKNOWN] seq={seq} type={event_type}")

    except grpc.aio.AioRpcError as e:
        print(f"  gRPC 错误: {e.code()} - {e.details()}")

    print()
    print(f"事件总数: {len(events)}")
    print(f"ask_user 触发: {ask_user_found}")
    print(f"DONE 消息: {done_message}")

    if done_message == "waiting_for_user":
        print(">>> 暂停流程验证通过: DONE 消息为 'waiting_for_user'")
    elif ask_user_found:
        print(">>> ask_user 已触发，但 DONE 消息不是 'waiting_for_user'")
        print(">>> 可能 LLM 在 ask_user 后继续执行了（LLM 行为不确定性）")
    else:
        print(">>> ask_user 未触发，LLM 可能直接完成了任务")
        print(">>> 这是正常的——LLM 不一定会调用 ask_user")

    # 检查 complete_agent_run 是否传了 loop_state_json
    # 这需要查看 Java 日志或数据库，这里无法直接检查
    # 但我们可以验证 orchestrator 逻辑是否正确序列化了 state

    print()
    print("=" * 60)
    print("阶段 2: 测试恢复流程（使用模拟的 loop_state_json）")
    print("=" * 60)

    # 构造一个模拟的 loop_state_json，模拟暂停状态
    from app.agent_loop.state import AgentLoopState
    from app.runtime.state import ToolCallRecord

    mock_state = AgentLoopState()
    mock_state.mode = "implement"
    mock_state.iteration = 5
    mock_state.mode_switches = 1
    mock_state.selected_skill_id = "ui-ux-pro-max"
    mock_state.implementation_outline = {"text": "创建深色主题 SaaS 仪表盘"}
    mock_state.files_touched = ["src/App.vue"]
    mock_state.executed_tool_calls = [
        ToolCallRecord(id="t1", name="select_skill", arguments={"skill_id": "ui-ux-pro-max"}, result="已选择"),
        ToolCallRecord(id="t2", name="ask_user", arguments={"question": "配色？"}, result="已向用户提问"),
    ]
    mock_state.conversation_messages = [
        {"role": "user", "content": "帮我做一个SaaS数据仪表盘"},
        {"role": "assistant", "content": "好的，我需要确认一些细节"},
    ]
    mock_state.resolved_model = {"provider": "openai", "modelName": "gpt-4"}
    mock_state.plan_iterations = 2
    mock_state.status = "waiting_for_user"

    loop_state_json = mock_state.serialize()

    # 验证序列化/反序列化
    restored = AgentLoopState.deserialize(loop_state_json)
    print(f"  序列化 → 反序列化:")
    print(f"    mode: {restored.mode} (预期: implement)")
    print(f"    status: {restored.status} (预期: waiting_for_user)")
    print(f"    iteration: {restored.iteration} (预期: 5)")
    print(f"    selected_skill_id: {restored.selected_skill_id} (预期: ui-ux-pro-max)")
    print(f"    implementation_outline: {restored.implementation_outline is not None} (预期: True)")
    print(f"    executed_tool_calls: {len(restored.executed_tool_calls)} (预期: 2)")
    print(f"    conversation_messages: {len(restored.conversation_messages)} (预期: 2)")

    assert restored.mode == "implement", f"mode 不匹配: {restored.mode}"
    assert restored.selected_skill_id == "ui-ux-pro-max", f"skill_id 不匹配: {restored.selected_skill_id}"
    assert restored.implementation_outline is not None, "outline 丢失"
    assert len(restored.executed_tool_calls) == 2, f"tool_calls 数量不匹配: {len(restored.executed_tool_calls)}"

    print("  >>> 恢复状态验证通过!")

    # 发送恢复请求
    print()
    print("  发送带 loop_state_json 的恢复请求...")

    request2 = code_generation_pb2.CodeGenerationRequest(
        agent_run_id="9002",
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="深色主题",
        code_gen_type=common_pb2.VUE_PROJECT,
        workspace_path="E:/Programme/Project/protoflow-ai/agent-runtime-python/workspace/test-app",
        model_config_id=1,
        config_version=1,
        loop_state_json=loop_state_json,
    )

    resume_events = []
    select_skill_after_resume = False

    try:
        response_stream = stub.StreamGenerate(request2)
        async for event in response_stream:
            event_type = event.event_type
            seq = event.seq

            if event_type == common_pb2.AI_RESPONSE:
                text = event.ai_response.text
                if text:
                    print(f"  [AI_RESPONSE] seq={seq} text={text[:100]}...")
                    resume_events.append({"type": "ai_response", "text": text})

            elif event_type == common_pb2.TOOL_REQUEST:
                name = event.tool_request.name
                args = event.tool_request.arguments
                print(f"  [TOOL_REQUEST] seq={seq} name={name} args={args[:200] if args else ''}")
                resume_events.append({"type": "tool_request", "name": name, "args": args})
                if name == "select_skill":
                    select_skill_after_resume = True
                    print(f"  >>> WARNING: 恢复后 LLM 又调用了 select_skill!")

            elif event_type == common_pb2.TOOL_EXECUTED:
                name = event.tool_executed.name
                print(f"  [TOOL_EXECUTED] seq={seq} name={name}")
                resume_events.append({"type": "tool_executed", "name": name})

            elif event_type == common_pb2.STATUS:
                msg = event.status.message
                print(f"  [STATUS] seq={seq} msg={msg}")
                resume_events.append({"type": "status", "message": msg})

            elif event_type == common_pb2.DONE:
                done_msg = event.done.message
                print(f"  [DONE] seq={seq} message={done_msg}")
                resume_events.append({"type": "done", "message": done_msg})

            elif event_type == common_pb2.ERROR:
                msg = event.error.message
                print(f"  [ERROR] seq={seq} msg={msg}")
                resume_events.append({"type": "error", "message": msg})

    except grpc.aio.AioRpcError as e:
        print(f"  gRPC 错误: {e.code()} - {e.details()}")

    print()
    print(f"恢复事件总数: {len(resume_events)}")
    if select_skill_after_resume:
        print(">>> 恢复后 LLM 重新调用了 select_skill（不符合预期，但取决于 LLM 行为）")
    else:
        print(">>> 恢复后 LLM 未重新调用 select_skill（符合预期）")

    # 检查恢复后是否有 write_file 等实际执行操作
    write_tools = [e for e in resume_events if e["type"] in ("tool_request", "tool_executed") and e.get("name") in ("write_file", "modify_file")]
    if write_tools:
        print(f">>> 恢复后 LLM 直接开始写文件: {len(write_tools)} 次写操作（符合预期——从暂停点继续）")

    print()
    print("=" * 60)
    print("端到端测试完成")
    print("=" * 60)

    await channel.close()


if __name__ == "__main__":
    asyncio.run(run_e2e_test())
