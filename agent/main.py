"""
SuAgent - 极简 Coding Agent
用法：python agent/main.py

功能：
  - 多轮对话（短期 Context）
  - 历史自动压缩（长期 Context）
  - 工具：bash / read_file / write_file / edit_file
  - 流式输出
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.prompts import SYSTEM_PROMPT
from agent.loop import run_agent_turn
from core.llm import call_llm

# ── Context / Memory 配置 ─────────────────────────────────────────────────────
SHORT_TERM_LIMIT = 20   # 短期 Context：保留最近 20 条完整消息
                         # 超出后触发长期 Context 压缩


def compress_history(messages: list[dict]) -> list[dict]:
    """
    长期 Context 压缩（Step 6）：
      - 短期 Context = 最近 SHORT_TERM_LIMIT 条，原样保留
      - 长期 Context = 更早的对话，用 LLM 总结成一段话
      - 最终 = system prompt + 长期摘要 + 短期 Context
    """
    system_msgs = [m for m in messages if m["role"] == "system"]
    non_system  = [m for m in messages if m["role"] != "system"]

    if len(non_system) <= SHORT_TERM_LIMIT:
        return messages  # 还没超出，不需要压缩

    to_compress = non_system[:-SHORT_TERM_LIMIT]   # 需要压缩的旧消息
    recent      = non_system[-SHORT_TERM_LIMIT:]   # 保留的短期消息

    print("\n\033[90m[对话历史过长，正在压缩...]\033[0m\n")

    # 用 LLM 把旧消息总结成一段话
    summary = call_llm([
        {"role": "system", "content": "请简洁总结以下对话的关键内容（操作过的文件、解决的问题、重要结论），供后续参考："},
        {"role": "user",   "content": "\n".join(
            f"{m['role']}: {m.get('content') or ''}" for m in to_compress
        )},
    ])

    # 把摘要作为一条 system 消息注入
    summary_msg = {"role": "system", "content": f"[早期对话摘要]\n{summary}"}

    return system_msgs + [summary_msg] + recent


def main():
    print("\033[36m")
    print("╔══════════════════════════════════╗")
    print("║        SuAgent  Coding Agent     ║")
    print("║  工具: bash / read / write / edit ║")
    print("║  输入 quit 退出，clear 清空历史   ║")
    print("╚══════════════════════════════════╝")
    print("\033[0m")

    cwd = os.getcwd()
    print(f"工作目录：{cwd}\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\n\n当前工作目录：{cwd}"}]

    while True:
        try:
            user_input = input("\033[32m你：\033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        if user_input.lower() == "clear":
            messages = [messages[0]]  # 只保留 system prompt
            print("历史已清空\n")
            continue

        # 加入用户消息
        messages.append({"role": "user", "content": user_input})

        # 执行一轮 Agent 推理（含工具调用）
        print("\n\033[34mAI：\033[0m", end="")
        messages = run_agent_turn(messages)

        # 压缩超长历史（长期 Context）
        messages = compress_history(messages)
        print()


if __name__ == "__main__":
    main()
