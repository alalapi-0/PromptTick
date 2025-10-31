"""Echo adapter used for smoke testing and debugging."""
from __future__ import annotations

from typing import Any

from .base import BaseAdapter


class EchoAdapter(BaseAdapter):
    """A minimal adapter that echoes prompts for end-to-end testing."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)

    def generate(self, prompt_text: str) -> str:
        """Return the input prompt with a fixed prefix for observability."""

        return f"[ECHO PLACEHOLDER]\n\nPROMPT:\n{prompt_text}"
