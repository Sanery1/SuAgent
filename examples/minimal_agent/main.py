"""
最小 Agent 示例：两步流程 + "end" 终止
=======================================

演示目标：
    用最少的代码展示 Agent 的基本工作原理：
        - Node 封装单步逻辑
        - shared 字典在节点间共享状态
        - 返回 "end" 让 Agent 主动终止（区别于 Workflow 被动到头结束）

流程图：
    SetX ──(default)──► PrintX ──"end"──► [Agent 停止]

    SetX  : 把 42 写入 shared["x"]
    PrintX: 读取并打印 shared["x"]，返回 "end" 主动终止

"end" vs 无后继的区别：
    - 无后继（到头结束）：Flow 找不到下一个节点，自然结束
    - 返回 "end"：Agent 检测到特殊动作名 "end"，主动停止
    两者在单路径场景效果相同，但 "end" 在循环或复杂分支中可以强制打断流程。

注意：Node.execute(shared) → str 是旧版 API 风格，
      当前版本已改为 Node.exec(payload) → (action, payload)。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.node import Agent, Node


class SetX(Node):
    """
    第一个节点：把固定值 42 写入 shared 字典。

    返回 None 等价于 "default"，Flow 沿 "default" 边跳转到下一个节点。
    这里演示了最简单的节点形式：只写状态，不做计算。
    """

    def execute(self, shared: dict) -> str | None:
        shared["x"] = 42    # 通过 shared 向后续节点传递数据
        return None         # None 等价于 "default" 动作


class PrintX(Node):
    """
    第二个节点：从 shared 读取 x 并打印，然后用 "end" 终止 Agent。

    "end" 是保留动作名：Agent 遇到它时立即停止执行。
    这是"主动终止"的方式，区别于到达无后继节点时的"被动终止"。
    """

    def execute(self, shared: dict) -> str | None:
        print(f"x = {shared['x']}")     # 输出：x = 42
        return "end"                    # 主动通知 Agent 停止


if __name__ == "__main__":
    set_x = SetX()
    print_x = PrintX()

    # add_successor 是旧版 API，连接 "default" 边
    # 等价于新版的：set_x >> print_x
    set_x.add_successor(print_x)   # 不传第二参数 = 默认 "default" 边

    agent = Agent(start=set_x)
    # agent.run() 返回最终的 shared 字典
    final_shared = agent.run()
    print("final shared:", final_shared)    # {"x": 42}
