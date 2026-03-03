from .builtins import get_builtin_tools, Tool
from .executor import ToolExecutor, ToolResult

__all__ = ["Tool", "get_builtin_tools", "ToolExecutor", "ToolResult",
           "get_tools", "execute_tool"]


def get_tools():
    return get_builtin_tools()


def execute_tool(name: str, arguments: dict) -> str:
    tools = get_builtin_tools()
    tool_map = {t.name: t for t in tools}
    tool = tool_map.get(name)
    if not tool:
        return f"Error: Tool '{name}' not found"
    try:
        result = tool.execute(**arguments)
        return str(result)
    except Exception as e:
        return f"Error: {e}"
