#!/usr/bin/env python3
"""
실제 데이터를 사용한 벡터DB 검색 테스트

실제 아티클 ID: 5000875040
실제 티켓 ID: 104

이 스크립트는 실제 데이터로 벡터DB의 doc_type 필터링과 검색이 정상 작동하는지 확인합니다.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from core.database.vectordb import vector_db


async def check_data_exists():
    """실제 데이터가 벡터DB에 존재하는지 확인"""
    logger.info("=== 실제 데이터 존재 여부 확인 ===")
    
    # 전체 문서 수 확인
    total_count = vector_db.count()
    logger.info(f"전체 문서 수: {total_count}")
    
    # 컬렉션의 샘플 데이터 조회 (첫 10개)
    try:
        scroll_result = vector_db.client.scroll(
            collection_name=vector_db.collection_name,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0] if scroll_result else []
        logger.info(f"샘플 문서 {len(points)}개 조회:")
        
        tenant_ids = set()
        doc_types = set()
        
        for i, point in enumerate(points):
            payload = point.payload
            tenant_id = payload.get("tenant_id", "N/A")
            doc_type = payload.get("doc_type", "N/A")
            original_id = payload.get("original_id", "N/A")
            
            tenant_ids.add(tenant_id)
            doc_types.add(doc_type)
            
            logger.info(f"  [{i+1}] ID: {point.id[:20]}..., tenant_id: {tenant_id}, doc_type: {doc_type}, original_id: {original_id}")
        
        logger.info(f"발견된 tenant_id들: {list(tenant_ids)}")
        logger.info(f"발견된 doc_type들: {list(doc_types)}")
        
        return list(tenant_ids), list(doc_types)
        
    except Exception as e:
        logger.error(f"샘플 데이터 조회 실패: {e}")
        return [], []


async def test_specific_document_search(tenant_id: str, doc_type: str, original_id: str):
    """특정 문서를 검색해서 존재하는지 확인"""
    logger.info(f"=== 특정 문서 검색 테스트 ===")
    logger.info(f"검색 조건: tenant_id={tenant_id}, doc_type={doc_type}, original_id={original_id}")
    
    try:
        # get_by_id로 직접 조회
        result = vector_db.get_by_id(
            original_id_value=original_id,
            doc_type=doc_type,
            tenant_id=tenant_id
        )
        
        if result:
            logger.info(f"✅ 문서 발견: {result.get('id')} (doc_type: {result.get('doc_type')})")
            return True
        else:
            logger.warning(f"❌ 문서를 찾을 수 없음")
            return False
            
    except Exception as e:
        logger.error(f"문서 검색 실패: {e}")
        return False


async def test_vector_search_with_real_data(tenant_id: str):
    """실제 데이터로 벡터 검색 테스트"""
    logger.info(f"=== 실제 데이터로 벡터 검색 테스트 ===")
    logger.info(f"테넌트 ID: {tenant_id}")
    
    # 더미 임베딩 생성 (1536차원)
    dummy_embedding = [0.1] * 1536
    
    # 티켓 검색 테스트
    logger.info("1. 티켓 검색 테스트 (doc_type=ticket)")
    try:
        ticket_results = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=5,
            tenant_id=tenant_id,
            doc_type="ticket"
        )
        
        logger.info(f"티켓 검색 결과: {len(ticket_results.get('results', []))}개")
        for i, result in enumerate(ticket_results.get('results', [])[:3]):  # 첫 3개만 표시
            logger.info(f"  티켓 [{i+1}]: ID={result.get('original_id')}, doc_type={result.get('doc_type')}")
    
    except Exception as e:
        logger.error(f"티켓 검색 실패: {e}")
    
    # 아티클 검색 테스트
    logger.info("2. 아티클 검색 테스트 (doc_type=article)")
    try:
        article_results = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=5,
            tenant_id=tenant_id,
            doc_type="article"
        )
        
        logger.info(f"아티클 검색 결과: {len(article_results.get('results', []))}개")
        for i, result in enumerate(article_results.get('results', [])[:3]):  # 첫 3개만 표시
            logger.info(f"  아티클 [{i+1}]: ID={result.get('original_id')}, doc_type={result.get('doc_type')}")
    
    except Exception as e:
        logger.error(f"아티클 검색 실패: {e}")
    
    # KB 검색 테스트 (레거시 호환성)
    logger.info("3. KB 검색 테스트 (doc_type=kb, 레거시 호환성)")
    try:
        kb_results = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=5,
            tenant_id=tenant_id,
            doc_type="kb"
        )
        
        logger.info(f"KB 검색 결과: {len(kb_results.get('results', []))}개")
        for i, result in enumerate(kb_results.get('results', [])[:3]):  # 첫 3개만 표시
            logger.info(f"  KB [{i+1}]: ID={result.get('original_id')}, doc_type={result.get('doc_type')}")
    
    except Exception as e:
        logger.error(f"KB 검색 실패: {e}")


async def main():
    """메인 테스트 함수"""
    logger.info("🔍 실제 데이터를 사용한 벡터DB 검색 테스트 시작")
    logger.info("실제 아티클 ID: 5000875040")
    logger.info("실제 티켓 ID: 104")
    logger.info("=" * 60)
    
    # 1. 데이터 존재 여부 확인
    tenant_ids, doc_types = await check_data_exists()
    
    if not tenant_ids:
        logger.error("❌ 벡터DB에 데이터가 없거나 조회할 수 없습니다.")
        return
    
    # 첫 번째 tenant_id 사용
    primary_tenant_id = tenant_ids[0]
    logger.info(f"주요 테넌트 ID 사용: {primary_tenant_id}")
    logger.info("=" * 60)
    
    # 2. 특정 문서들 검색 테스트
    if "ticket" in doc_types or "티켓" in str(doc_types):
        await test_specific_document_search(primary_tenant_id, "ticket", "104")
    
    if "article" in doc_types or "kb" in doc_types:
        # article 타입으로 시도
        found = await test_specific_document_search(primary_tenant_id, "article", "5000875040")
        if not found:
            # kb 타입으로 재시도 (레거시)
            await test_specific_document_search(primary_tenant_id, "kb", "5000875040")
    
    logger.info("=" * 60)
    
    # 3. 벡터 검색 테스트
    await test_vector_search_with_real_data(primary_tenant_id)
    
    logger.info("=" * 60)
    logger.info("🎉 실제 데이터 검색 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
