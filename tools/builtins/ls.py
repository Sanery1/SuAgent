from __future__ import annotations
from pathlib import Path

DEFAULT_LIMIT = 500
DEFAULT_MAX_BYTES = 30 * 1024


def ls(path: str | None = None, limit: int | None = None, cwd: str | None = None) -> str:
    dir_path = ((Path(cwd) / (path or ".")) if cwd else Path(path or ".")).resolve()
    if not dir_path.exists():
        raise FileNotFoundError(f"Path not found: {dir_path}")
    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {dir_path}")
    effective_limit = limit or DEFAULT_LIMIT
    entries = sorted(dir_path.iterdir(), key=lambda e: e.name.lower())
    results = []
    limit_reached = False
    for entry in entries:
        if len(results) >= effective_limit:
            limit_reached = True
            break
        results.append(entry.name + ("/" if entry.is_dir() else ""))
    if not results:
        return "(empty directory)"
    output = "\n".join(results)
    if len(output.encode("utf-8")) > DEFAULT_MAX_BYTES:
        output = output.encode("utf-8")[:DEFAULT_MAX_BYTES].decode("utf-8", errors="ignore")
        output += f"\n\n[{DEFAULT_MAX_BYTES // 1024}KB limit reached]"
    if limit_reached:
        output += f"\n\n[{effective_limit} entries limit reached]"
    return output
