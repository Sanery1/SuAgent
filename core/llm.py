"""
LLM 调用核心模块
================

提供统一入口 call_llm()，同时兼容两种使用模式：

  模式 1 —— 简单 prompt（旧式，适合单次问答）：
      response: str = call_llm("用一句话解释什么是 Agent")

  模式 2 —— 多轮消息 / 工具调用（适合 Agent 对话）：
      result: dict = call_llm(
          messages=history,
          tools=[...],
          system_prompt="你是一个编程助手"
      )
      # result 格式：{"role": "assistant", "content": "...", "tool_calls": [...]}

环境变量（需在 .env 中配置）：
    OPENAI_API_KEY  : API 密钥
    OPENAI_BASE_URL : 接口地址（支持任意 OpenAI 兼容接口）
    LLM_MODEL       : 默认模型名称
"""

from __future__ import annotations

import os
import sys
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

# Windows 下 sys.stdout 默认是 GBK 编码，强制改成 UTF-8 避免中文乱码
sys.stdout.reconfigure(encoding="utf-8")
# 从项目根目录的 .env 文件加载环境变量（OPENAI_API_KEY 等）
load_dotenv()

# ── 全局 OpenAI 客户端 ────────────────────────────────────────────────────────
# 模块加载时创建一次，后续所有调用复用，避免重复初始化连接池
_client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL"),  # 支持 Kimi / Zhipu / DeepSeek 等兼容接口
)

# 默认模型：从环境变量读取，未设置时回退到 moonshot-v1-8k
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

    参数二选一：
        prompt   : 字符串提示词（简单模式）→ 函数直接返回字符串
        messages : OpenAI 格式的消息列表（对话模式）→ 返回 assistant message 字典

    可选参数：
        tools        : OpenAI function calling 工具列表（开启后 LLM 可以调用工具）
        system_prompt: 系统提示词，会被插到消息列表最前面
        model        : 覆盖默认模型

    返回值：
        - 简单模式（只传 prompt，无 tools/system_prompt）：返回 str
        - 对话模式（传了 messages 或 tools 或 system_prompt）：返回 dict，格式：
            {
                "role": "assistant",
                "content": "...",           # 文本回复（若只调工具可能为空字符串）
                "tool_calls": [...]         # 仅当 LLM 决定调用工具时才有此字段
            }
    """
    # ── 构建消息列表 ──────────────────────────────────────────────────────────
    if messages is not None:
        msgs = list(messages)           # 复制，避免修改调用方的原始列表
    elif prompt is not None:
        # 把普通字符串包装成 OpenAI 消息格式
        msgs = [{"role": "user", "content": prompt}]
    else:
        raise ValueError("Either prompt or messages must be provided")

    # system_prompt 插到消息列表最前面（system 角色有最高指令优先级）
    if system_prompt:
        msgs = [{"role": "system", "content": system_prompt}, *msgs]

    # ── 构建请求参数 ──────────────────────────────────────────────────────────
    kwargs: dict[str, Any] = {"model": model, "messages": msgs}
    if tools:
        kwargs["tools"] = tools
        # "auto"：让 LLM 自己决定是否调用工具（也可设为 "required" 强制调用）
        kwargs["tool_choice"] = "auto"

    # ── 发送请求并解析响应 ────────────────────────────────────────────────────
    response = _client.chat.completions.create(**kwargs)
    message = response.choices[0].message  # 取第一个候选回复

    # 简单 prompt 模式：直接返回字符串，保持与旧版用法兼容
    if messages is None and tools is None and system_prompt is None:
        return message.content or ""

    # 对话模式：封装成字典，后续可直接 append 进 messages 列表
    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.content or "",
    }
    if message.tool_calls:
        # model_dump() 把 Pydantic 对象转为普通字典，方便序列化和传参
        result["tool_calls"] = [tc.model_dump() for tc in message.tool_calls]

    return result


def call_llm_stream(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> str:
    """
    流式 LLM 调用：逐 token 打印到终端，同时返回完整文本。

    与 call_llm() 的区别：
        - 开启 stream=True，LLM 生成一个 token 就立刻推送过来
        - 用户可以实时看到输出，而不是等全部生成完再显示
        - 不支持工具调用（工具调用需要完整 JSON，流式时需特殊处理，见 agent/loop.py）

    适用场景：agent/main.py 中纯文本的最终回复展示。
    工具调用场景请使用 agent/loop.py 中的 _stream_response()。
    """
    stream = _client.chat.completions.create(
        model=model, messages=messages, stream=True
    )
    full = ""
    for chunk in stream:
        # 每个 chunk.choices[0].delta.content 是一小段新生成的文本（或 None）
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)    # 实时打印，不换行
        full += delta                        # 累积完整文本
    print()     # 流结束后换行
    return full


if __name__ == "__main__":
    # 快速验证 API 连通性：直接运行 python core/llm.py
    print("Basic:", call_llm("用一句话解释什么是 Agent。"))
