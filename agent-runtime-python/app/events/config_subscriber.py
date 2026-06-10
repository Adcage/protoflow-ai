import json

import redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.events.config_subscriber")

CHANNEL = "model-config-events"

_local_cache: dict[str, dict] = {}


def get_cache_key(model_config_id: int, config_version: int) -> str:
    return f"{model_config_id}:{config_version}"


def get_cached_config(model_config_id: int, config_version: int) -> dict | None:
    key = get_cache_key(model_config_id, config_version)
    return _local_cache.get(key)


def set_cached_config(model_config_id: int, config_version: int, config: dict) -> None:
    key = get_cache_key(model_config_id, config_version)
    _local_cache[key] = config


def invalidate_config(model_config_id: int) -> None:
    keys_to_remove = [k for k in _local_cache if k.startswith(f"{model_config_id}:")]
    for key in keys_to_remove:
        del _local_cache[key]
    logger.info("清除模型配置缓存: modelConfigId=%d, 清除 %d 条", model_config_id, len(keys_to_remove))


def _handle_message(message: dict) -> None:
    try:
        data = json.loads(message["data"])
        event_type = data.get("eventType")
        if event_type == "MODEL_CONFIG_UPDATED":
            model_config_id = data.get("modelConfigId")
            if model_config_id:
                invalidate_config(model_config_id)
    except Exception:
        logger.exception("处理模型配置事件失败")


# NOTE: This subscriber is currently not enabled (no caller in production).
# Retained for potential future use when Redis pub/sub is deployed.
def start_subscriber(redis_url: str | None = None) -> None:
    url = redis_url or settings.redis_url
    if not url:
        logger.warning("未配置 Redis URL，模型配置事件订阅未启动")
        return

    try:
        client = redis.from_url(url)
        pubsub = client.pubsub()
        pubsub.subscribe(CHANNEL)
        logger.info("模型配置事件订阅已启动: channel=%s", CHANNEL)
        for message in pubsub.listen():
            if message["type"] == "message":
                _handle_message(message)
    except Exception:
        logger.exception("模型配置事件订阅异常")
