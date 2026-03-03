from __future__ import annotations
from typing import Any, Callable, List


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, fn: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn

    def to_llm_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs) -> Any:
        return self.fn(**kwargs)


def get_builtin_tools() -> List[Tool]:
    from .read import read_file
    from .write import write_file
    from .edit import edit_file
    from .bash import bash
    from .grep import grep
    from .find import find
    from .ls import ls
    from .search import search

    return [
        Tool("read", "Read file contents. Use offset/limit for large files.",
             {"type": "object", "properties": {
                 "path": {"type": "string", "description": "File path"},
                 "offset": {"type": "integer", "description": "Start line (1-indexed)"},
                 "limit": {"type": "integer", "description": "Max lines to read"},
             }, "required": ["path"]}, fn=read_file),
        Tool("write", "Write content to a file. Creates parent directories automatically.",
             {"type": "object", "properties": {
                 "path": {"type": "string", "description": "File path"},
                 "content": {"type": "string", "description": "Content to write"},
             }, "required": ["path", "content"]}, fn=write_file),
        Tool("edit", "Edit file by replacing exact text. old_text must match exactly and be unique.",
             {"type": "object", "properties": {
                 "path": {"type": "string", "description": "File path"},
                 "old_text": {"type": "string", "description": "Exact text to find (must be unique)"},
                 "new_text": {"type": "string", "description": "Replacement text"},
             }, "required": ["path", "old_text", "new_text"]}, fn=edit_file),
        Tool("bash", "Execute bash command. Output truncated to 2000 lines or 30KB.",
             {"type": "object", "properties": {
                 "command": {"type": "string", "description": "Command to execute"},
                 "timeout": {"type": "integer", "description": "Timeout in seconds"},
             }, "required": ["command"]}, fn=bash),
        Tool("grep", "Search file contents for a pattern.",
             {"type": "object", "properties": {
                 "pattern": {"type": "string", "description": "Search pattern (regex)"},
                 "path": {"type": "string", "description": "Directory or file to search"},
                 "glob": {"type": "string", "description": "File pattern e.g. '*.py'"},
             }, "required": ["pattern"]}, fn=grep),
        Tool("find", "Find files by glob pattern.",
             {"type": "object", "properties": {
                 "pattern": {"type": "string", "description": "Glob pattern e.g. '*.py'"},
                 "path": {"type": "string", "description": "Directory to search"},
             }, "required": ["pattern"]}, fn=find),
        Tool("ls", "List directory contents.",
             {"type": "object", "properties": {
                 "path": {"type": "string", "description": "Directory path"},
             }}, fn=ls),
        Tool("search", "Search the web for up-to-date information.",
             {"type": "object", "properties": {
                 "query": {"type": "string", "description": "Search query"},
                 "max_results": {"type": "integer", "description": "Maximum number of results"},
             }, "required": ["query"]}, fn=search),
    ]
