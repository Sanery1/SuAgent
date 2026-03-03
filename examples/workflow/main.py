"""
Workflow 示例：Query → Search → Summarize 三步流水线
======================================================

演示目标：
    用 Node/Flow 构建一条线性"流水线"（Pipeline）。
    每个节点只做一件事（单一职责），中间结果通过 payload 向下传递。

流程图（线性，无循环，无分支）：
    QueryNode
        │ "search"（把查询字符串透传）
        ▼
    SearchNode
        │ "summarize"（把搜索结果标题拼接后传下去）
        ▼
    SummarizeNode
        │ "default"（无后继 → Flow 结束，返回摘要文本）

各节点职责：
    QueryNode     : 接收原始查询，透传（可在此做查询改写、意图识别等扩展）
    SearchNode    : 调 DuckDuckGo 获取最新结果，提取标题拼成文本
    SummarizeNode : 用 LLM 把标题要点压缩成一句话中文摘要

Workflow vs Agent 的本质区别：
    Workflow = 提前确定执行顺序，节点间逻辑由开发者写死（确定性）
    Agent    = 执行路径由 LLM 的 tool_calls 决定（动态决策）
"""

from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import call_llm
from core.node import Node, Flow
# 直接导入底层搜索函数，绕过 Tool/ToolExecutor 封装（在 Workflow 节点内直接调用更简洁）
from tools.builtins.search import search as search_ddgs


class QueryNode(Node):
    """
    查询入口节点：接收初始 payload（查询字符串），原样传给下一个节点。

    当前实现是透传，在更复杂的场景可以在这里扩展：
        - 查询改写（把口语问题改写成搜索关键词）
        - 多语言翻译
        - 意图分类（决定是搜索还是查本地文件）
    """

    def exec(self, payload: Any) -> Tuple[str, Any]:
        # "search" 动作 → 跳到 SearchNode；把查询字符串作为 payload 传下去
        return "search", str(payload)


class SearchNode(Node):
    """
    搜索节点：调用 DuckDuckGo，提取结果标题并拼成字符串传给下一节点。

    只取标题而非全文的原因：减少传给 LLM 的 token 数，同时保留关键信息。
    当 title 为空时回退取 body 字段，确保有内容可用。

    输出示例：
        "Python asyncio tutorial | Understanding async-await | Asyncio best practices..."
    """

    def exec(self, payload: Any) -> Tuple[str, Any]:
        # 搜索最多 3 条，控制 token 消耗
        results = search_ddgs(str(payload), max_results=3)
        # 提取标题（title 优先，无则取 body 摘要）
        titles = [r.get("title") or r.get("body") or "" for r in results]
        # 过滤空字符串后拼接
        return "summarize", " | ".join(t for t in titles if t)


class SummarizeNode(Node):
    """
    摘要节点：用 LLM 把搜索结果要点压缩成一句话摘要。

    接收 SearchNode 传来的标题拼接字符串，构造简单 prompt 让 LLM 提炼。
    使用 call_llm 的简单模式（传字符串→返字符串），无需工具调用。
    """

    def exec(self, payload: Any) -> Tuple[str, Any]:
        # 简单模式：传字符串 → 返回字符串
        text = call_llm(f"基于以下要点写一句话摘要：{payload}")
        # "default" 且 SummarizeNode 无后继节点 → Flow.run() 结束并返回 text
        return "default", text


def main() -> None:
    query = QueryNode()
    search = SearchNode()
    summarize = SummarizeNode()

    # 声明线性流程（运算符重载）
    query - "search" >> search
    search - "summarize" >> summarize
    # summarize 没有配置后继节点，Flow.run() 返回时 payload 即为最终摘要

    flow = Flow(query)
    # 把查询字符串作为初始 payload 传入，启动整个流水线
    _, result = flow.run("python asyncio best practices")
    print("Workflow 输出：", result)


if __name__ == "__main__":
    main()
