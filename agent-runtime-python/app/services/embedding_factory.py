"""Embedding 模型工厂 — 创建 OpenAIEmbeddings 实例。"""

from __future__ import annotations

import logging

from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class EmbeddingModelFactory:
    """Embedding 模型工厂，复用 ChatModelFactory 的配置模式。

    从 RuntimeModelBundle 的 EMBEDDING 角色配置创建 OpenAIEmbeddings 实例。
    """

    def create(self, config: dict) -> OpenAIEmbeddings:
        """创建 Embedding 模型实例。

        Args:
            config: 模型配置字典，需包含 provider/modelName/apiKey/baseUrl

        Returns:
            OpenAIEmbeddings 实例

        Raises:
            ValueError: 配置缺失或不支持
        """
        provider = config.get("provider", "")
        model_name = config.get("modelName", "")
        api_key = config.get("apiKey", "")
        base_url = config.get("baseUrl", "")

        if not model_name:
            raise ValueError("Embedding 模型名称不能为空")
        if not api_key:
            raise ValueError("Embedding 模型 API Key 不能为空")
        if provider not in {"openai", "openai-compatible"}:
            raise ValueError(f"不支持的 Embedding 提供商: {provider}")

        kwargs: dict = {
            "model": model_name,
            "api_key": api_key,
            # 阿里百炼等国产平台需要显式传递 Authorization header
            # 新版本 openai SDK 的 auth 格式与 dashscope 不兼容
            "default_headers": {
                "Authorization": f"Bearer {api_key}",
            },
            # 跳过 tiktoken tokenization，直接发原始文本
            # 阿里百炼不支持 token ID 数组作为 input
            "check_embedding_ctx_length": False,
        }
        if base_url:
            kwargs["base_url"] = base_url

        logger.info("创建 Embedding 模型: provider=%s, model=%s", provider, model_name)
        return OpenAIEmbeddings(**kwargs)
