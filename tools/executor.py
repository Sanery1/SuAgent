"""
工具执行引擎
============

本模块负责"解析 LLM 返回的工具调用请求 → 执行对应工具 → 封装结果返回给 LLM"
这一完整闭环。定义了三个数据结构：

  ToolCall   —— LLM 想调用的工具（名称 + 参数）
  ToolResult —— 工具执行完的结果（内容 + 是否出错）
  ToolExecutor —— 管理所有工具、驱动整个执行流程

完整数据流：
    LLM 返回的 assistant message
        │
        ▼ parse_tool_calls()
    List[ToolCall]          ← 每个 ToolCall 对应一次工具调用请求
        │
        ▼ execute() / execute_all()
    List[ToolResult]        ← 每个 ToolResult 对应一个执行结果
        │
        ▼ to_message()
    List[dict]              ← role="tool" 的消息，append 到 messages 后再送给 LLM
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
from tools.builtins import get_builtin_tools


@dataclass(slots=True)
class ToolCall:
    """
    LLM 发起的单次工具调用请求。

    来源：LLM 返回的 assistant message 中的 tool_calls 字段，格式如下：
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "read",
                "arguments": '{"path": "src/main.py", "limit": 50}'
            }
        }

    Attributes:
        id        : OpenAI 分配的唯一 ID，后续 ToolResult 需要引用此 ID
                    以便 LLM 把结果与对应的工具调用匹配起来
        name      : 工具名称（对应 Tool.name，如 "read"、"bash"）
        arguments : 解析后的参数字典（原始是 JSON 字符串，已在 from_openai_item 中解析）

    slots=True 的作用：禁止动态添加属性，减少内存占用，访问略快。
    """

    id: str
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_openai_item(cls, item: dict[str, Any]) -> "ToolCall":
        """
        从 OpenAI 格式的单个 tool_call 字典构造 ToolCall 实例。

        Args:
            item: tool_calls 列表中的一个元素（字典格式）

        处理细节：
            - arguments 字段在 OpenAI 协议中是 JSON 字符串（不是字典），需要 json.loads()
            - 容错：若解析失败或结果不是字典，回退到空字典 {}，避免崩溃
        """
        function = item.get("function", {})
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            # OpenAI 把参数序列化为字符串，需要反序列化
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}          # 解析失败时降级为空参数，让后续执行给出错误提示
        if not isinstance(arguments, dict):
            arguments = {}              # 类型不对时也降级
        return cls(
            id=item.get("id", ""),
            name=function.get("name", ""),
            arguments=arguments,
        )


@dataclass(slots=True)
class ToolResult:
    """
    单次工具调用的执行结果。

    Attributes:
        tool_call_id : 对应 ToolCall.id，LLM 用此 ID 把结果与请求关联起来
        content      : 工具执行的输出内容（字符串，已序列化）
        is_error     : True 表示工具执行失败（工具找不到 / 运行时异常等）
    """

    tool_call_id: str
    content: str
    is_error: bool = False

    def to_message(self) -> dict[str, str]:
        """
        把执行结果封装为 OpenAI role="tool" 的消息字典。

        格式：
            {"role": "tool", "tool_call_id": "call_abc123", "content": "文件内容..."}

        这个字典需要 append 到 messages 列表后再发给 LLM，
        LLM 看到这条消息后才知道工具执行结果是什么，并据此生成最终回复。
        """
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


class ToolExecutor:
    """
    工具执行器：维护工具注册表，驱动"解析 → 执行 → 返回结果"的完整流程。

    初始化时自动加载所有内置工具，并建立 name → Tool 的映射索引，
    使得按名查找的时间复杂度为 O(1)。
    """

    def __init__(self) -> None:
        # 加载全部内置工具
        self.tools = get_builtin_tools()
        # 建立 name → Tool 的映射，执行时按名快速查找
        self.tool_map = {t.name: t for t in self.tools}

    def parse_tool_calls(self, assistant_message: dict[str, Any]) -> list[ToolCall]:
        """
        从 LLM 返回的 assistant message 中解析出所有工具调用请求。

        Args:
            assistant_message: call_llm() 返回的字典，可能包含 "tool_calls" 字段

        Returns:
            ToolCall 列表（LLM 没有调用工具时返回空列表）

        说明：
            LLM 可以在一次响应中同时请求多个工具调用（parallel tool calls），
            因此 tool_calls 是列表，这里统一解析为 ToolCall 列表。
        """
        openai_calls = assistant_message.get("tool_calls")
        if isinstance(openai_calls, list):
            return [ToolCall.from_openai_item(item) for item in openai_calls]
        return []

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        执行单个工具调用并返回结果。

        执行策略：
            1. 在 tool_map 中查找工具，找不到则返回错误结果
            2. 调用 tool.execute(**arguments)，捕获所有异常
            3. 如果返回值是字典，JSON 序列化为字符串（LLM 只能接收字符串内容）
            4. 其他类型直接 str() 转换

        Args:
            tool_call: 要执行的工具调用请求

        Returns:
            ToolResult（无论成功或失败，始终返回有效对象，不抛异常）
        """
        tool = self.tool_map.get(tool_call.name)
        if not tool:
            # 工具不存在：返回错误结果，让 LLM 知道调用失败并可自行处理
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Tool '{tool_call.name}' not found",
                is_error=True,
            )
        try:
            raw = tool.execute(**tool_call.arguments)
        except Exception as exc:
            # 运行时异常：同样封装为错误结果，而不是直接崩溃
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: {exc}",
                is_error=True,
            )
        # 序列化：字典 → JSON 字符串（确保 LLM 收到可解析的结构化文本）
        content = json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else str(raw)
        return ToolResult(tool_call_id=tool_call.id, content=content)

    def execute_all(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """
        批量执行多个工具调用，顺序执行，返回同序的结果列表。

        Args:
            tool_calls: parse_tool_calls() 返回的列表

        Returns:
            与 tool_calls 等长、一一对应的 ToolResult 列表
        """
        return [self.execute(tc) for tc in tool_calls]
