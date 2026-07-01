"""代码实现 Agent 的提示词构建器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent_loop_vnext.state import SingleImplementState
from app.capabilities.skills.registry import SkillRegistry
from app.runtime.context import ExecutionContext

if TYPE_CHECKING:
    from app.rag.service import RAGService

_SINGLE_FILE_RULES = (
    "项目类型：single_file（单文件模式）\n"
    "技术栈与约束：\n"
    "1. 只能使用 HTML、CSS 和原生 JavaScript，禁止任何外部 CSS 框架、JS 库或字体库。\n"
    "2. 所有 CSS 必须内联在 <head> 的 <style> 标签内，所有 JS 必须放在 </body> 前的 <script> 标签内。\n"
    "3. 只生成一个 index.html 文件，不包含任何外部文件引用。\n"
    "4. 响应式设计：必须使用 Flexbox 或 Grid 布局，适配桌面和移动端。\n"
    "5. 禁止使用渐变色（gradient）和 Emoji。\n"
    "6. 禁止将完整源码输出到回复中。"
)

_MULTI_FILE_RULES = (
    "项目类型：multi-file（多文件模式）\n"
    "技术栈与约束：\n"
    "1. 只能使用 HTML、CSS 和原生 JavaScript，禁止任何外部 CSS 框架、JS 库或字体库。\n"
    "2. 禁止使用任何构建工具或包管理器：不得创建 package.json、vite.config.js、webpack.config.js、tsconfig.json 等配置文件，不得使用 npm、yarn、Vite、Vue、React 等框架或工具。\n"
    "3. 文件分离：必须且只能生成以下三个文件：\n"
    "   - index.html：页面结构，通过 <link> 引用 style.css，通过 <script> 引用 script.js\n"
    "   - style.css：所有样式规则\n"
    "   - script.js：所有交互逻辑；无交互需求时也应写入基础代码或空文件注释\n"
    "4. 响应式设计：必须使用 Flexbox 或 Grid 布局，适配桌面和移动端。\n"
    "5. 禁止使用渐变色（gradient）和 Emoji。\n"
    "6. 禁止将完整源码输出到回复中。"
)

_VUE_PROJECT_RULES = (
    "项目类型：vue_project（Vue 工程模式）\n"
    "技术栈与约束：\n"
    "1. 技术栈固定为 Vue 3 + Vite + Vue Router 4 + JavaScript + 原生 CSS。\n"
    "2. vite.config.js 必须设置 base: './'。\n"
    "3. 路由必须使用 createWebHashHistory()。\n"
    "4. 页面文案和界面内容必须使用中文。\n"
    "5. 禁止使用渐变色（gradient）和 Emoji。\n"
    "6. 只生成运行项目所需的最小文件集，禁止生成 node_modules、dist、README 等冗余内容。\n"
    "7. package.json 仅允许以下核心依赖：vue、vue-router、vite、@vitejs/plugin-vue，不要声明额外依赖。\n"
    "8. package.json 依赖版本必须使用可安装的稳定范围版本（如 ^3.4.0），禁止使用不存在的精确版本号。\n"
    "9. 禁止将完整源码输出到回复中。"
)

_RULES_MAP: dict[str, str] = {
    "single_file": _SINGLE_FILE_RULES,
    "multi-file": _MULTI_FILE_RULES,
    "vue_project": _VUE_PROJECT_RULES,
}


_OUTPUT_FORMAT = (
    "输出格式规范：\n"
    "1. 回复中的 Markdown 必须符合标准语法：ATX 标题（# 标记）后面必须跟一个空格，例如 `## 标题` 而非 `##标题`。\n"
    "2. 列表项前必须有空行与上文分隔，列表符号后必须跟空格，例如 `- 项目` 而非 `-项目`。\n"
    "3. 代码块必须使用三反引号围栏格式，并标注语言标识。\n"
    "4. 禁止将完整源码输出到回复中，代码应通过工具写入文件。"
)


class ImplementorPromptBuilder:
    """代码实现 Agent 的提示词构建器。"""

    def __init__(
        self,
        context: ExecutionContext,
        state: SingleImplementState,
        skill_registry: SkillRegistry | None = None,
        rag_service: RAGService | None = None,
    ) -> None:
        self._context = context
        self._state = state
        self._skill_registry = skill_registry
        self._rag_service = rag_service

    def build_system_prompt(self) -> str:
        """构建系统提示词，由多个段落组合。"""
        parts = [
            self._render_role(),
            self._render_project_rules(),
            self._render_output_format(),
            self._render_skills(),
            self._render_available_docs(),
        ]
        return "\n\n".join(p for p in parts if p)

    def _render_role(self) -> str:
        return (
            "你是一个专业的代码实现助手，负责理解用户需求并生成代码实现。\n"
            "\n"
            "工作方式：\n"
            "- 和用户正常对话交流，理解需求\n"
            "- 需要实现代码时，使用工具创建或修改文件\n"
            "- 需要了解项目现有结构时，使用 Read 工具查看\n"
            "- 需要搜索文件时，使用 Glob 按文件名搜索或 Grep 按内容搜索\n"
            "- 需要执行命令时（如安装依赖、构建项目），使用 Bash 工具\n"
            "- 需要向用户提问以明确需求时，使用 AskUser 工具\n"
            "- Bash 工具每次只能执行一条命令，不支持 &&、||、|、; 等操作符。多条命令请分多次调用\n"
            "- 不需要工具时直接回复，不要主动调用工具"
        )

    def _render_project_rules(self) -> str:
        """根据 code_gen_type 渲染项目规则。"""
        code_gen_type = self._get_effective_code_gen_type()
        return _RULES_MAP.get(
            code_gen_type,
            f"项目类型：{code_gen_type}\n生成代码时请遵循该类型项目的目录结构和文件规范。",
        )

    def _render_output_format(self) -> str:
        """渲染输出格式规范。"""
        return _OUTPUT_FORMAT

    def _render_skills(self) -> str:
        """渲染可用技能摘要和已加载技能的参考文件前缀。"""
        if self._skill_registry is None:
            return ""

        all_skills = self._skill_registry.all()
        if not all_skills:
            return ""

        lines = [
            "## 可用技能",
            "可使用 LoadSkill 工具加载一个或多个技能。每次调用加载一个技能，可多次调用加载不同技能。",
            "加载后可通过 Read 工具使用 skill/{技能ID}/ 路径前缀读取参考文件。",
            "",
        ]

        for skill in all_skills:
            lines.append(f"- **{skill.id}**: {skill.description}")

        # 已加载技能的参考文件前缀
        if self._state.loaded_skills:
            lines.append("")
            lines.append("## 已加载技能参考文件")
            for skill_id, loaded in self._state.loaded_skills.items():
                if loaded.references:
                    lines.append(f"**{skill_id}** 的参考文件（使用 Read 工具读取）：")
                    for ref in loaded.references:
                        lines.append(f"- skill/{skill_id}/{ref}")
                else:
                    lines.append(f"**{skill_id}**: 无参考文件")

        return "\n".join(lines)

    def _render_available_docs(self) -> str:
        """渲染可查的技术文档库目录（RAG）。"""
        if self._rag_service is None or not self._rag_service.enabled:
            return ""

        # 获取 library 列表（同步方式，从缓存读取）
        # 注意：list_libraries 是 async，这里用 get_available_docs_description 作为同步替代
        return self._rag_service.get_available_docs_description()

    def _get_effective_code_gen_type(self) -> str:
        code_gen_type = self._context.code_gen_type
        if code_gen_type is not None:
            return code_gen_type.value if hasattr(code_gen_type, "value") else str(code_gen_type)
        return "unknown"
