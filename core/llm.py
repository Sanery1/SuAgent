from __future__ import annotations

import os
import sys
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

_client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL"),
)

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "moonshot-v1-8k")


def call_llm(
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    system_prompt: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str | dict[str, Any]:
    """
    统一 LLM 调用入口。
    - 只传 prompt：返回字符串（兼容旧用法）
    - 传 messages 或 tools：返回 assistant message 字典
    """
    if messages is not None:
        msgs = list(messages)
    elif prompt is not None:
        msgs = [{"role": "user", "content": prompt}]
    else:
        raise ValueError("Either prompt or messages must be provided")

    if system_prompt:
        msgs = [{"role": "system", "content": system_prompt}, *msgs]

    kwargs: dict[str, Any] = {"model": model, "messages": msgs}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = _client.chat.completions.create(**kwargs)
    message = response.choices[0].message

    # 简单 prompt 模式直接返回字符串
    if messages is None and tools is None and system_prompt is None:
        return message.content or ""

    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.content or "",
    }
    if message.tool_calls:
        result["tool_calls"] = [tc.model_dump() for tc in message.tool_calls]

    return result


def call_llm_stream(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> str:
    """流式调用，逐 token 打印，返回完整文本。"""
    stream = _client.chat.completions.create(
        model=model, messages=messages, stream=True
    )
    full = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
        full += delta
    print()
    return full


if __name__ == "__main__":
    print("Basic:", call_llm("用一句话解释什么是 Agent。"))
