"""
Agent 主循环（适配新 tools 架构）

使用 ToolExecutor 解析 + 执行工具调用，流式输出 LLM 响应。
"""

from __future__ import annotations
import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.llm import _client, DEFAULT_MODEL
from tools import get_tools, ToolExecutor

_executor = ToolExecutor()
_tools_schema = [t.to_llm_format() for t in get_tools()]


def _stream_response(messages: list[dict]) -> tuple[str, list[dict]]:
    """
    流式调用 LLM（带工具支持）。
    返回 (full_text, tool_calls_list)
    """
    stream = _client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        tools=_tools_schema,
        tool_choice="auto",
        stream=True,
    )

    full_text = ""
    tool_calls_raw: dict[int, dict] = {}

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            print(delta.content, end="", flush=True)
            full_text += delta.content
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_raw:
                    tool_calls_raw[idx] = {"id": "", "name": "", "arguments": ""}
                if tc.id:                        tool_calls_raw[idx]["id"] = tc.id
                if tc.function.name:             tool_calls_raw[idx]["name"] = tc.function.name
                if tc.function.arguments:        tool_calls_raw[idx]["arguments"] += tc.function.arguments

    if full_text:
        print()

    tool_calls = [tool_calls_raw[i] for i in sorted(tool_calls_raw)]
    return full_text, tool_calls


def run_agent_turn(messages: list[dict]) -> list[dict]:
    """一轮推理：LLM 可能连续调用多个工具，直到给出纯文本回复。"""
    while True:
        full_text, tool_calls = _stream_response(messages)

        messages.append({
            "role": "assistant",
            "content": full_text or None,
            "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls
            ] if tool_calls else None,
        })

        if not tool_calls:
            break

        for tc in tool_calls:
            name = tc["name"]
            try:
                args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                args = {}

            print(f"\n\033[33m▶ {name}({json.dumps(args, ensure_ascii=False)})\033[0m")

            # 用 ToolExecutor 执行
            from tools.executor import ToolCall as TC
            result = _executor.execute(TC(id=tc["id"], name=name, arguments=args))
            preview = result.content[:300] + ("..." if len(result.content) > 300 else "")
            print(f"\033[90m{preview}\033[0m")

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result.content,
            })

    return messages
