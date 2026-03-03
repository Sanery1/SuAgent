"""
RAG 示例：用向量数据库检索相关文档，再让 LLM 基于文档回答问题
===============================================================

演示目标：
    RAG（Retrieval-Augmented Generation，检索增强生成）的完整实现。
    核心思路：不把所有知识塞进 prompt，而是"先检索，后生成"：
        1. 把知识库文档存入向量数据库（只做一次）
        2. 用户提问时，先从向量库找最相关的文档片段
        3. 把这些片段作为上下文塞进 prompt，让 LLM 基于证据回答

为什么 RAG 比直接放在 prompt 里好？
    - 知识库可以很大（几千篇文档），每次只取最相关的几条，节省 token
    - 有文档依据的回答更可靠，减少 LLM "幻觉"
    - 知识库可以随时更新，不需要重新训练模型

两阶段流程：
    ┌──────────────────────────────────────────────────────────────┐
    │ 【索引阶段】一次性执行，结果持久化到 chroma_db/              │
    │   文档文本 → Embedding API → 浮点向量 → 存入 ChromaDB        │
    └──────────────────────────────────────────────────────────────┘
    ┌──────────────────────────────────────────────────────────────┐
    │ 【查询阶段】每次问答执行                                      │
    │   用户问题 → Embedding API → 向量                            │
    │           → ChromaDB 余弦相似度搜索 → 最相关的 N 条文档      │
    │           → 拼成上下文 → 附加到 prompt → LLM 回答            │
    └──────────────────────────────────────────────────────────────┘
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.rag import get_collection, add_documents, query_documents
from core.llm import call_llm

# ── 知识库内容（实际项目中可替换为从文件/数据库加载）────────────────────────
# 每条字符串是一个"文档片段"（chunk），粒度适中（一个知识点一条）是最佳实践
KNOWLEDGE_BASE = [
    "Python 是一种解释型、面向对象的编程语言，由 Guido van Rossum 于 1991 年创建。",
    "Python 的列表（list）是有序可变序列，使用方括号定义，例如 [1, 2, 3]。",
    "Python 的字典（dict）是键值对集合，使用花括号定义，例如 {'key': 'value'}。",
    "Python 的 for 循环语法：for item in iterable:，可以遍历任何可迭代对象。",
    "Python 使用缩进（通常4个空格）来表示代码块，没有花括号。",
    "pip 是 Python 的包管理器，用 pip install 包名 来安装第三方库。",
    "uv 是用 Rust 编写的 Python 包管理器，比 pip 快很多，推荐用于新项目。",
    "虚拟环境（venv）用于隔离不同项目的依赖，避免版本冲突。",
    "Agent 是一种能够调用工具、自主决策的 AI 系统，核心是 LLM + 工具调用。",
    "RAG（Retrieval-Augmented Generation）的本质是：用向量数据库检索相关文档，再交给 LLM 生成回答。",
    "Chroma 是一个轻量级向量数据库，部署简单，适合本地和小规模生产使用。",
    "Embedding 是把文本转换成向量的过程，语义相近的文本对应的向量距离也更近。",
]

# 集合名称：相当于数据库中的"表名"，同名集合可以复用已有数据
COLLECTION_NAME = "python_knowledge"


def build_index():
    """
    建立向量索引（索引阶段）。

    首次运行时把 KNOWLEDGE_BASE 存入 ChromaDB，后续检测到已有数据则跳过。
    "幂等性"处理很重要：重复运行不会导致数据重复插入，也不会重复调 Embedding API。

    内部流程：
        collection.add() → ApiEmbeddingFunction.__call__() → Embedding API → 存向量
    """
    collection = get_collection(COLLECTION_NAME)
    if collection.count() > 0:
        # 已有数据，直接复用（避免重复调用 Embedding API 浪费费用）
        print(f"索引已存在（{collection.count()} 条），跳过索引步骤\n")
        return collection
    print("正在建立索引（首次运行需要调用 Embedding API）...")
    add_documents(collection, KNOWLEDGE_BASE)
    print()
    return collection


def answer_question(collection, question: str) -> str:
    """
    RAG 问答（查询阶段）：检索相关文档 → 构造带上下文的 prompt → LLM 回答。

    Args:
        collection : 已建立索引的 ChromaDB 集合
        question   : 用户的问题

    Returns:
        LLM 基于检索到的文档生成的回答（dict，含 content 字段）

    三步执行：
        Step 1 - 向量检索：把 question 转为向量，在库中找最相似的 3 条文档
        Step 2 - 上下文拼接：把检索到的文档格式化为 "- 文档内容" 列表
        Step 3 - LLM 生成：system 提示要求"只根据上下文回答"，防止 LLM 编造内容
    """
    # Step 1：向量检索，返回最相似的 3 条文档（n_results 可按需调整）
    relevant_docs = query_documents(collection, question, n_results=3)

    # Step 2：把文档列表格式化为上下文字符串
    # 例：
    #   - Python 的列表（list）是有序可变序列...
    #   - Python 的字典（dict）是键值对集合...
    context = "\n".join(f"- {doc}" for doc in relevant_docs)

    # Step 3：构造 messages，system 提示词限制 LLM 只能基于上下文回答
    messages = [
        {
            "role": "system",
            "content": "你是一个知识助手，只根据提供的上下文回答问题，如果上下文中没有相关信息就说不知道。",
        },
        {
            "role": "user",
            # 把检索到的上下文和用户问题一起发给 LLM
            "content": f"上下文：\n{context}\n\n问题：{question}",
        },
    ]

    return call_llm(messages)


if __name__ == "__main__":
    print("=== RAG 示例（输入 quit 退出）===\n")

    # 第一步：建立（或复用）向量索引
    collection = build_index()

    # 第二步：进入问答循环
    while True:
        question = input("你的问题：").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        print("\n[检索中...]\n")
        answer = answer_question(collection, question)
        # call_llm 对话模式返回 dict，取 content 字段打印
        content = answer.get("content", answer) if isinstance(answer, dict) else answer
        print(f"回答：{content}\n")
