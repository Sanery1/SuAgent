"""
Agent 示例：带工具的对话（ChatNode -tool_call-> ToolCallNode -chat-> ChatNode）
==============================================================================

演示目标：
    在聊天机器人基础上加入工具调用能力，
    LLM 可以主动决定"调用工具获取信息"还是"直接回答"，形成两条执行路径。

流程图（含循环）：
    （用户输入）
         │
         ▼
     ChatNode ──"tool_call"──► ToolCallNode ──"chat"──┐
         ▲                                             │
         └─────────────────────────────────────────────┘
         │
         │ "output"（LLM 不需要工具，直接给出回答）
         ▼
    OutputNode  ← 打印最终回复

为什么要形成循环（ChatNode ↔ ToolCallNode）？
    LLM 一次可能连续调用多个工具：
        第1轮：LLM → grep 找文件 → 把结果送回 LLM
        第2轮：LLM → read 读文件 → 把结果送回 LLM
        第3轮：LLM 基于两次结果给出最终回答 → 跳出循环到 OutputNode
    循环让 Agent 能处理任意深度的工具调用链，直到 LLM 决定停止。

ChatNode 的路由逻辑：
    - assistant_msg 含 "tool_calls"  →  "tool_call"（去执行工具）
    - assistant_msg 无 "tool_calls"  →  "output"（直接输出）
"""

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
    """
    对话节点：带工具列表调用 LLM，根据是否有 tool_calls 决定下一步。

    与 chatbot/main.py 的 ChatNode 区别：
        - 使用 call_llm(messages=..., tools=...) 的对话模式（返回 dict，不是字符串）
        - 需要把 tools 注册表传给 LLM，让它知道可以调用哪些工具
        - 根据 LLM 的响应类型（含/不含 tool_calls）返回不同的动作
    """

    def exec(self, payload: Any) -> Tuple[str, Any]:
        messages = shared.get("messages", [])
        tools = shared.get("tools", [])  # 预先转换好的 OpenAI Function Calling 格式

        # 调用 LLM：传入对话历史 + 工具列表 + 系统提示词
        # 返回的 assistant_msg 是字典，可能含 "tool_calls" 字段
        assistant_msg = call_llm(messages=messages, tools=tools, system_prompt=SYSTEM_PROMPT)

        # 先把 assistant 回复存入历史
        # 注意：OpenAI 协议要求 tool 消息之前必须有对应的 assistant 消息
        messages.append(assistant_msg)
        shared["messages"] = messages

        if assistant_msg.get("tool_calls"):
            # LLM 决定调用工具 → 把整个 assistant_msg 传给 ToolCallNode（它需要从中解析工具调用）
            return "tool_call", assistant_msg
        # LLM 直接给出文本回答 → 传给 OutputNode 打印
        return "output", assistant_msg


class ToolCallNode(Node):
    """
    工具执行节点：解析并执行 LLM 请求的所有工具调用，把结果追加到消息历史。

    执行后返回 "chat" → 触发 ChatNode 再次调 LLM：
        - LLM 看到工具结果后可能继续调工具（循环继续）
        - 也可能给出最终文本回答（跳出循环到 OutputNode）
    """

    def exec(self, payload: Any) -> Tuple[str, Any]:
        messages = shared.get("messages", [])
        executor: ToolExecutor = shared.get("tool_executor")

        # 从 assistant_msg 中解析 tool_calls 字段 → List[ToolCall]
        tool_calls = executor.parse_tool_calls(payload)
        # 批量执行所有工具 → List[ToolResult]
        results = executor.execute_all(tool_calls)

        for tc, result in zip(tool_calls, results):
            print(f"  [Tool] {tc.name}({tc.arguments})")
            print(f"  [Result] {result.content[:150]}...")
            # 把工具结果以 role="tool" 格式追加，LLM 下一轮推理时能看到执行结果
            messages.append(result.to_message())

        shared["messages"] = messages
        # 返回 "chat" → 回到 ChatNode，让 LLM 基于工具结果继续决策
        return "chat", None


class OutputNode(Node):
    """输出节点：打印 LLM 的最终文本回复（无工具调用的那一轮）。"""

    def exec(self, payload: Any) -> Tuple[str, Any]:
        # payload 是 assistant_msg 字典，content 字段是文本回复
        print(f"\nAssistant: {payload.get('content', '')}\n")
        return "default", None


def main() -> None:
    shared.clear()
    shared["messages"] = []
    # 预先把工具转换为 OpenAI Function Calling 所需的 JSON Schema 格式
    shared["tools"] = [t.to_llm_format() for t in get_tools()]
    # 预初始化执行器（建立 name→Tool 映射，后续按名查找工具）
    shared["tool_executor"] = ToolExecutor()

    chat = ChatNode()
    tool_call = ToolCallNode()
    output = OutputNode()

    # 声明循环流程：
    #   chat --"tool_call"--> tool_call --"chat"--> chat  (工具调用循环)
    #   chat --"output"-----> output                      (最终输出)
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
        # 每次对话从 ChatNode 出发，Flow 自动沿流程图执行直到无后继节点
        Flow(chat).run(None)


if __name__ == "__main__":
    main()
