# SuAgent

一个轻量级的 AI Agent 框架，基于 Node/Flow 架构，支持工具调用、RAG、多智能体等核心能力。跟随 [poi-agent 一周学完 Agent](https://github.com/lasywolf/poipoi-agent) 教程从零构建。

## 特性

- **Node/Flow 架构** — 用运算符重载（`node - "action" >> next_node`）声明式地构建执行流程
- **统一 LLM 接口** — `call_llm()` 同时支持简单 prompt、多轮对话、工具调用
- **8 个内置工具** — `read` / `write` / `edit` / `bash` / `grep` / `find` / `ls` / `search`
- **流式输出** — LLM 响应逐 token 打印，工具调用实时展示
- **RAG 知识库** — ChromaDB 向量存储 + OpenAI Embedding API
- **上下文压缩** — 超出短期记忆上限时自动 LLM 摘要压缩历史
- **Multi-Agent** — Master 分发任务给 Subagent，上下文完全隔离
- **兼容任意 OpenAI 格式 API** — Kimi、Zhipu、DeepSeek、本地模型均可接入

---

## 快速开始

### 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
# 克隆项目
git clone https://github.com/your-username/SuAgent.git
cd SuAgent

# 安装依赖（uv 会自动创建虚拟环境）
uv sync
```

### 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 API 配置：

```bash
cp .env.example .env
```

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/   # 或其他兼容接口
LLM_MODEL=glm-4-flash                                   # 模型名称
EMBEDDING_MODEL=embedding-2                             # Embedding 模型
```

### 运行示例

```bash
# 激活虚拟环境
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux

# 最简 Chatbot
python examples/chatbot/main.py

# 带工具的 Agent
python examples/chatbot_with_tools/main.py

# Workflow：搜索 + 摘要
python examples/workflow/main.py

# RAG 知识库问答
python examples/rag/main.py

# Coding Agent（完整智能体）
python agent/main.py

# Multi-Agent 演示
python examples/multi_agent/main.py
```

---

## 项目结构

```
SuAgent/
├── core/
│   ├── node.py          # Node / Flow 核心架构
│   ├── llm.py           # 统一 LLM 调用接口
│   └── rag.py           # ChromaDB + Embedding RAG
│
├── tools/
│   ├── builtins/
│   │   ├── tool_def.py  # Tool 类 + get_builtin_tools()
│   │   ├── read.py      # 读取文件（支持分页）
│   │   ├── write.py     # 写入文件
│   │   ├── edit.py      # 精确替换文件内容
│   │   ├── bash.py      # 执行 Shell 命令
│   │   ├── grep.py      # 正则搜索（rg / Python fallback）
│   │   ├── find.py      # 文件查找（fd / glob fallback）
│   │   ├── ls.py        # 列出目录
│   │   └── search.py    # DuckDuckGo 网络搜索
│   ├── executor.py      # ToolCall / ToolResult / ToolExecutor
│   └── __init__.py
│
├── agent/
│   ├── main.py          # Coding Agent 交互入口 + 上下文压缩
│   ├── loop.py          # 单轮推理：流式输出 + 工具调用循环
│   └── prompts.py       # Agent 系统提示词
│
├── examples/
│   ├── chatbot/         # 多轮对话
│   ├── chatbot_with_tools/  # 带工具调用的对话
│   ├── workflow/        # Query → Search → Summarize 流水线
│   ├── rag/             # 知识库问答
│   └── multi_agent/     # Master + Subagent 分工协作
│
├── chroma_db/           # RAG 向量数据持久化（自动生成）
├── .env                 # API 配置（不提交到 git）
├── .env.example         # 配置模板
└── pyproject.toml       # 项目依赖
```

---

## 核心概念

### Node / Flow

Node 是一个执行单元，`exec(payload)` 返回 `(action, next_payload)`：

```python
from core.node import Node, Flow, shared

class MyNode(Node):
    def exec(self, payload):
        result = do_something(payload)
        return "next", result

# 用运算符声明流程
node_a - "next" >> node_b - "done" >> node_c

# 运行
Flow(node_a).run(initial_payload)
```

### call_llm

```python
from core.llm import call_llm

# 简单模式 → 返回字符串
response = call_llm("用一句话解释什么是 Agent")

# 多轮对话 + 工具调用 → 返回 dict（含 tool_calls）
result = call_llm(
    messages=history,
    tools=[tool.to_llm_format() for tool in get_tools()],
    system_prompt="你是一个编程助手"
)
```

### 自定义工具

```python
from tools.builtins.tool_def import Tool

my_tool = Tool(
    name="my_tool",
    description="工具描述",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "输入参数"}
        },
        "required": ["input"]
    },
    fn=lambda input: f"处理结果: {input}"
)
```

### RAG

```python
from core.rag import get_collection, add_documents, query_documents

col = get_collection("my_kb")
add_documents(col, ["文档1内容", "文档2内容"], ["id1", "id2"])

results = query_documents(col, "查询问题", n_results=3)
```

---

## 架构图

```
用户输入
   │
   ▼
┌──────────────────────┐
│   agent/main.py      │  ← 上下文压缩 / 命令处理
│  (Coding Agent REPL) │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   agent/loop.py      │  ← 流式输出 + 工具调用循环
│  run_agent_turn()    │
└────┬─────────────────┘
     │
     ├──► call_llm_stream()  ← core/llm.py
     │
     └──► ToolExecutor       ← tools/executor.py
               │
               ├── read / write / edit / bash
               ├── grep / find / ls
               └── search (DuckDuckGo)
```

---

## 支持的模型

任何兼容 OpenAI Chat API 格式的模型均可接入，只需修改 `.env`：

| 提供商 | BASE_URL | 模型示例 |
|--------|----------|---------|
| Kimi (月之暗面) | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4/` | `glm-4-flash` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |

---

## 参考资料

- 教程来源：[poi-agent — 一周学完 Agent](https://github.com/lasywolf/poipoi-agent)
- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [ChromaDB 文档](https://docs.trychroma.com/)
- [DuckDuckGo Search](https://pypi.org/project/duckduckgo-search/)

---

## License

MIT
