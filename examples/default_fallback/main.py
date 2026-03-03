"""
默认回退示例：未知 action 时自动降级到 "default" 边
====================================================

演示目标：
    展示 Flow/Workflow 的容错机制：
    当节点返回一个在 successors 里找不到的 action 时，
    会自动回退到 "default" 边（如果存在的话）。

流程图：
    Router ──"unknown_action"──► [找不到对应边]
                                      │
                                      ▼ 回退到 "default"
                                 FallbackNode（打印结果）

工作原理：
    1. Router.execute() 返回 "unknown_action"
    2. Workflow 在 router.successors 里查找 "unknown_action" → 找不到
    3. 自动尝试 successors["default"] → 找到 FallbackNode
    4. 执行 FallbackNode

应用场景：
    - LLM 偶尔返回超出预期的动作名时，用 default 做兜底处理
    - 类似 switch-case 的 default 分支，处理未预料的情况

注意：Node.execute(shared) → str 是旧版 API 风格，
      当前版本已改为 Node.exec(payload) → (action, payload)。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Workflow, Node


class Router(Node):
    """
    路由节点：故意返回一个不存在的动作名，用来触发 default 回退。

    实际场景中，这可能是 LLM 返回了未预期的工具名或动作名。
    """

    def execute(self, shared: dict) -> str | None:
        # 记录尝试的路由值（便于调试）
        shared["route_try"] = "unknown_action"
        return "unknown_action"     # successors 里没有这个 key → 会触发 default 回退


class FallbackNode(Node):
    """
    回退节点：处理未匹配到动作名时的兜底逻辑。

    通过 add_successor(fallback, "default") 注册为 Router 的 default 后继。
    """

    def execute(self, shared: dict) -> str | None:
        shared["result"] = "命中 default 回退"
        print(shared["result"])
        # 返回 None 等价于 "default"
        # 此节点没有注册任何后继 → Workflow 在此结束
        return None


if __name__ == "__main__":
    router = Router()
    fallback = FallbackNode()

    # 只注册 "default" 边，没有注册 "unknown_action" 边
    # 当 router 返回 "unknown_action" 找不到时，自动使用 "default" 边
    router.add_successor(fallback, "default")

    workflow = Workflow(start=router)
    final_shared = workflow.run()
    print("final shared:", final_shared)    # {"route_try": "unknown_action", "result": "命中 default 回退"}
