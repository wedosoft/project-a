"""
문서 검색 모듈

이 모듈은 ChromaDB를 사용하여 임베딩된 문서를 검색하는 기능을 제공합니다.
쿼리 임베딩과 유사도가 높은 문서를 효율적으로 검색합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""
import chromadb
from typing import List, Any

def get_chroma_collection(collection_name: str = "docs") -> Any:
    """
    ChromaDB 컬렉션을 반환합니다. 없으면 생성합니다.
    """
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    if collection_name not in [c.name for c in chroma_client.list_collections()]:
        chroma_client.create_collection(collection_name)
    return chroma_client.get_collection(collection_name)

def retrieve_top_k_docs(query_embedding: List[float], top_k: int) -> List[str]:
    """
    쿼리 임베딩을 이용해 VectorDB에서 top_k 문서를 검색합니다.
    """
    collection = get_chroma_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    docs = results.get("documents", [[]])[0]
    return docs if docs else []