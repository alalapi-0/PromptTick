"""Adapter factory used by PromptTick."""
from __future__ import annotations

from typing import Any

from .base import BaseAdapter
from .echo_adapter import EchoAdapter
from .generic_http_adapter import GenericHTTPAdapter
from .openai_adapter import OpenAIAdapter

__all__ = [
    "BaseAdapter",
    "EchoAdapter",
    "GenericHTTPAdapter",
    "OpenAIAdapter",
    "make_adapter",
]


def make_adapter(name: str, config: dict[str, Any]) -> BaseAdapter:
    """Return an adapter instance configured by *name* and *config*.

    Parameters
    ----------
    name:
        Adapter identifier from ``config.yaml``.
    config:
        Global configuration mapping. Adapter-specific sections are extracted
        inside this factory.
    """

    normalized = (name or "").strip().lower()
    if normalized in {"", "echo_adapter"}:
        return EchoAdapter(config)

    if normalized == "generic_http_adapter":
        section = config.get("generic_http", {}) if isinstance(config, dict) else {}
        if not isinstance(section, dict):
            raise ValueError("generic_http 配置必须为字典")
        return GenericHTTPAdapter(section)

    if normalized == "openai_adapter":
        return OpenAIAdapter(config)

    raise ValueError(f"未知适配器：{name}")
