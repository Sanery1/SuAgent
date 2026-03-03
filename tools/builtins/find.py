from __future__ import annotations
import subprocess
from pathlib import Path

DEFAULT_LIMIT = 1000
DEFAULT_MAX_BYTES = 30 * 1024


def find(pattern: str, path: str | None = None, limit: int | None = None, cwd: str | None = None) -> str:
    search_path = ((Path(cwd) / (path or ".")) if cwd else Path(path or ".")).resolve()
    if not search_path.exists():
        raise FileNotFoundError(f"Path not found: {search_path}")
    if not search_path.is_dir():
        raise ValueError(f"Not a directory: {search_path}")
    effective_limit = limit or DEFAULT_LIMIT
    try:
        cmd = ["fd", "--glob", "--color=never", "--hidden", "--max-results", str(effective_limit), pattern, str(search_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode not in (0, 1):
            raise RuntimeError(f"fd failed: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            return "No files found matching pattern"
        results = []
        for line in output.split("\n"):
            line = line.strip()
            if not line: continue
            try:
                results.append(str(Path(line).relative_to(search_path)))
            except ValueError:
                results.append(Path(line).name)
    except FileNotFoundError:
        return _find_python(pattern, search_path, effective_limit)
    result_text = "\n".join(results)
    if len(result_text.encode("utf-8")) > DEFAULT_MAX_BYTES:
        result_text = result_text.encode("utf-8")[:DEFAULT_MAX_BYTES].decode("utf-8", errors="ignore")
        result_text += f"\n\n[{DEFAULT_MAX_BYTES // 1024}KB limit reached]"
    if len(results) >= effective_limit:
        result_text += f"\n\n[{effective_limit} results limit reached]"
    return result_text


def _find_python(pattern: str, search_path: Path, limit: int) -> str:
    files = list(search_path.rglob(pattern.lstrip("**/")) if "**" in pattern else search_path.glob(pattern))
    results = []
    for f in files:
        if len(results) >= limit: break
        if f.is_file():
            try: results.append(str(f.relative_to(search_path)))
            except ValueError: results.append(f.name)
    if not results: return "No files found matching pattern"
    result_text = "\n".join(sorted(results))
    if len(result_text.encode("utf-8")) > DEFAULT_MAX_BYTES:
        result_text = result_text.encode("utf-8")[:DEFAULT_MAX_BYTES].decode("utf-8", errors="ignore")
        result_text += f"\n\n[{DEFAULT_MAX_BYTES // 1024}KB limit reached]"
    if len(results) >= limit:
        result_text += f"\n\n[{limit} results limit reached]"
    return result_text
