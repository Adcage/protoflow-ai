from langchain_core.messages import SystemMessage

from app.agent_loop.tool_history import compact_tool_records, format_tool_observation_history
from app.runtime.state import ToolCallRecord


def test_write_file_content_is_not_replayed():
    records = [
        ToolCallRecord(
            id="w1",
            name="write_file",
            arguments={"relative_path": "src/App.vue", "content": "x" * 20_000},
            result="文件写入成功",
        )
    ]

    compacted = compact_tool_records(
        records,
        max_total_chars=10_000,
        max_result_chars=2_000,
    )

    assert "content" in compacted[0].arguments
    assert compacted[0].arguments["content_length"] == 20_000
    assert compacted[0].arguments["relative_path"] == "src/App.vue"
    assert compacted[0].arguments["content_truncated"] is True


def test_read_file_result_is_preserved_in_full():
    result = "HEAD" + "x" * 20_000 + "TAIL"
    records = [
        ToolCallRecord(id="r1", name="read_file", arguments={}, result=result)
    ]

    compacted = compact_tool_records(
        records,
        max_total_chars=200_000,
        max_result_chars=200_000,
    )

    assert compacted[0].result == result
    assert len(compacted[0].result) == len(result)


def test_all_records_are_preserved():
    records = [
        ToolCallRecord(
            id=str(index),
            name="run_command",
            arguments={},
            result=str(index) * 2_000,
        )
        for index in range(5)
    ]

    compacted = compact_tool_records(
        records,
        max_total_chars=3_500,
        max_result_chars=2_000,
    )

    assert len(compacted) >= 1
    assert compacted[-1].id == "4"
    assert compacted[0].id != "0"


def test_format_tool_observation_history_is_readonly_system_message():
    records = [
        ToolCallRecord(
            id="w1",
            name="write_file",
            arguments={"relative_path": "src/App.vue", "content": "<template>secret</template>"},
            result="文件写入成功",
        ),
        ToolCallRecord(
            id="r1",
            name="read_file",
            arguments={"relative_path": "src/main.py"},
            result="print('hello')",
        ),
    ]

    message = format_tool_observation_history(
        records,
        max_total_chars=10_000,
        max_result_chars=2_000,
    )

    assert isinstance(message, SystemMessage)
    assert "历史工具操作记录" in message.content
    assert "不是当前待执行调用" in message.content
    assert "--- file_write" in message.content
    assert "[src/App.vue]" in message.content
    assert "(ok)" in message.content
    assert "内容已压缩" in message.content or "<template>" in message.content
    assert "--- file_read" in message.content
    assert "[src/main.py]" in message.content


def test_tool_history_prefers_latest_records_when_over_budget():
    records = [
        ToolCallRecord(
            id=str(index),
            name="run_command",
            arguments={"command": f"cmd-{index}"},
            result=f"result-{index}-" + "x" * 1_500,
        )
        for index in range(5)
    ]

    message = format_tool_observation_history(
        records,
        max_total_chars=3_000,
        max_result_chars=2_000,
    )

    assert message is not None
    assert "result-4-" in message.content
    assert "result-0-" not in message.content
