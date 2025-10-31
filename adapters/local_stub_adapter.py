"""Local stub adapter bridging prompts to local command-line programs."""
from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict

from .base import BaseAdapter

_LOGGER = logging.getLogger(__name__)


class LocalStubAdapter(BaseAdapter):
    """Adapter that delegates prompt handling to a local command-line process."""

    def __init__(self, config: dict | None = None):
        """Initialize adapter with local execution settings."""
        super().__init__(config)
        local_cfg = (config or {}).get("local", {}) or {}
        self.engine = str(local_cfg.get("engine", "cmd"))
        self.model = str(local_cfg.get("model", ""))
        self.timeout = int(local_cfg.get("timeout_seconds", 120))
        self.workdir = str(local_cfg.get("workdir", ""))
        self.env_map = local_cfg.get("env", {}) or {}
        self.command_template = str(local_cfg.get("command_template", ""))
        self.args = local_cfg.get("args", []) or []
        self.output_mode = str(local_cfg.get("output_mode", "stdout")).lower()
        self.out_suffix = str(local_cfg.get("out_suffix", ".out.txt"))

    def generate(self, prompt_text: str) -> str:
        """Write prompt to temp file, execute command template, return response text."""
        if not self.command_template:
            return "ERROR: local.command_template is not configured."

        info_prefix = (
            "[LocalStubAdapter]"
            f" engine={self.engine} model='{self.model}'"
            f" timeout={self.timeout}s workdir='{self.workdir or os.getcwd()}'"
        )
        template_preview = self.command_template[:120].replace("\n", " ")
        _LOGGER.info("%s template=%s", info_prefix, template_preview)

        try:
            with tempfile.TemporaryDirectory(prefix="promptick_local_") as temp_dir:
                tmpdir = Path(temp_dir)
                prompt_path = tmpdir / "input.prompt.txt"
                prompt_path.write_text(prompt_text, encoding="utf-8")

                out_path = tmpdir / f"output{self.out_suffix}"

                mapping = {
                    "PROMPT_PATH": str(prompt_path),
                    "MODEL": self.model,
                    "ARGS": self._join_args(self.args),
                    "OUT_PATH": str(out_path),
                }
                command = self._render_command(self.command_template, mapping)
                if "${ARGS}" not in self.command_template and self.args:
                    joined_args = self._join_args(self.args)
                    if joined_args:
                        command = f"{command} {joined_args}"
                masked_command = self._mask_for_log(command)
                _LOGGER.debug("[LocalStubAdapter] command(masked)=%s", masked_command)

                env = os.environ.copy()
                for key, value in self.env_map.items():
                    env[key] = self._expand_env_placeholders(str(value))

                cwd = Path(self.workdir).expanduser() if self.workdir else None
                if cwd and not cwd.exists():
                    _LOGGER.warning(
                        "[LocalStubAdapter] workdir does not exist, falling back to current process dir: %s",
                        cwd,
                    )
                    cwd = None

                start_time = time.time()
                try:
                    completed = subprocess.run(
                        command,
                        shell=True,
                        cwd=str(cwd) if cwd else None,
                        env=env,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=self.timeout,
                    )
                except subprocess.TimeoutExpired:
                    _LOGGER.error("[LocalStubAdapter] process timeout after %ss", self.timeout)
                    return f"ERROR: local process timeout after {self.timeout}s."
                except Exception as exc:  # pragma: no cover - defensive
                    _LOGGER.exception("[LocalStubAdapter] failed to launch process")
                    return f"ERROR: failed to launch local process: {exc}"

                elapsed = time.time() - start_time
                _LOGGER.info(
                    "[LocalStubAdapter] exit=%s elapsed=%.2fs stdout_len=%s stderr_len=%s",
                    completed.returncode,
                    elapsed,
                    len(completed.stdout),
                    len(completed.stderr),
                )

                if completed.returncode != 0:
                    stderr_excerpt = completed.stderr.strip()[:800]
                    return (
                        "ERROR: local process exit "
                        f"{completed.returncode}. stderr: {stderr_excerpt}"
                    )

                if self.output_mode == "file":
                    if not out_path.exists():
                        _LOGGER.error("[LocalStubAdapter] expected output file missing: %s", out_path)
                        return "ERROR: expected output file not found (OUT_PATH)."
                    try:
                        result_text = out_path.read_text(encoding="utf-8")
                    except Exception as exc:  # pragma: no cover - defensive
                        _LOGGER.exception("[LocalStubAdapter] failed reading output file")
                        return f"ERROR: failed to read OUT_PATH: {exc}"
                else:
                    result_text = completed.stdout
                    if not result_text.strip():
                        stderr_text = completed.stderr.strip()
                        if stderr_text:
                            return f"ERROR: stdout empty. stderr: {stderr_text[:800]}"
                        return "ERROR: stdout empty."

                _LOGGER.debug(
                    "[LocalStubAdapter] result lengths stdout=%s file=%s",
                    len(completed.stdout),
                    out_path.stat().st_size if out_path.exists() else 0,
                )
                return result_text
        except Exception as exc:  # pragma: no cover - defensive
            _LOGGER.exception("[LocalStubAdapter] fatal error")
            return f"ERROR: LocalStubAdapter failed: {exc}"

    # ------------------------------------------------------------------
    def _expand_env_placeholders(self, value: str) -> str:
        """Replace ${ENV:VAR} placeholders with environment variable values."""
        pattern = re.compile(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}")
        result = value
        for match in pattern.finditer(value):
            env_key = match.group(1)
            env_value = os.environ.get(env_key, "")
            result = result.replace(match.group(0), env_value)
        return result

    def _render_command(self, template: str, mapping: Dict[str, str]) -> str:
        """Render command template by replacing ${KEY} placeholders."""
        rendered = template
        for key, val in mapping.items():
            rendered = rendered.replace(f"${{{key}}}", val)
        return rendered

    def _join_args(self, args: list[str]) -> str:
        """Join argument list into a safely quoted string for shell execution."""
        if not args:
            return ""

        quoted: list[str] = []
        if os.name == "nt":
            for item in args:
                item_str = str(item)
                if any(ch.isspace() for ch in item_str):
                    quoted.append(f'"{item_str}"')
                else:
                    quoted.append(item_str)
        else:
            quoted = [shlex.quote(str(item)) for item in args]
        return " ".join(quoted)

    def _mask_for_log(self, command: str) -> str:
        """Mask common sensitive tokens in logged command strings."""
        pattern = re.compile(r"(?i)(api[-_]?key)(?:\s+|=)\S+")
        masked = pattern.sub(r"\1 ***", command)
        # TODO: extend masking for other secrets such as tokens.
        return masked
