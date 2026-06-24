import hashlib
import logging
import os

from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.types import SkillDefinition

logger = logging.getLogger("app.capabilities.skills.selector")


class SkillNotFoundError(KeyError):
    """Phase 3 Plan 阶段使用的明确异常，便于上层做 reject。"""


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_path(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/")


class SkillSelector:
    def select(self, prompt: str, registry: SkillRegistry) -> list[SkillDefinition]:
        all_skills = registry.all()
        return sorted(all_skills, key=lambda s: s.name)


class SkillRegistryProvider:
    """Plan 阶段使用的只读 Skill 解析器，返回 digest 与已扫描的 references。"""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def resolve_skill(self, skill_id: str) -> tuple[SkillDefinition, str, str, tuple[str, ...]]:
        try:
            skill = self._registry.get(skill_id)
        except KeyError as exc:
            raise SkillNotFoundError(skill_id) from exc
        source_path = str(skill.source_path)
        digest = self._digest_for(skill)
        references = tuple(skill.references or ())
        return skill, digest, _normalize_path(source_path), references

    def _digest_for(self, skill: SkillDefinition) -> str:
        try:
            return _sha256_file(str(skill.source_path))
        except OSError as exc:
            logger.warning(
                "SkillRegistryProvider | 无法计算 digest, fallback 空串: skill=%s err=%s",
                skill.id,
                exc,
            )
            return ""


__all__ = ["SkillSelector", "SkillRegistryProvider", "SkillNotFoundError"]

