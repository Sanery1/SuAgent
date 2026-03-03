"""
Node / Flow —— 流程编排核心
============================

核心思想：把任意一段逻辑封装成 "Node（节点）"，每个节点执行后
返回 (动作, 数据)，Flow 根据动作名跳转到下一个节点，构成有向图。

声明式连接语法（用运算符重载）：
    node_a - "action" >> node_b
    等价于：node_a 执行后若返回 "action" 则跳转到 node_b

典型使用场景：
    chat - "tool_call" >> tool_exec          # LLM 要调工具 → 去执行
    tool_exec - "chat"   >> chat             # 工具执行完 → 回到 LLM
    chat - "output"      >> output_node      # LLM 直接回答 → 输出
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import time

# ── 全局共享状态 ──────────────────────────────────────────────────────────────
# shared 是一个模块级别的普通字典，所有节点都可以读写它。
# 作用：充当节点间的"黑板"，避免把大量状态作为 payload 逐层传递。
# 例：messages 列表、tools 注册表、ToolExecutor 实例等都放在 shared 里。
shared: Dict[str, Any] = {}


class Node:
    """
    执行节点基类。

    每个 Node 代表流程中的一个步骤（如：调用 LLM、执行工具、打印输出）。
    子类只需实现 exec() 方法，描述"这一步做什么"。

    属性：
        successors  -- 动作名 → 下一个节点 的映射表
        _action     -- 暂存下一次 >> 时使用的动作名（默认 "default"）
        max_retries -- exec() 失败时最多重试次数（默认 1，即不重试）
        wait        -- 每次重试前等待的秒数（默认 0）
    """

    def __init__(self, max_retries: int = 1, wait: float = 0) -> None:
        # successors：动作名 → 下一节点，例如 {"tool_call": tool_node, "output": output_node}
        self.successors: Dict[str, "Node"] = {}
        # _action：运算符重载时的临时状态，记录"当前箭头应该绑定哪个动作名"
        self._action: str = "default"
        self.max_retries = max_retries  # 最大执行次数（1 = 不重试）
        self.wait = wait                # 重试前暂停秒数

    def exec(self, payload: Any) -> Tuple[str, Any]:
        """
        【子类必须重写】核心业务逻辑。

        Args:
            payload: 上一个节点传来的数据（第一个节点由 Flow.run() 传入）

        Returns:
            (action, next_payload)
            - action       : 字符串，决定跳转到 successors 里哪个节点
            - next_payload : 传给下一个节点的 exec() 的参数
        """
        raise NotImplementedError

    def _exec(self, payload: Any) -> Tuple[str, Any]:
        """
        内部执行入口，封装重试逻辑，不直接调用。

        重试策略：
            - 最多执行 max_retries 次
            - 前 (max_retries-1) 次异常会被捕获并等待 wait 秒后重试
            - 最后一次异常直接向上抛出
        """
        for cur_retry in range(self.max_retries):
            try:
                return self.exec(payload)
            except Exception as e:
                if cur_retry == self.max_retries - 1:
                    raise e          # 最后一次：不再重试，抛出原始异常
                if self.wait > 0:
                    time.sleep(self.wait)   # 重试前等待
        raise RuntimeError("Unexpected error in Node._exec")

    # ── 运算符重载：声明式连接语法 ─────────────────────────────────────────────

    def __rshift__(self, other: "Node") -> "Node":
        """
        >> 运算符：把当前节点与下一个节点连接起来。

        执行时使用 _action 作为键存入 successors，然后重置 _action 为 "default"。

        例：
            node_a - "success" >> node_b
            # _action 已被 __sub__ 设置为 "success"
            # 此时把 node_b 存入 node_a.successors["success"]
            # 返回 node_b，因此支持链式写法：... >> node_b >> node_c
        """
        self.successors[self._action] = other
        self._action = "default"    # 用完后重置，避免影响下次连接
        return other

    def __sub__(self, action: str) -> "Node":
        """
        - 运算符：设置下次 >> 时绑定的动作名。

        例：
            node_a - "tool_call" >> node_b
            # 先执行 node_a.__sub__("tool_call") → 返回 node_a，并将 _action 置为 "tool_call"
            # 再执行 node_a.__rshift__(node_b)    → 存入 successors["tool_call"] = node_b
        """
        if not isinstance(action, str):
            raise TypeError("Action must be a string")
        self._action = action or "default"
        return self  # 返回自身，让 >> 可以紧接着调用


class Flow:
    """
    流程编排器：从起始节点开始，依次执行并按动作名跳转，直到无后继节点为止。

    执行过程（状态机）：
        curr = start_node
        while curr 存在:
            action, payload = curr._exec(payload)
            curr = curr.successors.get(action)  # 找下一个节点
        return action, payload                  # 返回最终状态

    如果某个节点返回的 action 在 successors 里找不到，流程结束。
    """

    def __init__(self, start: Optional[Node] = None) -> None:
        self.start = start

    def run(self, payload: Any = None) -> Tuple[Optional[str], Any]:
        """
        启动流程。

        Args:
            payload: 传给第一个节点的初始数据（通常为 None、用户输入或任务描述）

        Returns:
            (last_action, final_payload) —— 最后一个节点返回的动作和数据
        """
        curr, last_action = self.start, "default"
        while curr:
            last_action, payload = curr._exec(payload)
            curr = curr.successors.get(last_action)  # 按动作名跳转下一节点
        return last_action, payload
