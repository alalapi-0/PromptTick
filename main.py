"""PromptTick Round 1 bootstrap entry point."""
from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - import guard
    print("缺少依赖：PyYAML。请先运行 `pip install pyyaml`。", file=sys.stderr)
    sys.exit(1)


APP_NAME = "PromptTick"
APP_VERSION = "0.1.0-round1"
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
    """Load YAML configuration from *path*.

    Parameters
    ----------
    path:
        Path to the YAML configuration file.

    Returns
    -------
    dict[str, Any]
        Parsed configuration mapping.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the configuration file is empty.
    yaml.YAMLError
        If the YAML content cannot be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

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
    """Initialize console and file logging handlers."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run.log"

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
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
    logging.info("%s v%s 启动（Round 1 自检模式）", APP_NAME, APP_VERSION)
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
    logging.info("日志级别: %s", cfg.get("log_level", "INFO"))
    logging.info("本轮不执行业务处理（定时循环/适配器调用在下一轮实现）。")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv:
        Optional argument list, defaults to :data:`sys.argv` when ``None``.
    """
    parser = argparse.ArgumentParser(description="PromptTick - Round 1 Boot Check")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径（默认 config.yaml）")
    parser.add_argument("--once", action="store_true", help="本轮仅用于自检；传与不传行为相同")
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
    except Exception as exc:  # pragma: no cover - defensive top-level guard
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
