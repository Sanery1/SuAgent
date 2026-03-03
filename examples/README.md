# Examples

下面是基于 `core/node.py` 的独立示例，每个都可单独运行。

## 1) minimal_agent
- 文件：`examples/minimal_agent/main.py`
- 演示：最小两步流程 + `end` 停止
- 运行：

```bash
python examples/minimal_agent/main.py
```

## 2) branching_agent
- 文件：`examples/branching_agent/main.py`
- 演示：决策节点根据 `action` 走 `pos/neg` 分支
- 运行：

```bash
python examples/branching_agent/main.py
```

## 3) default_fallback
- 文件：`examples/default_fallback/main.py`
- 演示：`action` 无匹配时自动回退到 `default`
- 运行：

```bash
python examples/default_fallback/main.py
```

## 4) counter_loop_agent
- 文件：`examples/counter_loop_agent/main.py`
- 演示：节点自循环（loop）+ 条件跳出 + `end` 停止
- 运行：

```bash
python examples/counter_loop_agent/main.py
```
