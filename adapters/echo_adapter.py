"""
Echo adapter (Round 1 placeholder).

本轮不参与实际调用，仅保留接口形状。
"""
from typing import Any

class EchoAdapter:
    """A minimal placeholder adapter that echoes prompts.

    Parameters
    ----------
    config:
        Adapter-specific configuration mapping. Stored for future use.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def generate(self, prompt_text: str) -> str:
        """
        未来接口：接收 prompt 文本，返回生成文本。
        Round 1 不会被 main.py 调用。
        """
        return f"[ECHO PLACEHOLDER]\\n\\nPROMPT:\\n{prompt_text}"
