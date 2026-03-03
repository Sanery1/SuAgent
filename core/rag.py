"""
RAG（检索增强生成）核心模块
============================

RAG = Retrieval-Augmented Generation，核心思路：
    不把所有知识都塞进 prompt，而是先用语义搜索找到相关文档，
    再把这些文档作为上下文附给 LLM，让 LLM 基于证据回答。

完整流程分两个阶段：

  【索引阶段】（一次性，提前做好）
      原始文档
        → call Embedding API（把文本变成高维向量）
        → 存入 ChromaDB（向量数据库，持久化到本地磁盘）

  【查询阶段】（每次问答时执行）
      用户问题
        → call Embedding API（把问题也变成向量）
        → ChromaDB 计算余弦相似度，找出最近的 n 条文档
        → 把这 n 条文档拼成上下文
        → 连同问题一起发给 LLM
        → LLM 基于上下文给出有据可查的回答

为什么需要 Embedding？
    普通关键词搜索是精确匹配，搜不到同义词。
    Embedding 把语义编码成向量，语义相似的句子向量距离近，
    即使用词不同也能匹配到（例如"下雨"和"天气湿润"）。
"""

import os
import sys
import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings
from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# Embedding 模型与 LLM 使用同一个 OpenAI 兼容客户端，通过 .env 配置
_client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL"),
)

# Embedding 模型名（Zhipu 用 "embedding-2"，OpenAI 用 "text-embedding-3-small" 等）
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "embedding-2")


class ApiEmbeddingFunction(EmbeddingFunction):
    """
    自定义 Embedding 函数，替代 ChromaDB 默认的本地模型。

    ChromaDB 默认会在本地下载并运行 sentence-transformers 模型（体积大、需 GPU）。
    这里改用远程 API，不需要本地 GPU，与 LLM 使用同一家服务商即可。

    ChromaDB 在调用 add() 和 query() 时会自动调用这个函数，无需手动干预。
    """

    def __call__(self, input: Documents) -> Embeddings:
        """
        把一批文本转换为向量列表。

        Args:
            input: ChromaDB 传入的文本列表（Documents = list[str]）

        Returns:
            每个文本对应一个浮点数向量（Embeddings = list[list[float]]）
        """
        result = []
        for text in input:
            # 每次调用 API 处理一条文本（可批量优化，但简单起见逐条处理）
            resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=text)
            result.append(resp.data[0].embedding)   # 取第一条结果的向量
        return result


def get_collection(name: str, persist_path: str = "./chroma_db"):
    """
    获取（或自动创建）一个 ChromaDB 集合（Collection）。

    Collection 类似于数据库中的"表"：同名则复用已有数据，不存在则新建。
    PersistentClient 会把向量数据持久化到本地磁盘（默认 ./chroma_db/），
    程序重启后数据不丢失。

    Args:
        name         : 集合名称，例如 "knowledge_base"
        persist_path : 本地存储路径，默认 "./chroma_db"

    Returns:
        chromadb.Collection 对象，用于后续的 add / query 操作
    """
    client = chromadb.PersistentClient(path=persist_path)
    return client.get_or_create_collection(
        name=name,
        # 注入自定义 Embedding 函数，后续 add/query 都会自动调用它
        embedding_function=ApiEmbeddingFunction(),
    )


def add_documents(collection, documents: list[str], ids: list[str] | None = None):
    """
    把文档列表存入向量数据库（自动计算 embedding）。

    ChromaDB 的 collection.add() 内部会调用 ApiEmbeddingFunction，
    把每条文档先转成向量再存储，不需要手动调用 Embedding API。

    Args:
        collection : get_collection() 返回的集合对象
        documents  : 要存入的文档文本列表
        ids        : 每条文档的唯一 ID（不传则自动生成 doc_0, doc_1, ...）
                     注意：同一集合内 ID 必须唯一，重复插入会报错

    注意：documents 和 ids 长度必须一致。
    """
    if ids is None:
        ids = [f"doc_{i}" for i in range(len(documents))]
    collection.add(documents=documents, ids=ids)
    print(f"已存入 {len(documents)} 条文档")


def query_documents(collection, question: str, n_results: int = 3) -> list[str]:
    """
    用问题在向量数据库中检索最相似的 n 条文档。

    检索原理：
        1. 把 question 通过 Embedding API 转换为向量
        2. 计算该向量与库中所有文档向量的余弦相似度
        3. 返回相似度最高的 n_results 条原始文档文本

    Args:
        collection : get_collection() 返回的集合对象
        question   : 用户的查询问题
        n_results  : 返回最相似的文档数量（默认 3）

    Returns:
        文档文本列表，按相似度从高到低排列，可直接拼接为 LLM 上下文
    """
    results = collection.query(query_texts=[question], n_results=n_results)
    # results["documents"] 是二维列表：[query1的结果列表, query2的结果列表, ...]
    # 我们只传了 1 条 query，所以取 [0] 即可
    return results["documents"][0]
