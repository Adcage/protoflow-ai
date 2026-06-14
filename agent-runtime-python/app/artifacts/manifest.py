import logging
from app.artifacts.types import ArtifactManifest

logger = logging.getLogger("app.artifacts.manifest")


class ArtifactCollector:
    def __init__(self) -> None:
        self._artifacts: list[ArtifactManifest] = []

    def add(self, artifact: ArtifactManifest) -> None:
        self._artifacts.append(artifact)

    def artifacts(self) -> list[ArtifactManifest]:
        return list(self._artifacts)
