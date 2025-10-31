"""Sorting helpers for PromptTick."""

from __future__ import annotations

import re
from typing import List, Union

_SPLIT_RE = re.compile(r"\d+|\D+")


def natural_key(name: str) -> List[Union[int, str]]:
    """Return a key for natural sorting of *name*.

    The function splits the provided string into alternating digit and non-digit
    blocks. Digits are converted to integers so that ``file2`` sorts before
    ``file10``. Text blocks are lower-cased for case-insensitive comparisons.
    """

    parts = _SPLIT_RE.findall(name)
    out: List[Union[int, str]] = []
    for part in parts:
        if part.isdigit():
            out.append(int(part))
        else:
            out.append(part.lower())
    return out
