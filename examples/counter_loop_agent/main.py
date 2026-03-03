"""
循环 Agent 示例：节点自指回边，形成 while 循环
================================================

演示目标：
    展示如何让 Node 指向自身，构成"执行循环"。
    这是 Agent 持续工作直到满足条件的核心机制。

流程图：
    Tick ──"default"──► Tick（指向自身，计数未达上限时循环）
         └──"done"────► Stop（计数达到上限时退出循环）
                            │
                            └──"end"──► [Agent 停止]

循环原理：
    Tick.execute() 返回 "default" → successors["default"] = tick（自身）→ 继续执行 Tick
    达到 limit 后返回 "done" → successors["done"] = stop → 执行 Stop → 返回 "end" → Agent 终止

这种模式在 AI Agent 中极为常见：
    LLM 推理 → 工具调用 → LLM 推理 → 工具调用 → ... → 给出最终回答 → "end"
    只要 LLM 还在调工具，Agent 就一直循环；不调工具了就终止。

注意：Node.execute(shared) → str 是旧版 API 风格，
      当前版本已改为 Node.exec(payload) → (action, payload)。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Agent, Node


class Tick(Node):
    """
    计数节点：每次执行将 shared["count"] 加 1，达到上限则退出循环。

    返回 "default" → 回到自己（循环继续）
    返回 "done"    → 跳到 Stop（循环结束）
    """

    def execute(self, shared: dict) -> str | None:
        # 每次执行 count +1（第一次 count 不存在，默认从 0 开始）
        shared["count"] = shared.get("count", 0) + 1
        print(f"tick -> count={shared['count']}")

        limit = shared.get("limit", 3)
        if shared["count"] >= limit:
            return "done"       # 达到上限 → 退出循环
        return "default"        # 未达上限 → 继续循环（跳回自身）


class Stop(Node):
    """
    终止节点：计数结束后的清理/输出逻辑，然后用 "end" 通知 Agent 停止。
    """

    def execute(self, shared: dict) -> str | None:
        shared["status"] = "finished"
        print("计数完成，停止")
        return "end"    # "end" 是 Agent 的特殊终止信号


if __name__ == "__main__":
    tick = Tick()
    stop = Stop()

    # ★ 关键：把 tick 自己注册为 "default" 的后继
    # add_successor 旧版 API，等价于新版：tick >> tick（default 自指）
    tick.add_successor(tick, "default")     # default 边：指向自身，形成循环
    tick.add_successor(stop, "done")        # done 边：达到上限，跳到 Stop

    agent = Agent(start=tick)
    # 传入初始 shared，limit=5 表示循环 5 次
    final_shared = agent.run({"limit": 5})
    print("final shared:", final_shared)    # {"limit": 5, "count": 5, "status": "finished"}
