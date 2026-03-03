from __future__ import annotations
from pathlib import Path

DEFAULT_MAX_BYTES = 30 * 1024
DEFAULT_MAX_LINES = 2000


def read_file(path: str, offset: int | None = None, limit: int | None = None, cwd: str | None = None) -> str:
    file_path = (Path(cwd) / path if cwd else Path(path)).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not file_path.is_file():
        raise ValueError(f"Not a file: {path}")
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    total_lines = len(lines)
    start_line = max(0, (offset or 1) - 1)
    if start_line >= total_lines:
        raise ValueError(f"Offset {offset} is beyond end of file ({total_lines} lines total)")
    end_line = min(start_line + limit, total_lines) if limit is not None else total_lines
    result = "\n".join(lines[start_line:end_line])
    result_bytes = result.encode("utf-8")
    if len(result_bytes) > DEFAULT_MAX_BYTES:
        truncated = result_bytes[:DEFAULT_MAX_BYTES].decode("utf-8", errors="ignore")
        last_nl = truncated.rfind("\n")
        if last_nl > 0:
            truncated = truncated[:last_nl]
        end_line = start_line + truncated.count("\n") + 1
        result = truncated + f"\n\n[Showing lines {start_line+1}-{end_line} of {total_lines}. Use offset={end_line+1} to continue.]"
    elif limit is not None and end_line < total_lines:
        result += f"\n\n[{total_lines - end_line} more lines. Use offset={end_line+1} to continue.]"
    return result
