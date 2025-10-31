"""Utility helpers for JSON Pointer extraction (RFC 6901)."""
from __future__ import annotations

from typing import Any


def _unescape_token(token: str) -> str:
    """Return JSON Pointer token with ``~1``/``~0`` sequences restored."""

    return token.replace("~1", "/").replace("~0", "~")


def json_pointer_get(data: Any, pointer: str) -> Any:
    """Resolve *pointer* against *data* following RFC 6901 semantics.

    Parameters
    ----------
    data:
        Root JSON-like structure (``dict``/``list``/primitive).
    pointer:
        JSON Pointer expression such as ``"/choices/0/message"``. The empty
        string refers to the root object.

    Returns
    -------
    Any
        Extracted value addressed by *pointer*.

    Raises
    ------
    KeyError
        If a map key is missing or if a list index token is invalid.
    IndexError
        If a list index is out of range.
    """

    if pointer == "":
        return data

    if not pointer.startswith("/"):
        raise ValueError(f"JSON Pointer 必须以 '/' 开头：{pointer}")

    current = data
    for raw_token in pointer.lstrip("/").split("/"):
        token = _unescape_token(raw_token)
        if isinstance(current, list):
            if token == "-":
                raise IndexError("JSON Pointer '-' token 不支持读取")
            try:
                index = int(token)
            except ValueError as exc:
                raise KeyError(f"JSON Pointer 索引无效：{token}") from exc
            try:
                current = current[index]
            except IndexError as exc:
                raise IndexError(
                    f"JSON Pointer 索引越界：{token}（长度 {len(current)}）"
                ) from exc
        elif isinstance(current, dict):
            if token not in current:
                raise KeyError(f"JSON Pointer key 不存在：{token}")
            current = current[token]
        else:
            raise KeyError(
                f"无法在类型 {type(current).__name__} 上继续解析 JSON Pointer"
            )

    return current
