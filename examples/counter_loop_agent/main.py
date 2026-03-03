"""
循环 Agent 示例：计数直到满足条件后 end

流程：Tick -> Tick -> ... -> Stop
- Tick 每次执行 +1
- 未达到上限返回 default（走回 Tick）
- 达到上限返回 'done'（走到 Stop）
- Stop 返回 'end'，Agent 停止
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Agent, Node


class Tick(Node):
    def execute(self, shared: dict) -> str | None:
        shared["count"] = shared.get("count", 0) + 1
        print(f"tick -> count={shared['count']}")

        limit = shared.get("limit", 3)
        if shared["count"] >= limit:
            return "done"
        return "default"


class Stop(Node):
    def execute(self, shared: dict) -> str | None:
        shared["status"] = "finished"
        print("计数完成，停止")
        return "end"


if __name__ == "__main__":
    tick = Tick()
    stop = Stop()

    tick.add_successor(tick, "default")  # 回到自己，形成 loop
    tick.add_successor(stop, "done")

    agent = Agent(start=tick)
    final_shared = agent.run({"limit": 5})
    print("final shared:", final_shared)
