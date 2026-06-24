"""Phase 1 Task 1-2 测试：动态工具参数摘要。"""

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Literal

from app.prompts.tool_summary import (
    format_tool_signature,
    format_tool_summary,
)


class _SimpleInput(BaseModel):
    name: str = Field(description="名称")
    value: int = Field(default=0, description="值")


class _EnumInput(BaseModel):
    mode: Literal["plan", "implement", "validate"] = Field(description="模式")
    reason: str = Field(default="", description="原因")


class _NestedInput(BaseModel):
    items: list[str] = Field(default_factory=list, description="项目列表")
    config: dict = Field(default_factory=dict, description="配置")


class _NoInput(BaseModel):
    pass


class _SimpleTool(BaseTool):
    name: str = "simple_tool"
    description: str = "简单工具"
    args_schema: type[BaseModel] = _SimpleInput

    def _run(self, **kwargs):
        return "ok"

    async def _arun(self, **kwargs):
        return "ok"


class _EnumTool(BaseTool):
    name: str = "enum_tool"
    description: str = "枚举工具"
    args_schema: type[BaseModel] = _EnumInput

    def _run(self, **kwargs):
        return "ok"

    async def _arun(self, **kwargs):
        return "ok"


class _NestedTool(BaseTool):
    name: str = "nested_tool"
    description: str = "嵌套工具"
    args_schema: type[BaseModel] = _NestedInput

    def _run(self, **kwargs):
        return "ok"

    async def _arun(self, **kwargs):
        return "ok"


class _NoArgsTool(BaseTool):
    name: str = "no_args_tool"
    description: str = "无参数工具"
    args_schema: type[BaseModel] = _NoInput

    def _run(self, **kwargs):
        return "ok"

    async def _arun(self, **kwargs):
        return "ok"


class TestRequiredAndOptionalFieldsAreDistinguished:
    """混合字段；预期 required 无 ?、optional 有 ?。"""

    def test_required_and_optional_fields_are_distinguished(self):
        sig = format_tool_signature(_SimpleTool())
        assert "name: string" in sig
        assert "value?:" in sig


class TestLiteralValuesRenderAsUnion:
    """Literal；预期枚举值完整。"""

    def test_literal_values_render_as_union(self):
        sig = format_tool_signature(_EnumTool())
        assert "'plan'" in sig or "plan" in sig
        assert "'implement'" in sig or "implement" in sig
        assert "'validate'" in sig or "validate" in sig


class TestDefaultValueIsRendered:
    """默认值；预期稳定输出。"""

    def test_default_value_is_rendered(self):
        sig = format_tool_signature(_EnumTool())
        assert "reason?:" in sig
        assert '""' in sig or "''" in sig


class TestRefAndArraySchemaAreSupported:
    """嵌套 schema；预期不输出 unknown。"""

    def test_ref_and_array_schema_are_supported(self):
        sig = format_tool_signature(_NestedTool())
        assert "list[" in sig or "list" in sig
        assert "dict" in sig
        assert "unknown" not in sig


class TestSummaryUsesOnlyResolvedTools:
    """传入子集；预期没有候选集合中未选工具。"""

    def test_summary_uses_only_resolved_tools(self):
        tools = [_SimpleTool(), _EnumTool()]
        summary = format_tool_summary(tools)
        assert "simple_tool" in summary
        assert "enum_tool" in summary
        assert "nested_tool" not in summary
        assert "no_args_tool" not in summary


class TestNoArgsTool:
    """无参数工具渲染为 name()。"""

    def test_no_args_tool_signature(self):
        sig = format_tool_signature(_NoArgsTool())
        assert sig == "no_args_tool()"


class TestSummaryFormat:
    """验证整体摘要格式。"""

    def test_summary_has_header(self):
        summary = format_tool_summary([_SimpleTool()])
        assert "## 当前模式可用能力" in summary

    def test_summary_empty_tools(self):
        summary = format_tool_summary([])
        assert summary == ""
