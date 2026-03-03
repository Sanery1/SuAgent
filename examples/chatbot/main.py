"""Chatbot 示例：多轮对话"""
from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import call_llm
from core.node import Node, Flow, shared


class ChatNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        messages = shared.get("messages", [])
        parts = ["你是一个友好的对话助手。\n"]
        for m in messages:
            role = m.get("role", "")
            if role == "user":    parts.append(f"User: {m['content']}")
            elif role == "assistant": parts.append(f"Assistant: {m['content']}")
        response = call_llm("\n".join(parts))
        messages.append({"role": "assistant", "content": response})
        shared["messages"] = messages
        return "output", response


class OutputNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        print(f"\nAssistant: {payload}\n")
        return "default", None


def main() -> None:
    shared.clear()
    shared["messages"] = []
    chat = ChatNode()
    output = OutputNode()
    chat - "output" >> output

    print("=== Chatbot（输入 quit 退出）===\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！"); break
        if not user_input: continue
        shared["messages"].append({"role": "user", "content": user_input})
        Flow(chat).run(None)


if __name__ == "__main__":
    main()
