"""
默认回退示例：未知 action 时走 default

流程：Router --(default)--> FallbackNode
说明：Router 返回 'unknown_action'，由于没有同名边，会自动回退到 default。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Workflow, Node


class Router(Node):
    def execute(self, shared: dict) -> str | None:
        shared["route_try"] = "unknown_action"
        return "unknown_action"


class FallbackNode(Node):
    def execute(self, shared: dict) -> str | None:
        shared["result"] = "命中 default 回退"
        print(shared["result"])
        return None  # 继续走 default；但此节点无后继，Workflow 结束


if __name__ == "__main__":
    router = Router()
    fallback = FallbackNode()

    router.add_successor(fallback, "default")

    workflow = Workflow(start=router)
    final_shared = workflow.run()
    print("final shared:", final_shared)
