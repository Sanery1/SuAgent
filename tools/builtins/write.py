from __future__ import annotations
from pathlib import Path


def write_file(path: str, content: str, cwd: str | None = None) -> str:
    file_path = (Path(cwd) / path if cwd else Path(path)).resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"Successfully wrote {len(content)} bytes to {path}"
