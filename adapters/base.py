"""Adapter base classes and interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """Unified interface for generation adapters."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    def generate(self, prompt_text: str) -> str:
        """Given prompt text, return generated text or a readable error string."""
        raise NotImplementedError
