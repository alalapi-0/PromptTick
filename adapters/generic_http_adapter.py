"""Generic HTTP adapter capable of calling arbitrary REST endpoints."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, Iterable

from .base import BaseAdapter
from utils.jsonptr import json_pointer_get

try:  # pragma: no cover - import guard handled at runtime
    import httpx
except ImportError:  # pragma: no cover - handled by adapter instantiation
    httpx = None  # type: ignore[assignment]

_ENV_PATTERN = re.compile(r"\$\{ENV:([A-Z0-9_]+)\}")
_PROMPT_PLACEHOLDER = "${PROMPT}"
_SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "x-api-token",
    "x-auth-token",
}


def _expand_env_placeholders(text: str) -> str:
    """Replace ``${ENV:VAR}`` placeholders in *text* with environment values."""

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        value = os.getenv(var_name)
        if value is None:
            raise RuntimeError(f"环境变量未设置：{var_name}")
        return value

    return _ENV_PATTERN.sub(replacer, text)


def _mask_headers_for_log(headers: Dict[str, str]) -> Dict[str, str]:
    """Return a copy of *headers* with sensitive values obscured for logging."""

    masked: Dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in _SENSITIVE_HEADERS:
            if not value:
                masked[key] = value
            else:
                parts = value.split(" ", 1)
                if len(parts) == 2:
                    masked[key] = f"{parts[0]} ***"
                else:
                    masked[key] = "***"
        else:
            masked[key] = value
    return masked


def _resolve_content_type(headers: Dict[str, str]) -> str | None:
    for key, value in headers.items():
        if key.lower() == "content-type":
            return value
    return None


def _json_or_text_payload(body: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Prepare keyword arguments for httpx.request based on headers."""

    if not body:
        return {}

    content_type = _resolve_content_type(headers)
    if content_type and content_type.split(";", 1)[0].strip().lower() == "application/json":
        try:
            return {"json": json.loads(body)}
        except json.JSONDecodeError as exc:
            raise ValueError(f"请求体 JSON 解析失败：{exc}") from exc
    return {"content": body}


def _extract_with_pointer(obj: Any, pointer: str) -> str:
    """Extract data using JSON Pointer and coerce to string."""

    target = json_pointer_get(obj, pointer) if pointer else obj
    if isinstance(target, str):
        return target
    return json.dumps(target, ensure_ascii=False)


class GenericHTTPAdapter(BaseAdapter):
    """Adapter that performs HTTP calls according to configuration."""

    def __init__(self, config: dict[str, Any] | None = None):
        if httpx is None:
            raise RuntimeError("缺少依赖 httpx，请先 pip install httpx")
        super().__init__(config)

    def _prepare_headers(self) -> Dict[str, str]:
        raw_headers = self.config.get("headers", {})
        if not isinstance(raw_headers, dict):
            raise ValueError("generic_http.headers 必须是字典")
        headers: Dict[str, str] = {}
        for key, value in raw_headers.items():
            if value is None:
                continue
            expanded = _expand_env_placeholders(str(value))
            headers[str(key)] = expanded
        return headers

    def _prepare_body(self, prompt_text: str) -> str:
        template = str(self.config.get("body_template", ""))
        if not template:
            return ""
        expanded = _expand_env_placeholders(template)
        return expanded.replace(_PROMPT_PLACEHOLDER, prompt_text)

    def _timeout_value(self) -> float:
        raw = self.config.get("timeout", 60)
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("generic_http.timeout 必须为数字") from exc

    def _retry_settings(self) -> tuple[int, float, set[int]]:
        retries = self.config.get("retries", {})
        if not isinstance(retries, dict):
            retries = {}
        raw_attempts = retries.get("max_attempts", 1)
        try:
            max_attempts = max(int(raw_attempts), 1)
        except (TypeError, ValueError) as exc:
            raise ValueError("retries.max_attempts 必须为整数") from exc
        raw_backoff = retries.get("backoff_seconds", 1.0)
        try:
            backoff = max(float(raw_backoff), 0.0)
        except (TypeError, ValueError) as exc:
            raise ValueError("retries.backoff_seconds 必须为数字") from exc
        retry_statuses: set[int] = set()
        raw_statuses: Iterable[Any] = retries.get("retry_on_status", []) or []
        for status in raw_statuses:
            try:
                retry_statuses.add(int(status))
            except (TypeError, ValueError):  # pragma: no cover - defensive casting
                logging.warning("忽略无法解析的重试状态码：%s", status)
        return max_attempts, backoff, retry_statuses

    def generate(self, prompt_text: str) -> str:  # noqa: D401 - inherited docs
        try:
            return self._generate_impl(prompt_text)
        except Exception as exc:  # pragma: no cover - defensive top-level guard
            logging.exception("Generic HTTP 适配器执行失败：%s", exc)
            return f"[Generic HTTP Adapter Error] {exc}"

    def _generate_impl(self, prompt_text: str) -> str:
        url = str(self.config.get("url", "")).strip()
        if not url:
            return "[Generic HTTP Adapter Error] 未配置 generic_http.url"

        method = str(self.config.get("method", "POST")).upper() or "POST"
        timeout = self._timeout_value()
        headers = self._prepare_headers()
        body = self._prepare_body(prompt_text)
        pointer = str(self.config.get("response_json_pointer", ""))
        max_attempts, backoff_seconds, retry_on_status = self._retry_settings()

        logging.info(
            "HTTP 请求: %s %s (timeout=%ss)",
            method,
            url,
            timeout,
        )
        logging.info("HTTP 请求头: %s", _mask_headers_for_log(headers))
        if body:
            logging.debug("HTTP 请求体长度: %s 字符", len(body))

        try:
            base_payload = _json_or_text_payload(body, headers)
        except ValueError as exc:
            return f"[Generic HTTP Adapter Error] {exc}"

        attempt = 0
        delay = backoff_seconds
        last_error: str | None = None
        while attempt < max_attempts:
            attempt += 1
            payload = dict(base_payload)
            try:
                response = httpx.request(  # type: ignore[arg-type]
                    method,
                    url,
                    headers=headers,
                    timeout=timeout,
                    **payload,
                )
            except httpx.RequestError as exc:  # type: ignore[union-attr]
                last_error = f"网络请求失败：{exc}"
                logging.warning(
                    "HTTP 请求异常（第 %s/%s 次）：%s", attempt, max_attempts, exc
                )
            else:
                status = response.status_code
                if 200 <= status < 300:
                    try:
                        data = response.json()
                    except json.JSONDecodeError as exc:
                        snippet = response.text[:512]
                        return (
                            "[Generic HTTP Adapter Error] 响应 JSON 解析失败："
                            f"{exc} | 响应片段: {snippet}"
                        )
                    try:
                        extracted = _extract_with_pointer(data, pointer)
                    except (KeyError, IndexError, ValueError) as exc:
                        preview = json.dumps(data, ensure_ascii=False)
                        truncated = preview[:512]
                        return (
                            "[Generic HTTP Adapter Error] JSON Pointer 解析失败："
                            f"{exc} | 响应片段: {truncated}"
                        )
                    return extracted

                snippet = response.text[:512]
                message = f"HTTP {status} | 响应片段: {snippet}"
                if status in retry_on_status and attempt < max_attempts:
                    logging.warning(
                        "HTTP 响应状态 %s，准备重试（第 %s/%s 次）",
                        status,
                        attempt,
                        max_attempts,
                    )
                    last_error = message
                else:
                    return f"[Generic HTTP Adapter Error] {message}"

            if attempt < max_attempts:
                if delay > 0:
                    logging.info("等待 %.2f 秒后重试", delay)
                    time.sleep(delay)
                delay = delay * 2 if delay > 0 else 0

        return last_error or "[Generic HTTP Adapter Error] HTTP 请求失败"
