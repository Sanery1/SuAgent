from __future__ import annotations
import re, subprocess
from pathlib import Path

DEFAULT_LIMIT = 100
DEFAULT_MAX_BYTES = 30 * 1024
GREP_MAX_LINE_LENGTH = 1000


def grep(pattern: str, path: str | None = None, glob: str | None = None,
         ignore_case: bool = False, literal: bool = False, context: int = 0,
         limit: int | None = None, cwd: str | None = None) -> str:
    search_path = ((Path(cwd) / (path or ".")) if cwd else Path(path or ".")).resolve()
    if not search_path.exists():
        raise FileNotFoundError(f"Path not found: {search_path}")
    effective_limit = limit or DEFAULT_LIMIT
    try:
        cmd = ["rg", "--line-number", "--color=never", "--hidden"]
        if ignore_case: cmd.append("--ignore-case")
        if literal: cmd.append("--fixed-strings")
        if glob: cmd.extend(["--glob", glob])
        if context > 0: cmd.extend(["-C", str(context)])
        cmd.extend(["--max-count", str(effective_limit), "-m", str(effective_limit)])
        cmd += [pattern, str(search_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode not in (0, 1):
            raise RuntimeError(f"ripgrep failed: {result.stderr}")
        output = result.stdout.strip()
    except FileNotFoundError:
        output = _grep_python(pattern, search_path, glob, ignore_case, literal, context, effective_limit)
        return output
    if not output:
        return "No matches found"
    lines = output.split("\n")
    truncated = []
    lines_truncated = False
    for line in lines:
        if len(line) > GREP_MAX_LINE_LENGTH:
            line = line[:GREP_MAX_LINE_LENGTH] + "..."
            lines_truncated = True
        truncated.append(line)
    output = "\n".join(truncated)
    if len(output.encode("utf-8")) > DEFAULT_MAX_BYTES:
        output = output.encode("utf-8")[:DEFAULT_MAX_BYTES].decode("utf-8", errors="ignore")
        output += f"\n\n[{DEFAULT_MAX_BYTES // 1024}KB limit reached]"
    notices = []
    if len(truncated) >= effective_limit: notices.append(f"{effective_limit} matches limit reached")
    if lines_truncated: notices.append(f"Some lines truncated to {GREP_MAX_LINE_LENGTH} chars")
    if notices: output += f"\n\n[{'. '.join(notices)}]"
    return output


def _grep_python(pattern, search_path, glob, ignore_case, literal, context, limit) -> str:
    flags = re.IGNORECASE if ignore_case else 0
    if literal: pattern = re.escape(pattern)
    regex = re.compile(pattern, flags)
    matches = []
    count = 0
    files = [search_path] if search_path.is_file() else (
        list(search_path.rglob(glob)) if glob else [f for f in search_path.rglob("*") if f.is_file()])
    for file_path in files:
        if count >= limit: break
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").split("\n")
            for i, line in enumerate(lines, 1):
                if count >= limit: break
                if regex.search(line):
                    rel = str(file_path.relative_to(search_path) if search_path in file_path.parents else file_path.name)
                    if context > 0:
                        for j in range(max(0, i-context-1), min(len(lines), i+context)):
                            prefix = f"{rel}:{j+1}:" if j == i-1 else f"{rel}-{j+1}-"
                            matches.append(f"{prefix} {lines[j]}")
                    else:
                        matches.append(f"{rel}:{i}: {line}")
                    count += 1
        except Exception:
            continue
    if not matches: return "No matches found"
    output = "\n".join(matches)
    if len(output.encode("utf-8")) > DEFAULT_MAX_BYTES:
        output = output.encode("utf-8")[:DEFAULT_MAX_BYTES].decode("utf-8", errors="ignore")
        output += f"\n\n[{DEFAULT_MAX_BYTES // 1024}KB limit reached]"
    return output
