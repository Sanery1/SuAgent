"""
RAG 示例：用向量数据库检索相关文档，再让 LLM 基于文档回答问题

流程：
  1. 索引：把知识库文档存入 Chroma（只需运行一次）
  2. 查询：用户提问 → Chroma 找最相似的文档 → 拼入 prompt → LLM 回答

为什么这就是全部？RAG 本质就是 VectorDB，没有更多魔法。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.rag import get_collection, add_documents, query_documents
from core.llm import call_llm

# ── 知识库（实际项目中可以替换成你自己的文档） ───────────────────────────────
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

COLLECTION_NAME = "python_knowledge"


def build_index():
    """把知识库存入 Chroma（如果已存在则跳过）。"""
    collection = get_collection(COLLECTION_NAME)
    if collection.count() > 0:
        print(f"索引已存在（{collection.count()} 条），跳过索引步骤\n")
        return collection
    print("正在建立索引（首次运行需要调用 Embedding API）...")
    add_documents(collection, KNOWLEDGE_BASE)
    print()
    return collection


def answer_question(collection, question: str) -> str:
    """检索相关文档，拼入 prompt，让 LLM 回答。"""
    # 1. 向量检索
    relevant_docs = query_documents(collection, question, n_results=3)

    # 2. 拼成上下文
    context = "\n".join(f"- {doc}" for doc in relevant_docs)

    # 3. 构造带上下文的 prompt
    messages = [
        {"role": "system", "content": "你是一个知识助手，只根据提供的上下文回答问题，如果上下文中没有相关信息就说不知道。"},
        {"role": "user", "content": f"上下文：\n{context}\n\n问题：{question}"},
    ]

    return call_llm(messages)


if __name__ == "__main__":
    print("=== RAG 示例（输入 quit 退出）===\n")

    # 建立索引
    collection = build_index()

    # 问答循环
    while True:
        question = input("你的问题：").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        print("\n[检索中...]\n")
        answer = answer_question(collection, question)
        print(f"回答：{answer}\n")
