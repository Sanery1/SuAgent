"""
Multi-Agent 示例：Master Agent + Subagent

核心价值：上下文隔离
  - 没有 Multi-Agent：所有工具调用细节都堆在主 context 里，越来越臃肿
  - 有 Multi-Agent：Subagent 在独立 context 中工作，只把最终结果摘要回传给 Master

结构：
  Master Agent
    ├── 直接回答简单问题
    └── 遇到需要大量工具操作的复杂任务
            └── 派发给 Subagent（全新 context）
                    └── Subagent 完成工作，只把"结论"回传 Master
                            └── Master context 保持干净
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.llm import client, call_llm, DEFAULT_MODEL
from tools import ALL_TOOLS, TOOL_EXECUTOR

# ─────────────────────────────────────────────────────────────────────────────
# Subagent：在完全独立的 context 中完成一个具体任务，只返回结论摘要
# ─────────────────────────────────────────────────────────────────────────────

SUBAGENT_SYSTEM = """你是一个专注执行具体任务的 AI。
你有 bash / read_file / write_file / edit_file 工具。
完成任务后，用简洁的一段话总结你做了什么、结果如何。"""


def run_subagent(task: str) -> str:
    """
    启动一个 Subagent，在全新 context 中执行 task，返回结果摘要。
    Master 的 context 完全不受 Subagent 工具调用的污染。
    """
    print(f"\n  \033[35m[Subagent 启动] 任务：{task}\033[0m")

    # Subagent 有自己的独立 messages，和 Master 完全隔离
    messages = [
        {"role": "system",  "content": SUBAGENT_SYSTEM},
        {"role": "user",    "content": task},
    ]

    # Subagent 的推理循环（和普通 agent 一样，但 context 是全新的）
    while True:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": msg.tool_calls,
        })

        if not msg.tool_calls:
            # 没有工具调用 → Subagent 给出了最终결론
            result = msg.content
            print(f"  \033[35m[Subagent 完成] {result[:100]}...\033[0m\n")
            return result

        # 执行工具
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            print(f"  \033[33m  ▶ subagent 调用 {name}({args})\033[0m")
            result = TOOL_EXECUTOR[name](args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })


# ─────────────────────────────────────────────────────────────────────────────
# Master Agent：管理对话，决定是自己回答还是派发给 Subagent
# ─────────────────────────────────────────────────────────────────────────────

MASTER_SYSTEM = """你是一个智能任务调度助手。

对于用户的请求，你需要判断：
1. 简单问题（聊天、解释概念）→ 直接回答
2. 需要大量文件操作/命令执行的复杂任务 → 调用 dispatch_subagent 工具派发给 Subagent

dispatch_subagent 会在独立环境中执行任务，只返回结论摘要给你。"""

# Master 只有一个工具：派发 Subagent
DISPATCH_TOOL = {
    "type": "function",
    "function": {
        "name": "dispatch_subagent",
        "description": "派发一个复杂任务给 Subagent 独立执行，返回执行结果摘要。适合需要多步工具操作的任务。",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "交给 Subagent 执行的具体任务描述",
                },
            },
            "required": ["task"],
        },
    },
}


def run_master_turn(messages: list[dict]) -> list[dict]:
    """Master Agent 推理一轮。"""
    while True:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=[DISPATCH_TOOL],
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": msg.tool_calls,
        })

        if not msg.tool_calls:
            print(f"AI：{msg.content}\n")
            break

        # Master 调用了 dispatch_subagent
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            task = args["task"]

            # 关键：Subagent 在独立 context 运行，大量工具细节不会出现在 Master 的 messages 里
            subagent_result = run_subagent(task)

            # Master 只收到一句话的摘要，context 保持干净
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": subagent_result,
            })

    return messages


def main():
    print("\033[36m")
    print("╔══════════════════════════════════════╗")
    print("║     Multi-Agent 示例                 ║")
    print("║  Master → Subagent（上下文隔离）      ║")
    print("║  输入 quit 退出                       ║")
    print("╚══════════════════════════════════════╝")
    print("\033[0m")
    print("试试：'帮我创建一个 test.py 并运行它'（会派发给 Subagent）")
    print("或者：'什么是 Multi-Agent'（Master 直接回答）\n")

    messages = [{"role": "system", "content": MASTER_SYSTEM}]

    while True:
        try:
            user_input = input("\033[32m你：\033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        messages.append({"role": "user", "content": user_input})
        messages = run_master_turn(messages)

        # 打印 Master context 大小，直观感受上下文隔离效果
        print(f"\033[90m[Master context 当前 {len(messages)} 条消息]\033[0m\n")


if __name__ == "__main__":
    main()
