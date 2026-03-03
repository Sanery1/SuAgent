"""
Multi-Agent 示例：Master Agent + Subagent（上下文隔离）
=======================================================

演示目标：
    当任务需要大量工具调用时，Master 把任务委托给 Subagent 独立执行。
    Subagent 完成后只把"结论摘要"返回给 Master，不让工具调用细节污染 Master 的 context。

为什么需要 Multi-Agent？
    假设用户让 Agent "在所有 Python 文件中找 TODO 注释并汇总"：

    单 Agent 方案：
        grep → read → read → read → ... → 汇总
        全部工具调用都堆在同一个 messages 列表里
        → context 越来越长 → token 费用高、LLM 注意力分散

    Multi-Agent 方案：
        Master 判断：这是复杂任务 → 派发给 Subagent
        Subagent：独立 context（全新 messages），执行 grep/read/... → 返回一句话摘要
        Master context：只多了一条 tool 消息（摘要）
        → Master context 保持干净，成本可控

架构图：
    ┌─────────────────────────────────────────┐
    │           Master Agent                  │
    │  系统提示：智能任务调度助手              │
    │  唯一工具：dispatch_subagent            │
    └──────────────────┬──────────────────────┘
                       │ 遇到复杂任务 → 调用 dispatch_subagent(task)
                       ▼
    ┌─────────────────────────────────────────┐
    │           Subagent（独立实例）           │
    │  全新 messages，与 Master 完全隔离       │
    │  完整工具集：bash/read/write/edit/...   │
    │  完成后：返回一段结论摘要                │
    └─────────────────────────────────────────┘

注意：此文件使用了旧版 tools 接口（ALL_TOOLS/TOOL_EXECUTOR），
      仅供理解 Multi-Agent 概念使用，接口与当前 tools/executor.py 略有不同。
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
    启动 Subagent，在全新 context 中执行 task，仅返回结果摘要。

    上下文隔离的关键：
        - messages 是局部变量，与 Master 的 messages 完全独立
        - Subagent 执行的所有工具调用只存在于 Subagent 的局部 messages 里
        - 只有最终的文本摘要会被返回给 Master

    Args:
        task: Master 下达的具体任务描述（自然语言）

    Returns:
        Subagent 完成任务后的结论摘要（普通字符串，通常一两句话）
    """
    print(f"\n  \033[35m[Subagent 启动] 任务：{task}\033[0m")

    # ★ 独立的 messages 列表 —— 这就是上下文隔离的实现
    messages = [
        {"role": "system",  "content": SUBAGENT_SYSTEM},
        {"role": "user",    "content": task},
    ]

    # Subagent 内部的 Agent 推理循环（与普通 Agent 完全相同的逻辑）
    while True:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=ALL_TOOLS,       # Subagent 拥有完整工具集
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": msg.tool_calls,
        })

        if not msg.tool_calls:
            # LLM 不再调工具 → 给出最终结论摘要 → 退出循环并返回
            result = msg.content
            print(f"  \033[35m[Subagent 完成] {result[:100]}...\033[0m\n")
            return result   # 这是唯一"泄露"给 Master 的信息

        # 执行工具，把结果附回 Subagent 的局部 messages
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
# Master Agent：管理对话，决定自己回答还是派发给 Subagent
# ─────────────────────────────────────────────────────────────────────────────

MASTER_SYSTEM = """你是一个智能任务调度助手。

对于用户的请求，你需要判断：
1. 简单问题（聊天、解释概念）→ 直接回答
2. 需要大量文件操作/命令执行的复杂任务 → 调用 dispatch_subagent 工具派发给 Subagent

dispatch_subagent 会在独立环境中执行任务，只返回结论摘要给你。"""

# Master 只暴露一个工具：dispatch_subagent
# 限制 Master 工具集的好处：Master 无法直接操作文件，
# 复杂操作一定经过 Subagent 隔离，保证 Master context 干净
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
    """
    Master Agent 执行一轮对话（可能包含多次工具调用）。

    推理循环：
        1. LLM 判断：简单问题直接回答，复杂任务调用 dispatch_subagent
        2. 若调用了 dispatch_subagent → 启动 run_subagent() → 只把摘要放回 messages
        3. 若无工具调用 → 打印回复，本轮结束

    上下文隔离效果：
        Subagent 做了 10 次工具调用，但 Master 的 messages 只多了 1 条 tool 消息
        （内容是简短摘要），而不是 10 条详细工具调用记录。
    """
    while True:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=[DISPATCH_TOOL],     # Master 只能看到这一个工具
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": msg.tool_calls,
        })

        if not msg.tool_calls:
            # Master 直接给出回答（简单问题）
            print(f"AI：{msg.content}\n")
            break

        # Master 决定派发 Subagent 处理复杂任务
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            task = args["task"]

            # ★ 核心隔离点：Subagent 在独立 context 运行
            #   工具调用细节不会出现在 Master messages 里
            subagent_result = run_subagent(task)

            # Master 只收到一句摘要，保持 context 精简
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": subagent_result,   # ← 只有结论，没有过程
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

    # Master 的全局 messages（系统提示词 + 所有对话历史）
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

        # 打印 Master context 大小，直观感受隔离效果（数字增长应该很缓慢）
        print(f"\033[90m[Master context 当前 {len(messages)} 条消息]\033[0m\n")


if __name__ == "__main__":
    main()
