"""
工具定义模块
============

本模块定义两个核心概念：

  Tool（工具对象）：
      把一个普通 Python 函数封装成"LLM 可以调用"的工具。
      核心能力：to_llm_format() 生成 OpenAI Function Calling 所需的 JSON Schema，
      让 LLM 知道"有哪些工具可用、每个参数的类型和含义"。

  get_builtin_tools()：
      返回本项目内置的 8 个工具实例，供 Agent 使用。

OpenAI Function Calling 的工作原理：
    1. 调用 LLM 时在请求体中附上 tools 列表（每个元素由 to_llm_format() 生成）
    2. LLM 在回复中若决定调用工具，会返回：
           {"tool_calls": [{"id": "...", "function": {"name": "read", "arguments": '{"path": "a.py"}'}}]}
    3. 我们执行对应函数，把结果以 role="tool" 消息格式送回给 LLM
    4. LLM 继续生成最终回复
"""

from __future__ import annotations
from typing import Any, Callable, List


class Tool:
    """
    工具封装类：把一个 Python 函数包装成 LLM 可以理解和调用的工具。

    Attributes:
        name        : 工具名称，LLM 调用时通过此名字识别（如 "read"、"bash"）
        description : 工具的自然语言描述，告诉 LLM "这个工具用来做什么"
                      描述写得越清晰，LLM 选择工具越准确
        parameters  : JSON Schema 格式的参数定义，告诉 LLM 参数名、类型、是否必填
        fn          : 实际执行的 Python 可调用对象（函数或 lambda）
    """

    def __init__(self, name: str, description: str, parameters: dict, fn: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn

    def to_llm_format(self) -> dict:
        """
        生成 OpenAI Function Calling 所需的工具描述字典。

        返回格式（符合 OpenAI tools 列表中每个元素的规范）：
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read file contents...",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            ...
                        },
                        "required": ["path"]
                    }
                }
            }

        这个字典会直接放进 call_llm(tools=[...]) 的列表里。
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs) -> Any:
        """
        执行工具函数。

        kwargs 来自 LLM 返回的 tool_call.function.arguments（JSON 解析后的字典）。
        例如 LLM 返回 '{"path": "src/main.py", "limit": 50}'，
        则 kwargs = {"path": "src/main.py", "limit": 50}。
        """
        return self.fn(**kwargs)


def get_builtin_tools() -> List[Tool]:
    """
    返回所有内置工具的实例列表。

    内置 8 个工具：
        read   - 读文件（支持分页，避免一次读入过大文件撑爆上下文）
        write  - 写文件（自动创建父目录）
        edit   - 精确替换文件片段（old_text 必须唯一，防止误改）
        bash   - 执行 Shell 命令（输出截断到 2000 行 / 30KB）
        grep   - 正则搜索文件内容（优先用 rg，无则 fallback 到 Python re）
        find   - 按 glob 模式查找文件（优先用 fd，无则 fallback 到 Python glob）
        ls     - 列出目录内容
        search - DuckDuckGo 网络搜索

    延迟导入（在函数体内 import）的原因：
        避免循环导入，且只有在需要工具时才加载对应模块。
    """
    # 延迟导入，避免模块级别的循环依赖
    from .read import read_file
    from .write import write_file
    from .edit import edit_file
    from .bash import bash
    from .grep import grep
    from .find import find
    from .ls import ls
    from .search import search

    return [
        # ── 文件读写 ──────────────────────────────────────────────────────────
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

        # ── Shell 命令 ────────────────────────────────────────────────────────
        Tool("bash", "Execute bash command. Output truncated to 2000 lines or 30KB.",
             {"type": "object", "properties": {
                 "command": {"type": "string", "description": "Command to execute"},
                 "timeout": {"type": "integer", "description": "Timeout in seconds"},
             }, "required": ["command"]}, fn=bash),

        # ── 搜索类 ────────────────────────────────────────────────────────────
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

        # ── 网络搜索 ──────────────────────────────────────────────────────────
        Tool("search", "Search the web for up-to-date information.",
             {"type": "object", "properties": {
                 "query": {"type": "string", "description": "Search query"},
                 "max_results": {"type": "integer", "description": "Maximum number of results"},
             }, "required": ["query"]}, fn=search),
    ]
