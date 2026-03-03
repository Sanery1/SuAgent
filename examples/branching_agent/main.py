"""
分支 Agent 示例：根据 action 走不同节点

流程：Decide -> (pos -> Pos) / (neg -> Neg)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Agent, Node


class Decide(Node):
    def execute(self, shared: dict) -> str | None:
        n = shared.get("n", 0)
        return "pos" if n > 0 else "neg"


class Pos(Node):
    def execute(self, shared: dict) -> str | None:
        shared["msg"] = "n 是正数"
        print(shared["msg"])
        return "end"


class Neg(Node):
    def execute(self, shared: dict) -> str | None:
        shared["msg"] = "n 不是正数"
        print(shared["msg"])
        return "end"


if __name__ == "__main__":
    decide = Decide()
    pos = Pos()
    neg = Neg()

    decide.add_successor(pos, "pos")
    decide.add_successor(neg, "neg")

    value = int(input("请输入一个整数 n：").strip() or "0")

    agent = Agent(start=decide)
    final_shared = agent.run({"n": value})
    print("final shared:", final_shared)
