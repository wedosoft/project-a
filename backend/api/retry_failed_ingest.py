"""
Qdrant 저장 누락 문서 재시도 스크립트

- Freshdesk 전체 문서 ID 목록 확보
- Qdrant 저장된 original_id 목록 조회
- 누락된 문서만 임베딩 및 Qdrant 저장 재시도
"""

import asyncio
import logging
from core.vectordb import vector_db
from freshdesk.fetcher import fetch_tickets, fetch_kb_articles
from core.embedder import embed_documents, process_documents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def retry_failed_ingest():
    logger.info("Qdrant 저장 누락 문서 재시도 시작")
    # 1. Freshdesk 전체 문서 수집
    tickets = await fetch_tickets()
    articles = await fetch_kb_articles()
    all_docs = []
    for t in tickets:
        doc_id = f"ticket-{t.get('id')}"
        all_docs.append({"id": doc_id, "text": t.get("description_text") or t.get("description") or "", "metadata": t})
    for a in articles:
        doc_id = f"kb-{a.get('id')}"
        all_docs.append({"id": doc_id, "text": a.get("description_text") or a.get("description") or "", "metadata": a})
    all_ids = set(doc["id"] for doc in all_docs)
    logger.info(f"Freshdesk 전체 문서 수: {len(all_ids)}")

    # 2. Qdrant 저장된 original_id 목록 조회
    qdrant_ids = set(vector_db.list_all_ids())
    logger.info(f"Qdrant 저장된 문서 수: {len(qdrant_ids)}")

    # 3. 누락된 문서만 추출
    missing_ids = all_ids - qdrant_ids
    logger.info(f"Qdrant에 누락된 문서 수: {len(missing_ids)}")
    if not missing_ids:
        logger.info("누락된 문서가 없습니다. 종료합니다.")
        return
    missing_docs = [doc for doc in all_docs if doc["id"] in missing_ids]

    # 4. 임베딩 및 Qdrant 저장 재시도 (batch)
    logger.info(f"누락 문서 {len(missing_docs)}개 임베딩 및 저장 재시도...")
    batch_size = 50
    for i in range(0, len(missing_docs), batch_size):
        batch = missing_docs[i:i+batch_size]
        texts = [d["text"] for d in batch]
        metadatas = [d["metadata"] for d in batch]
        ids = [d["id"] for d in batch]
        embeddings = embed_documents(texts)
        vector_db.add_documents(texts=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
        logger.info(f"{i+1}~{i+len(batch)} 저장 완료")
    logger.info("Qdrant 누락 문서 저장 재시도 완료")

if __name__ == "__main__":
    asyncio.run(retry_failed_ingest())
