from app.core.error_codes import AgentErrorCode


class AgentRuntimeError(Exception):
    def __init__(
        self,
        message: str,
        code: AgentErrorCode = AgentErrorCode.INTERNAL_ERROR,
        status_code: int = 400,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
