"""Fake local model script that echoes prompt content with a prefix."""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    """Entry point for the fake local model script."""
    parser = argparse.ArgumentParser(description="Fake local model returning prompt content.")
    parser.add_argument("--in", dest="in_path", required=True, help="Path to the input prompt file.")
    parser.add_argument("--out", dest="out_path", required=True, help="Path to write the output file.")
    args = parser.parse_args()

    input_path = Path(args.in_path)
    output_path = Path(args.out_path)

    prompt_text = input_path.read_text(encoding="utf-8")
    output_text = "[LOCAL FAKE]\n" + prompt_text
    output_path.write_text(output_text, encoding="utf-8")


if __name__ == "__main__":
    main()
