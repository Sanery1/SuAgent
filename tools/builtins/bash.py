from __future__ import annotations
import subprocess
from pathlib import Path

DEFAULT_MAX_BYTES = 30 * 1024
DEFAULT_MAX_LINES = 2000


def bash(command: str, timeout: int | None = None, cwd: str | None = None) -> dict:
    work_dir = Path(cwd) if cwd else Path.cwd()
    if not work_dir.exists():
        raise FileNotFoundError(f"Working directory does not exist: {work_dir}")
    try:
        result = subprocess.run(
            command, shell=True, cwd=work_dir,
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr if output else result.stderr
        lines = output.split("\n")
        if len(lines) > DEFAULT_MAX_LINES:
            lines = lines[-DEFAULT_MAX_LINES:]
            output = f"[Output truncated to last {DEFAULT_MAX_LINES} lines]\n" + "\n".join(lines)
        if len(output.encode("utf-8")) > DEFAULT_MAX_BYTES:
            output = output.encode("utf-8")[-DEFAULT_MAX_BYTES:].decode("utf-8", errors="ignore")
            output = f"[Output truncated to last {DEFAULT_MAX_BYTES // 1024}KB]\n{output}"
        return {"stdout": output, "stderr": result.stderr or "", "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Command timed out after {timeout}s", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}
