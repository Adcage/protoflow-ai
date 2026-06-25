"""测试 vNext 文件操作工具。"""

import tempfile
from pathlib import Path

import pytest

from app.agent_loop_vnext.shared.tools.file_tools import (
    CreateTool,
    InsertTool,
    StrReplaceTool,
    ViewTool,
)
from app.tools.file_tools import FileTools, Workspace


@pytest.fixture
def workspace():
    """创建临时工作区。"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Workspace(tmp)


@pytest.fixture
def file_tools(workspace):
    """创建 FileTools 实例。"""
    return FileTools(workspace)


@pytest.mark.asyncio
async def test_view_dir(file_tools, workspace):
    """view 目录应返回目录列表。"""
    tool = ViewTool(file_tools=file_tools)
    Path(workspace.root, "hello.txt").write_text("hello", encoding="utf-8")
    result = await tool._arun(".")
    assert "hello.txt" in result


@pytest.mark.asyncio
async def test_view_empty_dir(file_tools):
    """空目录应返回"目录为空"。"""
    tool = ViewTool(file_tools=file_tools)
    result = await tool._arun(".")
    assert result == "目录为空"


@pytest.mark.asyncio
async def test_view_file(file_tools, workspace):
    """view 文件应返回文件内容。"""
    Path(workspace.root, "test.txt").write_text("hello world", encoding="utf-8")
    tool = ViewTool(file_tools=file_tools)
    result = await tool._arun("test.txt")
    assert result == "hello world"


@pytest.mark.asyncio
async def test_view_empty_file(file_tools, workspace):
    """空文件应返回"文件内容为空"。"""
    Path(workspace.root, "empty.txt").write_text("", encoding="utf-8")
    tool = ViewTool(file_tools=file_tools)
    result = await tool._arun("empty.txt")
    assert "文件内容为空" in result


@pytest.mark.asyncio
async def test_view_file_with_view_range(file_tools, workspace):
    """view 文件支持 view_range 截取行范围。"""
    Path(workspace.root, "lines.txt").write_text(
        "line1\nline2\nline3\nline4\nline5\n", encoding="utf-8"
    )
    tool = ViewTool(file_tools=file_tools)
    result = await tool._arun("lines.txt", view_range=[2, 4])
    lines = result.strip().split("\n")
    assert lines == ["line2", "line3", "line4"]


@pytest.mark.asyncio
async def test_create_file(file_tools, workspace):
    """create 应创建新文件。"""
    tool = CreateTool(file_tools=file_tools)
    result = await tool._arun("new.txt", "new content")
    assert "写入成功" in result
    content = Path(workspace.root, "new.txt").read_text(encoding="utf-8")
    assert content == "new content"


@pytest.mark.asyncio
async def test_create_file_already_exists(file_tools, workspace):
    """create 已存在文件应报错。"""
    Path(workspace.root, "exist.txt").write_text("existing", encoding="utf-8")
    tool = CreateTool(file_tools=file_tools)
    with pytest.raises(Exception) as exc:
        await tool._arun("exist.txt", "new content")
    assert "文件已存在" in str(exc.value)


@pytest.mark.asyncio
async def test_str_replace(file_tools, workspace):
    """str_replace 应精确替换文本。"""
    Path(workspace.root, "test.txt").write_text("hello world", encoding="utf-8")
    tool = StrReplaceTool(file_tools=file_tools)
    result = await tool._arun("test.txt", "hello", "hi")
    assert "修改成功" in result
    content = Path(workspace.root, "test.txt").read_text(encoding="utf-8")
    assert content == "hi world"


@pytest.mark.asyncio
async def test_str_replace_not_found(file_tools, workspace):
    """str_replace 未找到 old_str 应报错。"""
    Path(workspace.root, "test.txt").write_text("hello world", encoding="utf-8")
    tool = StrReplaceTool(file_tools=file_tools)
    with pytest.raises(Exception) as exc:
        await tool._arun("test.txt", "not_exist", "hi")
    assert "未找到" in str(exc.value)


@pytest.mark.asyncio
async def test_str_replace_empty_old_str(file_tools, workspace):
    """str_replace 的 old_str 为空应报错。"""
    Path(workspace.root, "test.txt").write_text("hello", encoding="utf-8")
    tool = StrReplaceTool(file_tools=file_tools)
    with pytest.raises(Exception) as exc:
        await tool._arun("test.txt", "", "hi")
    assert "不能为空" in str(exc.value)


@pytest.mark.asyncio
async def test_insert(file_tools, workspace):
    """insert 应在指定行后插入文本。"""
    Path(workspace.root, "test.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    tool = InsertTool(file_tools=file_tools)
    result = await tool._arun("test.txt", 1, "inserted_line")
    assert "插入成功" in result
    content = Path(workspace.root, "test.txt").read_text(encoding="utf-8")
    assert "inserted_line" in content
    lines = content.strip().split("\n")
    assert lines[1] == "inserted_line"


@pytest.mark.asyncio
async def test_insert_at_beginning(file_tools, workspace):
    """insert_line=0 表示在文件开头插入。"""
    Path(workspace.root, "test.txt").write_text("line1\nline2\n", encoding="utf-8")
    tool = InsertTool(file_tools=file_tools)
    await tool._arun("test.txt", 0, "header")
    content = Path(workspace.root, "test.txt").read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    assert lines[0] == "header"


@pytest.mark.asyncio
async def test_insert_line_out_of_range(file_tools, workspace):
    """insert_line 超范围应报错。"""
    Path(workspace.root, "test.txt").write_text("line1\nline2\n", encoding="utf-8")
    tool = InsertTool(file_tools=file_tools)
    with pytest.raises(Exception) as exc:
        await tool._arun("test.txt", 999, "new")
    assert "超出" in str(exc.value)
