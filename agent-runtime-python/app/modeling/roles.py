from enum import Enum


class ModelRole(str, Enum):
    LIGHT = "light"
    PRIMARY = "primary"
    CRITIC = "critic"
    REPAIR = "repair"
    EMBEDDING = "embedding"
