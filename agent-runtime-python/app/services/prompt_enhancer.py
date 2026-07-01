import logging
import re

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.core.model_error_sanitizer import summarize_error_for_log, to_safe_agent_error
from app.services.chat_model_factory import ChatModelFactory

logger = logging.getLogger("app.services.prompt_enhancer")

RISK_REJECTION_PATTERNS = [
    re.compile(r"the request was rejected", re.IGNORECASE),
    re.compile(r"considered high risk", re.IGNORECASE),
    re.compile(r"content.*policy", re.IGNORECASE),
    re.compile(r"安全.*拦截", re.IGNORECASE),
    re.compile(r"内容.*违规", re.IGNORECASE),
]

ENHANCE_SYSTEM_PROMPT = """你是一个网页生成提示词增强助手。将用户简短的需求扩展为结构化的网页生成提示词。

规则：
1. 直接输出增强后的提示词，不要加任何前缀说明、引导语或总结。
2. 使用以下结构化格式，每个字段一行，用方括号标记字段名：

[页面类型] 单个短语描述页面类型
[风格] 配色方案、视觉风格关键词
[布局] 页面整体布局结构
[核心模块] 用编号列表描述每个功能模块的具体内容和交互
[交互细节] 按钮行为、表单验证、动效等交互要求
[其他] 补充说明（可选）

3. 核心模块要具体：描述每个模块的位置、内容、样式，而非笼统概括。
4. 如果用户需求较简短，补充合理的配色、布局和交互细节。
5. 如果有图片摘要信息，结合图片信息优化；否则仅基于用户需求增强。
6. 不要照抄图片链接，只保留对页面生成有帮助的摘要。
7. 不要输出 Markdown 格式，不要使用 # 标题。

示例输出：

[页面类型] 登录页
[风格] 白色卡片居中，浅灰背景，品牌蓝主色调，轻微阴影
[布局] 全屏垂直水平居中单卡片布局
[核心模块]
1. 顶部居中公司Logo
2. "欢迎登录"主标题 + "请输入账号信息"副标题
3. 邮箱输入框（标签"邮箱地址"，验证提示"格式错误"）
4. 密码输入框（标签"密码"，验证提示"密码不能为空"）
5. 品牌蓝色主按钮"登录"
6. 右对齐"忘记密码？"链接
7. 分隔线 + "或者使用以下方式登录" + 微信/QQ/GitHub 图标按钮
8. 底部版权信息
[交互细节] 输入框失焦验证，按钮悬停变深，第三方图标悬停放大
[其他] 响应式适配移动端"""


def _is_risk_rejection(text: str) -> bool:
    return any(p.search(text) for p in RISK_REJECTION_PATTERNS)


class PromptEnhancerService:
    def __init__(self, chat_model_factory: ChatModelFactory):
        self.chat_model_factory = chat_model_factory

    async def enhance(self, prompt: str, model_config: dict) -> str:
        if not prompt or not prompt.strip():
            raise AgentRuntimeError("提示词不能为空", code=AgentErrorCode.PROMPT_EMPTY)

        chat_model: BaseChatModel = self.chat_model_factory.create(model_config)

        messages = [
            {"role": "system", "content": ENHANCE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await chat_model.ainvoke(messages)
            content = response.content
            if not content or not content.strip():
                logger.warning("enhance prompt returned empty, returning original")
                return prompt
            if _is_risk_rejection(content):
                logger.warning("enhance prompt rejected by content safety: %s", content[:120])
                raise AgentRuntimeError(
                    "提示词优化被内容安全策略拦截，请修改提示词后重试",
                    code=AgentErrorCode.CONTENT_SAFETY_REJECTED,
                )
            return content.strip()
        except AgentRuntimeError as e:
            raise to_safe_agent_error(e, default_message="提示词优化服务暂时不可用") from e
        except Exception as e:
            logger.error(
                "enhance prompt failed: %s",
                summarize_error_for_log(e, default_message="提示词优化服务暂时不可用"),
            )
            raise to_safe_agent_error(e, default_message="提示词优化服务暂时不可用") from e
