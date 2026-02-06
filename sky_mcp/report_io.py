from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Callable
from uuid import uuid4


def _slugify(text: str, max_len: int = 50) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text or "").strip("_")
    if not slug:
        slug = "report"
    return slug[:max_len]


def build_report_path(
    query: str,
    reports_dir: Path,
    uuid_func: Callable[[], object] = uuid4,
) -> Path:
    slug = _slugify(query)
    uid = str(uuid_func())
    filename = f"{slug}_{uid}.html"
    return reports_dir / filename


def atomic_write_text(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=str(target_path.parent),
        prefix=target_path.stem + "_",
        suffix=".tmp",
    ) as tmp:
        tmp.write(content)
        temp_name = tmp.name
    os.replace(temp_name, target_path)
