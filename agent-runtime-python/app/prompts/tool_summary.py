"""动态工具参数摘要：从 BaseTool.args_schema.model_json_schema() 自动生成。

业务 Prompt 不手写工具调用签名，由本模块统一从 Pydantic schema 生成紧凑签名。
"""

from typing import Any

from langchain_core.tools import BaseTool


def format_schema_type(schema: dict[str, Any], root_schema: dict[str, Any]) -> str:
    """从 JSON Schema 片段渲染紧凑类型描述。"""
    if "const" in schema:
        return repr(schema["const"])

    if "enum" in schema:
        return " | ".join(repr(v) for v in schema["enum"])

    if "$ref" in schema:
        ref_path = schema["$ref"]
        ref_name = ref_path.rsplit("/", 1)[-1]
        defs = root_schema.get("$defs", root_schema.get("definitions", {}))
        if ref_name in defs:
            return format_schema_type(defs[ref_name], root_schema)
        return ref_name

    if "anyOf" in schema:
        parts = []
        for sub in schema["anyOf"]:
            if sub.get("type") == "null":
                continue
            parts.append(format_schema_type(sub, root_schema))
        return " | ".join(parts) if parts else "any"

    if "oneOf" in schema:
        parts = [format_schema_type(sub, root_schema) for sub in schema["oneOf"]]
        return " | ".join(parts)

    schema_type = schema.get("type", "any")

    if schema_type == "array":
        items = schema.get("items", {})
        if items:
            item_type = format_schema_type(items, root_schema)
            return f"list[{item_type}]"
        return "list"

    if schema_type == "object":
        return "dict"

    type_map = {
        "string": "string",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
    }
    return type_map.get(schema_type, schema_type)


def format_tool_signature(tool: BaseTool) -> str:
    """渲染单个工具的紧凑参数签名。

    示例: decide_route(mode: plan | implement | validate | finish, code_gen_type?: string = "", reason?: string = "")
    """
    if tool.args_schema is None:
        return f"{tool.name}()"

    schema = tool.args_schema.model_json_schema()
    root_schema = schema
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    defs = schema.get("$defs", schema.get("definitions", {}))
    if defs:
        root_schema = {**schema, "$defs": defs}

    params: list[str] = []
    for field_name, field_schema in properties.items():
        type_str = format_schema_type(field_schema, root_schema)
        is_required = field_name in required_fields
        default_value = field_schema.get("default")

        if is_required:
            param = f"{field_name}: {type_str}"
        else:
            if default_value is not None:
                default_repr = repr(default_value)
                param = f"{field_name}?: {type_str} = {default_repr}"
            else:
                param = f"{field_name}?: {type_str}"

        params.append(param)

    return f"{tool.name}({', '.join(params)})"


def format_tool_summary(tools: list[BaseTool] | tuple[BaseTool, ...]) -> str:
    """渲染当前模式可用能力的动态摘要。

    输出格式固定为：
    ## 当前模式可用能力

    - `tool_name(param: type, ...)`: 工具描述
    """
    if not tools:
        return ""

    lines = ["## 当前模式可用能力", ""]
    for tool in tools:
        sig = format_tool_signature(tool)
        desc = tool.description.split("\n")[0] if tool.description else ""
        lines.append(f"- `{sig}`：{desc}")

    return "\n".join(lines)
