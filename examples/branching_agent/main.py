"""
分支 Agent 示例：根据运行时数据决定走哪条路径
==============================================

演示目标：
    展示 Node 如何根据 shared 中的数据动态选择下一个节点（分支逻辑）。
    这是构建"条件路由"的基础：LLM 可以通过返回不同的动作名来控制流程走向。

流程图：
         ┌──"pos"──► Pos（打印"n 是正数"）
         │
    Decide
         │
         └──"neg"──► Neg（打印"n 不是正数"）

Decide 节点检查 shared["n"]，返回 "pos" 或 "neg"，
Flow 根据返回的动作名跳转到对应后继节点。

注意：Node.execute(shared) → str 是旧版 API 风格，
      当前版本已改为 Node.exec(payload) → (action, payload)。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Agent, Node


class Decide(Node):
    """
    路由节点：根据 shared["n"] 的值返回不同的动作名，实现运行时分支。

    关键点：节点本身不做任何业务操作，只负责"路由"——这是单一职责原则。
    所有的逻辑判断集中在 execute() 的返回值上，而非直接调用其他节点。
    """

    def execute(self, shared: dict) -> str | None:
        n = shared.get("n", 0)
        # 返回的字符串就是"动作名"，Flow 根据它在 successors 里找对应节点
        return "pos" if n > 0 else "neg"


class Pos(Node):
    """处理正数的节点：写入结果并打印。"""

    def execute(self, shared: dict) -> str | None:
        shared["msg"] = "n 是正数"
        print(shared["msg"])
        return "end"    # 主动终止 Agent


class Neg(Node):
    """处理非正数的节点：写入结果并打印。"""

    def execute(self, shared: dict) -> str | None:
        shared["msg"] = "n 不是正数"
        print(shared["msg"])
        return "end"    # 主动终止 Agent


if __name__ == "__main__":
    decide = Decide()
    pos = Pos()
    neg = Neg()

    # 注册两条不同的动作边（旧版 API）
    # 等价于新版的：decide - "pos" >> pos; decide - "neg" >> neg
    decide.add_successor(pos, "pos")    # decide 返回 "pos" 时跳到 pos 节点
    decide.add_successor(neg, "neg")    # decide 返回 "neg" 时跳到 neg 节点

    value = int(input("请输入一个整数 n：").strip() or "0")

    agent = Agent(start=decide)
    # 把 n 通过 shared 初始值传入
    final_shared = agent.run({"n": value})
    print("final shared:", final_shared)    # {"n": value, "msg": "n 是正数/不是正数"}
