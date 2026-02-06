from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


def find_asset(
    preferred_names: Iterable[str],
    globs: Iterable[str],
    base: Path,
) -> Optional[Path]:
    if not base.exists():
        return None
    for name in preferred_names:
        candidate = base / name
        if candidate.exists():
            return candidate
    for pattern in globs:
        matches = sorted(base.glob(pattern))
        for match in matches:
            if match.is_file():
                return match
    return None
