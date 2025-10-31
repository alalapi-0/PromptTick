"""OpenAI adapter built on top of the official SDK Responses API."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable

from .base import BaseAdapter


@dataclass(slots=True)
class _RetryDecision:
    """Internal helper describing retry behavior for a failed attempt."""

    should_retry: bool
    wait_seconds: float | None
    status_code: int | None


class OpenAIAdapter(BaseAdapter):
    """Adapter that proxies prompt generation to OpenAI's Responses API."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        try:  # Lazy import so environments without the dependency fail gracefully.
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - exercised when dependency missing.
            raise RuntimeError(
                "缺少依赖 openai，请先 `pip install openai>=1.0.0`"
            ) from exc

        self._OpenAI = OpenAI
        self.client = self._OpenAI()

        cfg = config.get("openai", {}) if isinstance(config, dict) else {}
        if not isinstance(cfg, dict):
            cfg = {}

        self.model: str = str(cfg.get("model", "gpt-4.1-mini"))
        self.temperature: float = float(cfg.get("temperature", 0.7))
        self.max_output_tokens: int = int(cfg.get("max_output_tokens", 800))
        self.system_prompt: str | None = cfg.get("system_prompt")

        headers_cfg = cfg.get("extra_headers")
        if isinstance(headers_cfg, dict):
            self.extra_headers: dict[str, str] | None = {
                str(key): str(value) for key, value in headers_cfg.items()
            }
        else:
            self.extra_headers = None

        self.max_attempts: int = int(cfg.get("max_attempts", 3))
        self.base_backoff: float = float(cfg.get("base_backoff", 1.0))

    def generate(self, prompt_text: str) -> str:
        """Generate text using OpenAI; never propagates exceptions to the caller."""

        if not os.getenv("OPENAI_API_KEY"):
            return "ERROR: OPENAI_API_KEY not set in environment."

        preview = prompt_text[:80].replace("\n", " ")
        suffix = "..." if len(prompt_text) > 80 else ""
        logging.info(
            "[OpenAIAdapter] model=%s temp=%s max_out=%s prompt_preview='%s%s' len=%s",
            self.model,
            self.temperature,
            self.max_output_tokens,
            preview,
            suffix,
            len(prompt_text),
        )

        messages: list[dict[str, str]] = []
        if isinstance(self.system_prompt, str) and self.system_prompt.strip():
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt_text})

        try:
            return self._with_retries(messages)
        except Exception as exc:  # pragma: no cover - defensive fallback.
            logging.exception("[OpenAIAdapter] generate fatal error")
            return f"ERROR: OpenAI generate failed: {exc}"

    def _with_retries(self, messages: list[dict[str, str]]) -> str:
        """Issue the Responses API call with retry semantics."""

        attempt = 0
        last_error: Exception | None = None

        while attempt < max(self.max_attempts, 1):
            attempt += 1
            try:
                response = self.client.responses.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                    extra_headers=self.extra_headers,
                )
                return self._extract_text(response)
            except Exception as exc:  # Broad catch: SDK exposes multiple subclasses.
                last_error = exc
                decision = self._evaluate_retry(exc, attempt)
                if not decision.should_retry:
                    break

                wait_seconds = decision.wait_seconds or 0.0
                logging.warning(
                    (
                        "[OpenAIAdapter] attempt %s/%s failed with status=%s: %s; "
                        "retrying in %.2fs"
                    ),
                    attempt,
                    self.max_attempts,
                    decision.status_code,
                    exc,
                    wait_seconds,
                )
                if wait_seconds > 0:
                    time.sleep(wait_seconds)

        return self._format_error(last_error)

    def _evaluate_retry(self, exc: Exception, attempt: int) -> _RetryDecision:
        """Return retry instruction for *exc* based on HTTP status and headers."""

        status_code = self._extract_status_code(exc)
        retry_after = self._extract_retry_after(exc)

        if status_code in {429, 500, 502, 503, 504} and attempt < self.max_attempts:
            if retry_after is not None:
                return _RetryDecision(True, retry_after, status_code)
            backoff = max(self.base_backoff, 0.0) * (2 ** (attempt - 1))
            return _RetryDecision(True, backoff, status_code)

        return _RetryDecision(False, None, status_code)

    @staticmethod
    def _extract_status_code(exc: Exception) -> int | None:
        """Attempt to get HTTP status code from an SDK exception."""

        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            return status

        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status

        # openai.APIStatusError keeps status on .status
        status = getattr(exc, "status", None)
        if isinstance(status, int):
            return status
        return None

    @staticmethod
    def _extract_retry_after(exc: Exception) -> float | None:
        """Parse Retry-After header from exception response if available."""

        response = getattr(exc, "response", None)
        headers: Any = getattr(response, "headers", None)
        if isinstance(headers, dict):
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
        else:
            retry_after = None

        if retry_after is None:
            return None

        try:
            value = float(retry_after)
            if value < 0:
                return None
            return value
        except (TypeError, ValueError):
            pass

        # Retry-After may be an HTTP-date. Attempt to parse it.
        try:
            parsed: datetime = parsedate_to_datetime(str(retry_after))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = (parsed - now).total_seconds()
            return max(delta, 0.0)
        except (TypeError, ValueError, OverflowError):
            return None

    def _format_error(self, exc: Exception | None) -> str:
        """Create a user-friendly error string from *exc*."""

        if exc is None:
            return "ERROR: OpenAI request failed with unknown error."

        status = self._extract_status_code(exc)
        status_info = f" status={status}" if status is not None else ""
        return f"ERROR: OpenAI request failed{status_info}: {exc}"[:1024]

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text content from a Responses API payload."""

        if response is None:
            return "ERROR: Empty response from OpenAI."

        try:
            text = getattr(response, "output_text", None)
            if isinstance(text, str) and text.strip():
                return text

            output = getattr(response, "output", None)
            if isinstance(output, Iterable):
                chunks: list[str] = []
                for item in output:
                    item_type = getattr(item, "type", None)
                    if item_type != "message":
                        continue
                    content = getattr(item, "content", None)
                    if not isinstance(content, Iterable):
                        continue
                    for block in content:
                        block_type = getattr(block, "type", None)
                        if block_type == "output_text":
                            text_piece = getattr(block, "text", None)
                            if isinstance(text_piece, str):
                                chunks.append(text_piece)
                if chunks:
                    return "".join(chunks)
        except Exception:
            logging.debug("[OpenAIAdapter] response parsing fallback", exc_info=True)

        try:
            raw = str(response)
        except Exception:  # pragma: no cover - extremely defensive.
            return "ERROR: OpenAI response parse failed."

        snippet = raw[:800]
        return f"ERROR: Unable to parse OpenAI response. Raw snippet: {snippet}"

