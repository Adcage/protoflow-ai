import logging
import re

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.core.model_error_sanitizer import summarize_error_for_log, to_safe_agent_error
from app.services.chat_model_factory import ChatModelFactory

logger = logging.getLogger("app.services.title_generator")

APP_TITLE_SYSTEM_PROMPT = """你是一个中文产品命名助手。

请根据用户需求生成一个简短、明确、像真实产品名的中文应用标题。

要求：
1. 输出 2 到 12 个字，必要时可包含简短英文缩写。
2. 不要解释，不要加引号，不要加“标题：”前缀。
3. 避免空泛词，比如“智能助手”“应用系统”单独成名。
4. 优先突出业务对象或核心场景。"""

SESSION_TITLE_SYSTEM_PROMPT = """你是一个中文会话摘要助手。

请根据应用上下文和用户本轮首条消息，生成一个简短会话标题。

要求：
1. 输出 4 到 18 个字。
2. 像任务摘要，不要解释，不要加引号，不要加“标题：”前缀。
3. 优先概括当前会话最核心的页面、功能或问题。"""

TITLE_PREFIX_PATTERN = re.compile(r"^(标题|应用名|应用标题|会话名|会话标题)\s*[:：-]\s*")


def normalize_title(raw_title: str, max_length: int) -> str:
    if not raw_title or not raw_title.strip():
        return ""
    title = ""
    for line in raw_title.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = TITLE_PREFIX_PATTERN.sub("", stripped)
        stripped = re.sub(r"^[\-\*#\s]+", "", stripped).strip()
        if stripped:
            title = stripped
            break
    title = title.strip("\"'`“”‘’[]【】")
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"[：:。；;，,]+$", "", title).strip()
    if max_length > 0 and len(title) > max_length:
        title = title[:max_length].strip()
    return title


class TitleGeneratorService:
    def __init__(self, chat_model_factory: ChatModelFactory):
        self.chat_model_factory = chat_model_factory

    async def generate_app_title(self, init_prompt: str, model_config: dict) -> str:
        if not init_prompt or not init_prompt.strip():
            raise AgentRuntimeError("初始化提示词不能为空", code=AgentErrorCode.PROMPT_EMPTY)
        return await self._generate_title(
            system_prompt=APP_TITLE_SYSTEM_PROMPT,
            user_prompt=f"请为下面这个应用需求生成一个应用名：\n\n{init_prompt}",
            model_config=model_config,
            max_length=12,
        )

    async def generate_session_title(
        self,
        app_name: str,
        app_init_prompt: str,
        first_user_message: str,
        model_config: dict,
    ) -> str:
        if not first_user_message or not first_user_message.strip():
            raise AgentRuntimeError("会话消息不能为空", code=AgentErrorCode.PROMPT_EMPTY)
        context_parts = []
        if app_name and app_name.strip():
            context_parts.append(f"应用名：{app_name.strip()}")
        if app_init_prompt and app_init_prompt.strip():
            context_parts.append(f"应用定位：{app_init_prompt.strip()}")
        context_parts.append(f"首条用户消息：{first_user_message.strip()}")
        return await self._generate_title(
            system_prompt=SESSION_TITLE_SYSTEM_PROMPT,
            user_prompt="\n".join(context_parts),
            model_config=model_config,
            max_length=18,
        )

    async def _generate_title(self, system_prompt: str, user_prompt: str, model_config: dict, max_length: int) -> str:
        chat_model: BaseChatModel = self.chat_model_factory.create(model_config)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = await chat_model.ainvoke(messages)
            content = response.content if response else ""
            title = normalize_title(content, max_length)
            if not title:
                raise AgentRuntimeError("标题生成结果为空", code=AgentErrorCode.MODEL_RESPONSE_EMPTY)
            return title
        except AgentRuntimeError as e:
            raise to_safe_agent_error(e, default_message="轻量标题生成服务暂时不可用") from e
        except Exception as e:
            logger.error(
                "title generation failed: %s",
                summarize_error_for_log(e, default_message="轻量标题生成服务暂时不可用"),
            )
            raise to_safe_agent_error(e, default_message="轻量标题生成服务暂时不可用") from e
