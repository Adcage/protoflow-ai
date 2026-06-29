"""vNext 工具状态描述策略。

根据工具名和参数动态生成第三人称客观描述（如"正在查看 App.vue"、"正在安装依赖"），
供前端状态条展示。每个策略独立，新增工具只需增加策略类。
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("app.agent_loop_vnext.status_strategies")


# ---------------------------------------------------------------------------
# 策略接口
# ---------------------------------------------------------------------------


class ToolStatusStrategy(ABC):
    """工具状态描述策略基类。"""

    @abstractmethod
    def match(self, tool_name: str) -> bool:
        """是否匹配此工具名。"""

    @abstractmethod
    def get_description(self, tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
        """生成第三人称客观描述。"""


# ---------------------------------------------------------------------------
# 文件操作策略
# ---------------------------------------------------------------------------


class FileStrategy(ToolStatusStrategy):
    """Read / Write / Edit / Insert / View / Create / StrReplace 等文件操作。"""

    _FILE_TOOLS = frozenset({
        "Read", "read_file", "view",
        "Write", "write_file", "create",
        "Edit", "str_replace", "Insert", "insert",
        "delete_file",
    })

    # 工具名 → 前缀映射
    _PREFIX: dict[str, str] = {
        "Read": "正在查看",
        "read_file": "正在查看",
        "view": "正在查看",
        "Write": "正在写入",
        "write_file": "正在写入",
        "create": "正在创建",
        "Edit": "正在修改",
        "str_replace": "正在修改",
        "Insert": "正在插入",
        "insert": "正在插入",
        "delete_file": "正在删除",
    }

    # 没有 path 时的兜底描述
    _DEFAULT: dict[str, str] = {
        "Read": "正在查看文件",
        "read_file": "正在查看文件",
        "view": "正在查看文件",
        "Write": "正在写入文件",
        "write_file": "正在写入文件",
        "create": "正在创建文件",
        "Edit": "正在修改文件",
        "str_replace": "正在修改文件",
        "Insert": "正在修改文件",
        "insert": "正在修改文件",
        "delete_file": "正在删除文件",
    }

    def match(self, tool_name: str) -> bool:
        return tool_name in self._FILE_TOOLS

    def get_description(self, tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
        path = self._extract_path(args)
        if path:
            display = path if is_test else os.path.basename(path)
            prefix = self._PREFIX.get(tool_name, "正在操作")
            return f"{prefix} {display}"
        return self._DEFAULT.get(tool_name, "正在操作文件")

    @staticmethod
    def _extract_path(args: dict[str, Any]) -> str:
        for key in ("path", "relative_path", "relativeFilePath", "relative_dir_path", "relativeDirPath"):
            val = args.get(key)
            if val and isinstance(val, str):
                return val
        return ""


# ---------------------------------------------------------------------------
# Bash 命令策略
# ---------------------------------------------------------------------------


class BashStrategy(ToolStatusStrategy):
    """Bash 命令，内部按子命令模式匹配。"""

    # (pattern, description_template)
    # 模板占位符: {pkg}=group(2), {cmd}=group(1), {script}=group(1)
    _COMMAND_ROUTERS: list[tuple[re.Pattern[str], str]] = [
        # install / uninstall
        (re.compile(r"^npm\s+(i|install)\s*$"), "正在安装依赖"),
        (re.compile(r"^npm\s+(i|install)\s+(\S+)"), "正在安装 {pkg}"),
        (re.compile(r"^npm\s+uninstall\s+(\S+)"), "正在移除 {pkg}"),
        (re.compile(r"^npm\s+ci\b"), "正在安装依赖"),
        (re.compile(r"^pip\s+install\s+(\S+)"), "正在安装 {pkg}"),
        (re.compile(r"^pip\s+install\s+-r\s+(\S+)"), "正在安装项目依赖"),
        # build
        (re.compile(r"^npm\s+run\s+build\b"), "正在构建项目"),
        (re.compile(r"^npx\s+.*\bbuild\b"), "正在构建项目"),
        (re.compile(r"^python\s+.*\bbuild\b"), "正在构建项目"),
        # dev server
        (re.compile(r"^npm\s+run\s+dev\b"), "正在启动开发服务器"),
        (re.compile(r"^npm\s+start\b"), "正在启动服务"),
        # test
        (re.compile(r"^npm\s+(t|test|run\s+test)\b"), "正在运行测试"),
        (re.compile(r"^pytest\b"), "正在运行测试"),
        (re.compile(r"^python\s+-m\s+pytest\b"), "正在运行测试"),
        # lint / format
        (re.compile(r"^npm\s+run\s+lint\b"), "正在检查代码格式"),
        (re.compile(r"^npm\s+run\s+format\b"), "正在格式化代码"),
        (re.compile(r"^ruff\b"), "正在检查代码格式"),
        # git
        (re.compile(r"^git\s+(commit|push)\b"), "正在提交代码"),
        (re.compile(r"^git\s+(pull|fetch)\b"), "正在同步代码"),
        (re.compile(r"^git\s+(checkout|switch)\b"), "正在切换分支"),
        (re.compile(r"^git\s+(reset|restore|revert)\b"), "正在撤销更改"),
        (re.compile(r"^git\s+(status|diff|log|show)\b"), "正在查看 Git 状态"),
        (re.compile(r"^git\s+add\b"), "正在暂存文件"),
        # npx run
        (re.compile(r"^npx\s+(\S+)"), "正在运行 {cmd}"),
        # python / node script
        (re.compile(r"^python\s+(\S+\.py)\b"), "正在运行 {script}"),
        (re.compile(r"^node\s+(\S+\.(?:js|ts|mjs))\b"), "正在运行 {script}"),
        # npm run other
        (re.compile(r"^npm\s+run\s+(\S+)"), "正在执行 {script}"),
        # cache
        (re.compile(r"^npm\s+cache\b"), "正在清理缓存"),
        # default
    ]

    def match(self, tool_name: str) -> bool:
        return tool_name == "Bash"

    def get_description(self, tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
        command = args.get("command", "")
        if not command:
            return "正在执行命令"
        # 测试模式：直接显示命令摘要
        if is_test:
            preview = command if len(command) < 100 else command[:97] + "..."
            return f"正在执行 {preview}"

        for pattern, template in self._COMMAND_ROUTERS:
            match = pattern.search(command.strip())
            if match:
                return self._format_template(template, match)
        return "正在执行命令"

    @staticmethod
    def _format_template(template: str, match: re.Match[str]) -> str:
        if "{pkg}" in template:
            # 需要 group(2)，否则 fallback 到 group(1)
            pkg = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(1)
            return template.replace("{pkg}", pkg)
        if "{cmd}" in template:
            return template.replace("{cmd}", match.group(1))
        if "{script}" in template:
            return template.replace("{script}", os.path.basename(match.group(1)))
        return template


# ---------------------------------------------------------------------------
# 搜索策略
# ---------------------------------------------------------------------------


class SearchStrategy(ToolStatusStrategy):
    """Glob / Grep 文件搜索。"""

    _SEARCH_TOOLS = frozenset({"Glob", "Grep"})

    def match(self, tool_name: str) -> bool:
        return tool_name in self._SEARCH_TOOLS

    def get_description(self, tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
        if tool_name == "Glob":
            pattern = args.get("pattern", "")
            if pattern:
                return f"正在搜索 {pattern}"
            return "正在搜索文件"
        # Grep
        pattern = args.get("pattern", "")
        if pattern:
            preview = pattern if len(pattern) < 30 else pattern[:27] + "..."
            return f"正在搜索代码 {preview}"
        return "正在搜索代码"


# ---------------------------------------------------------------------------
# Skill 策略
# ---------------------------------------------------------------------------


class SkillStrategy(ToolStatusStrategy):
    """LoadSkill 技能加载。"""

    def match(self, tool_name: str) -> bool:
        return tool_name == "LoadSkill"

    def get_description(self, tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
        skill_id = args.get("skill_id", "")
        if is_test and skill_id:
            return f"正在加载设计方案 {skill_id}"
        return "正在加载设计方案"


# ---------------------------------------------------------------------------
# 只读命令策略
# ---------------------------------------------------------------------------


class ReadonlyCommandStrategy(ToolStatusStrategy):
    """Bash 中常见的只读/查看命令。仅 Bash 内部使用，不独立匹配。"""

    _READONLY_COMMANDS = frozenset({
        "cat", "ls", "echo", "head", "tail",
        "pwd", "type", "wc", "find", "dir",
    })

    def match(self, tool_name: str) -> bool:
        return tool_name == "Bash" and self._check_command(
            # 由外部传入 args 决定
        )

    def _check_command(self, command: str) -> bool:
        if not command:
            return False
        tokens = command.strip().split()
        return tokens[0] in self._READONLY_COMMANDS if tokens else False

    def get_description(self, tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
        return "正在查看文件内容"


# ---------------------------------------------------------------------------
# AskUser 策略
# ---------------------------------------------------------------------------


class AskUserStrategy(ToolStatusStrategy):
    """AskUser 提问策略。"""

    def match(self, tool_name: str) -> bool:
        return tool_name == "AskUser"

    def get_description(self, tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
        return "正在向用户提问"


# ---------------------------------------------------------------------------
# 注册中心
# ---------------------------------------------------------------------------

_registry: list[ToolStatusStrategy] = [
    FileStrategy(),
    SearchStrategy(),
    SkillStrategy(),
    AskUserStrategy(),
    BashStrategy(),
]


def get_tool_status_description(tool_name: str, args: dict[str, Any], is_test: bool = False) -> str:
    """根据工具名和参数生成状态描述。

    Args:
        tool_name: 工具名（如 "Read"、"Bash"）
        args: 工具参数字典
        is_test: 测试模式下显示更详细的信息

    Returns:
        第三人称客观描述，如"正在查看 App.vue"。
        没有匹配的策略时返回空字符串。
    """
    try:
        dict_args = dict(args) if args else {}
    except (TypeError, ValueError):
        dict_args = {}

    for strategy in _registry:
        if strategy.match(tool_name):
            try:
                return strategy.get_description(tool_name, dict_args, is_test=is_test)
            except Exception:
                logger.warning("strategy %s failed for tool %s", type(strategy).__name__, tool_name, exc_info=True)
                return ""

    logger.debug("no strategy matched for tool: %s", tool_name)
    return ""
