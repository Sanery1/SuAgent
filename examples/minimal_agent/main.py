"""
最小 Agent 示例：两步 + end 结束

流程：SetX -> PrintX
- SetX 写入 shared['x']
- PrintX 打印并返回 'end'，Agent 立即停止
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Agent, Node


class SetX(Node):
    def execute(self, shared: dict) -> str | None:
        shared["x"] = 42
        return None  # 等价于 "default"


class PrintX(Node):
    def execute(self, shared: dict) -> str | None:
        print(f"x = {shared['x']}")
        return "end"


if __name__ == "__main__":
    set_x = SetX()
    print_x = PrintX()

    set_x.add_successor(print_x)  # default 边

    agent = Agent(start=set_x)
    final_shared = agent.run()
    print("final shared:", final_shared)
