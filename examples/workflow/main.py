"""Workflow 示例：Query -> Search -> Summarize"""
from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import call_llm
from core.node import Node, Flow
from tools.builtins.search import search as search_ddgs


class QueryNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        return "search", str(payload)


class SearchNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        results = search_ddgs(str(payload), max_results=3)
        titles = [r.get("title") or r.get("body") or "" for r in results]
        return "summarize", " | ".join(t for t in titles if t)


class SummarizeNode(Node):
    def exec(self, payload: Any) -> Tuple[str, Any]:
        text = call_llm(f"基于以下要点写一句话摘要：{payload}")
        return "default", text


def main() -> None:
    query = QueryNode()
    search = SearchNode()
    summarize = SummarizeNode()

    query - "search" >> search
    search - "summarize" >> summarize

    flow = Flow(query)
    _, result = flow.run("python asyncio best practices")
    print("Workflow 输出：", result)


if __name__ == "__main__":
    main()
