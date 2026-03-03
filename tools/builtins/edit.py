from __future__ import annotations
from pathlib import Path


def edit_file(path: str, old_text: str, new_text: str, cwd: str | None = None) -> dict:
    file_path = (Path(cwd) / path if cwd else Path(path)).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    content = file_path.read_text(encoding="utf-8")
    if old_text not in content:
        raise ValueError(f"Could not find the exact text in {path}. The old text must match exactly.")
    occurrences = content.count(old_text)
    if occurrences > 1:
        raise ValueError(f"Found {occurrences} occurrences in {path}. The text must be unique.")
    new_content = content.replace(old_text, new_text, 1)
    if content == new_content:
        raise ValueError(f"No changes made to {path}.")
    file_path.write_text(new_content, encoding="utf-8")
    old_lines = content.split("\n")
    new_lines = new_content.split("\n")
    first_changed = next((i + 1 for i, (o, n) in enumerate(zip(old_lines, new_lines)) if o != n), None)
    return {"message": f"Successfully replaced text in {path}", "first_changed_line": first_changed}
