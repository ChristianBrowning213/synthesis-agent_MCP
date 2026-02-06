from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional

from src import ASSETS_DIR

DEFAULT_MAX_FILE_BYTES = 2_000_000


class PathResolutionError(RuntimeError):
    def __init__(self, error_type: str, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details or {}


def _parse_max_bytes() -> int:
    value = os.getenv("SKY_MCP_MAX_FILE_BYTES")
    if not value:
        return DEFAULT_MAX_FILE_BYTES
    try:
        parsed = int(value)
        return parsed if parsed > 0 else DEFAULT_MAX_FILE_BYTES
    except ValueError:
        return DEFAULT_MAX_FILE_BYTES


def _default_allowed_roots() -> List[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    roots = [repo_root, ASSETS_DIR, Path.cwd()]
    extra = os.getenv("SKY_MCP_ALLOWED_ROOTS")
    if extra:
        for raw in extra.split(os.pathsep):
            raw = raw.strip()
            if raw:
                roots.append(Path(raw))
    return roots


def resolve_local_path(
    path_str: str,
    allowed_roots: Optional[Iterable[Path]] = None,
    max_bytes: Optional[int] = None,
) -> Path:
    if not path_str or not str(path_str).strip():
        raise PathResolutionError("invalid_input", "Path is required.")

    try:
        candidate = Path(path_str).expanduser()
    except Exception as exc:
        raise PathResolutionError(
            "invalid_input", "Invalid path string.", details={"error": str(exc)}
        ) from exc

    resolved = candidate.resolve(strict=False)
    roots = list(allowed_roots) if allowed_roots is not None else _default_allowed_roots()
    resolved_roots = [Path(root).expanduser().resolve(strict=False) for root in roots]

    if not any(resolved.is_relative_to(root) for root in resolved_roots):
        raise PathResolutionError(
            "permission_denied",
            "Path is outside allowed roots.",
            details={
                "path": str(resolved),
                "allowed_roots": [str(r) for r in resolved_roots],
            },
        )

    if not resolved.exists():
        raise PathResolutionError(
            "file_not_found",
            "File not found.",
            details={"path": str(resolved)},
        )

    if not resolved.is_file():
        raise PathResolutionError(
            "invalid_input",
            "Path is not a file.",
            details={"path": str(resolved)},
        )

    limit = max_bytes if max_bytes is not None else _parse_max_bytes()
    try:
        size = resolved.stat().st_size
    except OSError as exc:
        raise PathResolutionError(
            "runtime_error",
            "Unable to stat file.",
            details={"path": str(resolved), "error": str(exc)},
        ) from exc

    if size > limit:
        raise PathResolutionError(
            "file_too_large",
            "File exceeds size limit.",
            details={"path": str(resolved), "size": size, "max_bytes": limit},
        )

    return resolved
