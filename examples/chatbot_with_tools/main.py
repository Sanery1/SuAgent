"""Agent 示例：带工具的对话（ChatNode -tool_call-> ToolCallNode -chat-> ChatNode）"""
from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import call_llm
from core.node import Node, Flow, shared
from tools import get_tools, ToolExecutor

SYSTEM_PROMPT = (
    "你是一个会调用工具的助手。"
    "涉及最新信息时优先用 search 工具；本地文件相关优先用 read/grep/find/ls 等工具。"
)


class ChatNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        messages = shared.get("messages", [])
        tools = shared.get("tools", [])
        assistant_msg = call_llm(messages=messages, tools=tools, system_prompt=SYSTEM_PROMPT)
        messages.append(assistant_msg)
        shared["messages"] = messages
        if assistant_msg.get("tool_calls"):
            return "tool_call", assistant_msg
        return "output", assistant_msg


class ToolCallNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        messages = shared.get("messages", [])
        executor: ToolExecutor = shared.get("tool_executor")
        tool_calls = executor.parse_tool_calls(payload)
        results = executor.execute_all(tool_calls)
        for tc, result in zip(tool_calls, results):
            print(f"  [Tool] {tc.name}({tc.arguments})")
            print(f"  [Result] {result.content[:150]}...")
            messages.append(result.to_message())
        shared["messages"] = messages
        return "chat", None


class OutputNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        print(f"\nAssistant: {payload.get('content', '')}\n")
        return "default", None


def main() -> None:
    shared.clear()
    shared["messages"] = []
    shared["tools"] = [t.to_llm_format() for t in get_tools()]
    shared["tool_executor"] = ToolExecutor()

    chat = ChatNode()
    tool_call = ToolCallNode()
    output = OutputNode()

    chat - "tool_call" >> tool_call
    tool_call - "chat" >> chat
    chat - "output" >> output

    print("=== Agent（输入 quit 退出）===\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！"); break
        if not user_input: continue
        shared["messages"].append({"role": "user", "content": user_input})
        Flow(chat).run(None)


if __name__ == "__main__":
    main()
