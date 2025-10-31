"""PromptTick Round 2 processing entry point."""
from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - import guard
    print("缺少依赖：PyYAML。请先运行 `pip install pyyaml`。", file=sys.stderr)
    sys.exit(1)

from adapters import make_adapter
from utils.sort import natural_key

APP_NAME = "PromptTick"
APP_VERSION = "0.5.0-round5"
REQUIRED_CONFIG_KEYS = {
    "input_dir",
    "output_dir",
    "log_dir",
    "state_path",
    "file_extensions",
    "ordering",
    "log_level",
}


def load_config(path: Path) -> dict[str, Any]:
    """Load YAML configuration from *path*."""

    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if data is None:
        raise ValueError("配置文件为空，请填写必要配置后再运行。")

    return data


def validate_config(cfg: dict[str, Any]) -> None:
    """Validate that mandatory configuration keys are present and well-formed."""

    missing = REQUIRED_CONFIG_KEYS - cfg.keys()
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(f"配置缺少必填项：{joined}")

    if not isinstance(cfg.get("file_extensions"), list) or not all(
        isinstance(ext, str) for ext in cfg["file_extensions"]
    ):
        raise ValueError("file_extensions 必须为字符串列表")

    if not isinstance(cfg.get("ordering"), str):
        raise ValueError("ordering 必须为字符串")

    if not isinstance(cfg.get("log_level"), str):
        raise ValueError("log_level 必须为字符串")


def setup_logger(log_dir: Path, level: str = "INFO") -> None:
    """Initialize console and dated file logging handlers."""

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run-{time.strftime('%Y%m%d')}.log"

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
        force=True,
    )


def ensure_dirs_and_state(cfg: dict[str, Any]) -> None:
    """Ensure configured directories and ``state.json`` exist."""

    input_dir = Path(cfg["input_dir"]).expanduser()
    output_dir = Path(cfg["output_dir"]).expanduser()
    log_dir = Path(cfg["log_dir"]).expanduser()
    state_path = Path(cfg["state_path"]).expanduser()

    for directory in (input_dir, output_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    if not state_path.exists():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"processed": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def print_boot_info(cfg: dict[str, Any], config_path: Path) -> None:
    """Log boot information for troubleshooting purposes."""

    logging.info("%s v%s 启动（Round 2 核心流程模式）", APP_NAME, APP_VERSION)
    logging.info(
        "Python: %s | OS: %s %s",
        platform.python_version(),
        platform.system(),
        platform.release(),
    )
    logging.info("配置文件: %s", config_path.resolve())
    logging.info(
        "关键路径: input=%s | output=%s | logs=%s | state=%s",
        cfg["input_dir"],
        cfg["output_dir"],
        cfg["log_dir"],
        cfg["state_path"],
    )
    logging.info(
        "处理参数: ordering=%s | batch_size=%s | interval=%s s",
        cfg.get("ordering"),
        resolve_batch_size(cfg),
        cfg.get("interval_seconds", "n/a"),
    )


def resolve_batch_size(cfg: dict[str, Any]) -> int:
    """Return a sanitized ``batch_size`` value from *cfg*."""

    try:
        batch_size = int(cfg.get("batch_size", 1))
    except (TypeError, ValueError):
        logging.warning("batch_size 配置无效，默认 1")
        batch_size = 1
    return max(batch_size, 1)


def effective_cap(batch_size: int, limit: int | None) -> int:
    """Compute the maximum items to handle based on *batch_size* and *limit*."""

    if limit is None:
        return batch_size
    return max(0, min(batch_size, limit))


def collect_pending(cfg: dict[str, Any], processed_set: set[str]) -> list[Path]:
    """Collect files pending processing respecting configuration filters."""

    input_dir = Path(cfg["input_dir"]).expanduser()
    extensions = cfg.get("file_extensions", [])
    if not extensions:
        logging.warning("配置 file_extensions 为空，默认使用 .txt")
        extensions = [".txt"]
    ordering = cfg.get("ordering", "name")
    files = list_prompt_files(input_dir, [ext.lower() for ext in extensions], ordering)
    return [path for path in files if str(path.resolve()) not in processed_set]


def log_startup_summary(
    cfg: dict[str, Any],
    mode: str,
    adapter_name: str,
    dry_run: bool,
    limit: int | None,
) -> None:
    """Log a concise summary of the current run configuration."""

    logging.info("启动模式: %s | 适配器: %s | dry_run=%s | limit=%s", mode, adapter_name, dry_run, limit)
    logging.info(
        "排序: %s | batch_size=%s",
        cfg.get("ordering", "name"),
        resolve_batch_size(cfg),
    )


def list_prompt_files(input_dir: Path, exts: list[str], ordering: str) -> list[Path]:
    """List prompt files under *input_dir* filtered by extensions and ordering."""

    lower_exts = [ext.lower() for ext in exts]
    files: list[Path] = []
    for path in input_dir.iterdir():
        if not path.is_file():
            continue
        name = path.name
        lower_name = name.lower()
        if lower_name.endswith((".part", ".lock", ".tmp")):
            continue
        if path.suffix.lower() not in lower_exts:
            continue
        files.append(path)

    ordering_mode = ordering.lower()
    if ordering_mode == "mtime":
        files.sort(key=lambda item: item.stat().st_mtime)
    else:
        if ordering_mode != "name":
            logging.warning("未知排序方式 %s，回退至 name", ordering)
        files.sort(key=lambda item: natural_key(item.name))

    return files


def load_state(state_path: Path) -> dict[str, Any]:
    """Load persisted state from ``state.json``; fall back to a clean state."""

    if not state_path.exists():
        return {"processed": []}

    try:
        raw = state_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:  # pragma: no cover - defensive IO guard
        logging.warning("state.json 读取失败，使用空状态重建")
        return {"processed": []}

    processed = data.get("processed", []) if isinstance(data, dict) else []
    if not isinstance(processed, list) or not all(isinstance(item, str) for item in processed):
        logging.warning("state.json 内容异常，重置 processed 列表")
        processed = []

    return {"processed": processed}


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    """Persist ``state`` to ``state_path`` in UTF-8 encoded JSON."""

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_text(path: Path) -> str:
    """Read UTF-8 text from *path* and replace undecodable characters."""

    return path.read_text(encoding="utf-8", errors="replace")


def _timestamp() -> str:
    """Return a filesystem-friendly timestamp string."""

    return datetime.now().strftime("%Y%m%d-%H%M%S")


def write_output(output_dir: Path, input_file: Path, content: str) -> Path:
    """Write *content* to *output_dir* using the configured naming convention."""

    output_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{_timestamp()}_{input_file.name}.out.txt"
    out_path = output_dir / out_name
    out_path.write_text(content, encoding="utf-8")
    return out_path


def process_once(cfg: dict[str, Any], adapter: Any, limit: int | None = None) -> int:
    """Run a single processing round and return the number of successful files."""

    input_dir = Path(cfg["input_dir"]).expanduser()
    output_dir = Path(cfg["output_dir"]).expanduser()
    state_path = Path(cfg["state_path"]).expanduser()

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    batch_size = resolve_batch_size(cfg)
    cap = effective_cap(batch_size, limit)

    state = load_state(state_path)
    processed_set = {item for item in state.get("processed", []) if isinstance(item, str)}

    pending = collect_pending(cfg, processed_set)

    if not pending or cap == 0:
        if not pending:
            logging.info("没有待处理的文件")
        else:
            logging.info("批次上限为 0，本轮不处理文件")
        return 0

    to_handle = pending[:cap]
    success_count = 0

    for file_path in to_handle:
        abs_str = str(file_path.resolve())
        try:
            prompt_text = read_text(file_path).strip()
            if not prompt_text:
                logging.info("跳过空文件: %s", file_path.name)
                processed_set.add(abs_str)
                continue

            logging.info("处理: %s", file_path.name)
            output_text = adapter.generate(prompt_text)
            out_path = write_output(output_dir, file_path, output_text)
            logging.info("输出: %s", out_path.name)

            processed_set.add(abs_str)
            success_count += 1
        except Exception as exc:  # pragma: no cover - defensive per-file guard
            logging.exception("处理失败: %s -> %s", file_path.name, exc)

    state["processed"] = sorted(processed_set)
    save_state(state_path, state)
    return success_count


def loop_forever(cfg: dict[str, Any], adapter: Any, limit: int | None = None) -> None:
    """Continuously execute :func:`process_once` with configured intervals."""

    try:
        interval = int(cfg.get("interval_seconds", 300))
    except (TypeError, ValueError):
        logging.warning("interval_seconds 配置无效，默认 300 秒")
        interval = 300
    interval = max(interval, 1)

    logging.info("进入定时模式，按 Ctrl+C 退出")
    try:
        while True:
            processed = process_once(cfg, adapter, limit=limit)
            logging.info("本轮处理文件数: %s，休眠 %s 秒", processed, interval)
            time.sleep(interval)
    except KeyboardInterrupt:  # pragma: no cover - interactive loop guard
        logging.info("收到中断，退出")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="PromptTick - Round 2 Processor")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径（默认 config.yaml）")
    parser.add_argument("--once", action="store_true", help="仅执行一轮处理后退出")
    parser.add_argument("--rescan", action="store_true", help="重置 state.json，重新处理全部文件")
    parser.add_argument("--dry-run", action="store_true", help="预演处理列表但不调用适配器")
    parser.add_argument(
        "--limit",
        type=int,
        help="限制本轮最多处理的文件数，与 batch_size 取最小值",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point used by ``python main.py``."""

    try:
        args = parse_args(argv)
        config_path = Path(args.config)
        cfg = load_config(config_path)
        validate_config(cfg)

        log_dir = Path(cfg["log_dir"]).expanduser()
        setup_logger(log_dir, level=cfg.get("log_level", "INFO"))

        ensure_dirs_and_state(cfg)
        print_boot_info(cfg, config_path)

        adapter_name = cfg.get("adapter", "echo_adapter")
        adapter = make_adapter(adapter_name, cfg)
        logging.info("使用适配器: %s", adapter_name)

        if args.limit is not None and args.limit <= 0:
            raise ValueError("--limit 必须为正整数")

        mode_label = "once" if args.once else "loop_forever"
        log_startup_summary(cfg, mode_label, adapter_name, args.dry_run, args.limit)

        state_path = Path(cfg["state_path"]).expanduser()
        if args.dry_run:
            state = load_state(state_path)
            processed_raw = [] if args.rescan else state.get("processed", [])
            processed_set = {item for item in processed_raw if isinstance(item, str)}
            pending = collect_pending(cfg, processed_set)
            batch_size = resolve_batch_size(cfg)
            cap = effective_cap(batch_size, args.limit)
            logging.info("[DRY-RUN] 适配器: %s", adapter_name)
            logging.info(
                "[DRY-RUN] ordering=%s | batch_size=%s | limit=%s | effective_cap=%s",
                cfg.get("ordering", "name"),
                batch_size,
                args.limit,
                cap,
            )
            logging.info("[DRY-RUN] 将要处理的数量上限: %s", cap)
            if pending and cap > 0:
                preview = [path.name for path in pending[:cap]]
                logging.info("[DRY-RUN] 将处理以下文件: %s", ", ".join(preview))
            elif pending:
                logging.info("[DRY-RUN] 列表: %s", ", ".join(path.name for path in pending))
                logging.info("[DRY-RUN] 注意: 有待处理文件但当前有效上限为 0")
            else:
                logging.info("[DRY-RUN] 没有待处理的文件")
            return 0

        if args.rescan:
            logging.info("收到 --rescan，清空 state.json")
            save_state(state_path, {"processed": []})

        if args.once:
            processed = process_once(cfg, adapter, limit=args.limit)
            logging.info("本轮处理文件数: %s", processed)
            return 0

        loop_forever(cfg, adapter, limit=args.limit)
        return 0
    except Exception as exc:  # pragma: no cover - defensive top-level guard
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
