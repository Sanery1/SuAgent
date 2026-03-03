from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
from tools.builtins import get_builtin_tools


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_openai_item(cls, item: dict[str, Any]) -> "ToolCall":
        function = item.get("function", {})
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        return cls(id=item.get("id", ""), name=function.get("name", ""), arguments=arguments)


@dataclass(slots=True)
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False

    def to_message(self) -> dict[str, str]:
        return {"role": "tool", "tool_call_id": self.tool_call_id, "content": self.content}


class ToolExecutor:
    def __init__(self) -> None:
        self.tools = get_builtin_tools()
        self.tool_map = {t.name: t for t in self.tools}

    def parse_tool_calls(self, assistant_message: dict[str, Any]) -> list[ToolCall]:
        openai_calls = assistant_message.get("tool_calls")
        if isinstance(openai_calls, list):
            return [ToolCall.from_openai_item(item) for item in openai_calls]
        return []

    def execute(self, tool_call: ToolCall) -> ToolResult:
        tool = self.tool_map.get(tool_call.name)
        if not tool:
            return ToolResult(tool_call_id=tool_call.id, content=f"Tool '{tool_call.name}' not found", is_error=True)
        try:
            raw = tool.execute(**tool_call.arguments)
        except Exception as exc:
            return ToolResult(tool_call_id=tool_call.id, content=f"Error: {exc}", is_error=True)
        content = json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else str(raw)
        return ToolResult(tool_call_id=tool_call.id, content=content)

    def execute_all(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        return [self.execute(tc) for tc in tool_calls]
