"""
Chatbot 示例：多轮对话
======================

演示目标：
    用 Node/Flow 架构实现一个有对话记忆的聊天机器人。
    核心概念：shared 字典作为"对话历史黑板"，每轮对话都追加消息，
    形成多轮上下文，让 LLM 能记住之前说过的内容。

流程图：
    （用户输入追加到 shared["messages"]）
         │
         ▼
     ChatNode   ← 读取 shared["messages"]，拼 prompt，调 LLM，把回复 append 进去
         │
         │ "output"
         ▼
    OutputNode  ← 打印 LLM 的回复，本轮结束

为什么把消息存在 shared 而不是 payload？
    payload 是节点间的"一次性快递"，适合传单个响应。
    shared 是全局黑板，适合跨轮次累积的状态（对话历史、配置等）。
    每次用户输入后直接 append 到 shared["messages"]，无需通过 payload 传递。
"""

from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Any, Tuple

# 把项目根目录加入 sys.path，使 examples/ 下的文件可以 import core/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import call_llm
from core.node import Node, Flow, shared


class ChatNode(Node):
    """
    对话节点：读取历史消息 → 构造 prompt → 请求 LLM → 追加回复到历史。

    使用"把历史消息手动拼成字符串"的简单方式调用 LLM（call_llm 的简单 prompt 模式）。
    这种方式直观易懂，适合演示多轮对话原理。
    带工具调用的版本（chatbot_with_tools/main.py）使用更正规的 messages 列表模式。

    prompt 拼接示例：
        你是一个友好的对话助手。
        User: 你好
        Assistant: 你好！有什么我可以帮你的？
        User: 最近怎样？
    """

    def exec(self, payload: Any) -> Tuple[str, Any]:
        # 从全局 shared 取出历史消息（第一轮时为空列表）
        messages = shared.get("messages", [])

        # 把历史消息拼成对话格式的字符串，作为 LLM 的完整 prompt
        parts = ["你是一个友好的对话助手。\n"]
        for m in messages:
            role = m.get("role", "")
            if role == "user":       parts.append(f"User: {m['content']}")
            elif role == "assistant": parts.append(f"Assistant: {m['content']}")

        # call_llm 简单模式：传字符串 → 返回字符串
        response = call_llm("\n".join(parts))

        # 把 LLM 的回复追加到历史，供下一轮对话使用
        messages.append({"role": "assistant", "content": response})
        shared["messages"] = messages

        # 返回动作 "output" → 跳到 OutputNode；把 response 作为 payload 传过去
        return "output", response


class OutputNode(Node):
    """输出节点：把 LLM 的回复打印到终端。"""

    def exec(self, payload: Any) -> Tuple[str, Any]:
        print(f"\nAssistant: {payload}\n")
        # 返回 "default"，successors 中无 "default" 后继 → Flow 结束本轮
        return "default", None


def main() -> None:
    # 重置全局状态（防止多次调用 main() 时历史混在一起）
    shared.clear()
    shared["messages"] = []   # 初始化空的对话历史

    # 创建节点并声明流程
    chat = ChatNode()
    output = OutputNode()
    chat - "output" >> output   # ChatNode 返回 "output" → 跳到 OutputNode

    print("=== Chatbot（输入 quit 退出）===\n")
    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！"); break
        if not user_input:
            continue

        # 把用户输入追加到历史（role="user"），然后启动一轮 Flow
        shared["messages"].append({"role": "user", "content": user_input})
        # payload=None，ChatNode 不依赖 payload，直接从 shared 读取历史
        Flow(chat).run(None)


if __name__ == "__main__":
    main()
