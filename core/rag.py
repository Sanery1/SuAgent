"""
RAG 核心模块
= VectorDB（文档存入 + 相似检索）

流程：
  索引阶段：文档 → Embedding API → 向量 → 存入 Chroma
  查询阶段：问题 → Embedding API → 向量 → Chroma 找相似 → 返回相关文档
"""

import os
import sys
import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings
from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# Embedding 用同一个 OpenAI 兼容客户端
_client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL"),
)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "embedding-2")


class ApiEmbeddingFunction(EmbeddingFunction):
    """调用 API 的 Embedding 函数，替代 Chroma 默认的本地模型。"""

    def __call__(self, input: Documents) -> Embeddings:
        result = []
        for text in input:
            resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=text)
            result.append(resp.data[0].embedding)
        return result


def get_collection(name: str, persist_path: str = "./chroma_db"):
    """获取（或创建）一个 Chroma 集合（持久化到本地磁盘）。"""
    client = chromadb.PersistentClient(path=persist_path)
    return client.get_or_create_collection(
        name=name,
        embedding_function=ApiEmbeddingFunction(),
    )


def add_documents(collection, documents: list[str], ids: list[str] | None = None):
    """把文档列表存入向量数据库（自动计算 embedding）。"""
    if ids is None:
        ids = [f"doc_{i}" for i in range(len(documents))]
    collection.add(documents=documents, ids=ids)
    print(f"已存入 {len(documents)} 条文档")


def query_documents(collection, question: str, n_results: int = 3) -> list[str]:
    """用问题检索最相似的 n 条文档，返回文档列表。"""
    results = collection.query(query_texts=[question], n_results=n_results)
    return results["documents"][0]
