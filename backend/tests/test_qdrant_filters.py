#!/usr/bin/env python3
"""
Qdrant doc_type 필터링 성능 최적화 테스트
- Qdrant 쿼리 레벨에서 doc_type 필터가 동작하는지 확인
- 메모리 내 필터링 vs. Qdrant 필터링 성능 비교
"""

import sys
import os
import time
import asyncio
from typing import List, Dict, Any

# 백엔드 모듈 경로 추가
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

from core.config import Settings, TenantConfig
from core.database.vectordb import QdrantAdapter
from qdrant_client.models import Filter, FieldCondition, MatchValue
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_qdrant_doc_type_filter():
    """Qdrant 쿼리 레벨에서 doc_type 필터 동작 테스트"""
    
    # 설정 로드
    settings = Settings()
    
    # QdrantAdapter 인스턴스 생성 (기본 컬렉션 사용)
    vectordb = QdrantAdapter()
    
    # 테스트용 임베딩 (1536차원 - OpenAI/Anthropic 표준)
    test_embedding = [0.1] * 1536
    
    # 테스트 파라미터 (실제 데이터 있는 테넌트 사용)
    tenant_id = "wedosoft"
    platform = "freshdesk"
    
    print("=== Qdrant doc_type 필터링 성능 테스트 ===\n")
    
    # 1. 기존 방식: 메모리 내 필터링 (top_k * 10개 가져와서 필터링)
    print("1️⃣ 기존 방식: 메모리 내 doc_type 필터링")
    start_time = time.time()
    result_memory = vectordb.search(
        query_embedding=test_embedding,
        top_k=10,
        tenant_id=tenant_id,
        platform=platform,
        doc_type="article"
    )
    memory_time = time.time() - start_time
    print(f"   결과: {len(result_memory.get('results', []))}개, 소요시간: {memory_time:.3f}초")
    
    # 2. Qdrant 쿼리 필터링 테스트
    print("\n2️⃣ Qdrant 쿼리 레벨 doc_type 필터링 테스트")
    
    # 직접 Qdrant 클라이언트로 doc_type 필터 테스트
    filter_conditions = [
        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
        FieldCondition(key="platform", match=MatchValue(value=platform)),
        FieldCondition(key="doc_type", match=MatchValue(value="article"))  # doc_type 필터 추가
    ]
    
    search_filter = Filter(must=filter_conditions)
    
    try:
        start_time = time.time()
        search_results = vectordb.client.search(
            collection_name=vectordb.collection_name,
            query_vector=test_embedding,
            query_filter=search_filter,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        qdrant_time = time.time() - start_time
        print(f"   결과: {len(search_results)}개, 소요시간: {qdrant_time:.3f}초")
        print(f"   ✅ Qdrant 쿼리 레벨 doc_type 필터링 성공!")
        
        # 결과 샘플 확인
        if search_results:
            sample = search_results[0]
            print(f"   샘플 결과: doc_type={sample.payload.get('doc_type')}, score={sample.score:.4f}")
            
    except Exception as e:
        print(f"   ❌ Qdrant 쿼리 필터링 실패: {e}")
        return
    
    # 3. 성능 비교
    print(f"\n📊 성능 비교:")
    print(f"   메모리 내 필터링: {memory_time:.3f}초")
    print(f"   Qdrant 쿼리 필터: {qdrant_time:.3f}초")
    if memory_time > 0:
        improvement = ((memory_time - qdrant_time) / memory_time) * 100
        print(f"   성능 개선: {improvement:.1f}%")
    
    # 4. 다른 doc_type도 테스트
    print(f"\n3️⃣ 다른 doc_type 테스트 (ticket)")
    
    filter_conditions_ticket = [
        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
        FieldCondition(key="platform", match=MatchValue(value=platform)),
        FieldCondition(key="doc_type", match=MatchValue(value="ticket"))
    ]
    
    search_filter_ticket = Filter(must=filter_conditions_ticket)
    
    try:
        start_time = time.time()
        ticket_results = vectordb.client.search(
            collection_name=vectordb.collection_name,
            query_vector=test_embedding,
            query_filter=search_filter_ticket,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        ticket_time = time.time() - start_time
        print(f"   티켓 검색 결과: {len(ticket_results)}개, 소요시간: {ticket_time:.3f}초")
        
        if ticket_results:
            sample = ticket_results[0]
            print(f"   샘플 결과: doc_type={sample.payload.get('doc_type')}, score={sample.score:.4f}")
            
    except Exception as e:
        print(f"   ❌ 티켓 검색 실패: {e}")
    
    print(f"\n✅ Qdrant doc_type 필터링 테스트 완료")

if __name__ == "__main__":
    asyncio.run(test_qdrant_doc_type_filter())
