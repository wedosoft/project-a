#!/usr/bin/env python
"""
Qdrant 벡터 DB 테스트 스크립트

이 스크립트는 Qdrant에 저장된 문서를 확인하고 간단한 검색을 수행합니다.
문자열 ID를 UUID로 변환하는 로직이 제대로 작동하는지 테스트합니다.

사용법: python test_vectordb.py
"""

import os
import sys
import time
import logging
import uuid
import random
from hashlib import md5

# 현재 디렉토리를 모듈 검색 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 벡터 DB 모듈 임포트
import vectordb
from vectordb import QdrantAdapter

# 벡터 DB 초기화
vector_db = vectordb.vector_db

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def test_count():
    """벡터 DB에 저장된 문서 수를 확인합니다."""
    try:
        # 전체 문서 수 확인
        total_count = vector_db.count()
        logger.info(f"전체 문서 수: {total_count}")
        
        # 기본 company_id로 문서 수 확인
        DEFAULT_COMPANY_ID = "default"
        company_count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
        logger.info(f"{DEFAULT_COMPANY_ID} 회사의 문서 수: {company_count}")
        
        return total_count
    except Exception as e:
        logger.error(f"문서 수 확인 중 오류 발생: {e}")
        return 0

def test_id_conversion():
    """문자열 ID를 UUID로 변환하는 로직이 일관되게 작동하는지 테스트합니다."""
    test_ids = ["ticket-1234", "kb-5678", "ticket-abcd", "kb-efgh"]
    
    for id in test_ids:
        # UUID 생성
        uuid_id = uuid.UUID(md5(id.encode()).hexdigest())
        logger.info(f"원본 ID: {id} -> UUID: {uuid_id}")

def test_search():
    """간단한 검색 테스트를 수행합니다."""
    try:
        # 임의의 쿼리 임베딩 생성 (OpenAI API를 사용하지 않고 테스트)
        dummy_embedding = [random.random() for _ in range(1536)]
        
        # 검색 수행
        DEFAULT_COMPANY_ID = "default"
        results = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=3,
            company_id=DEFAULT_COMPANY_ID
        )
        
        # 결과 출력
        if results and "documents" in results and len(results["documents"]) > 0:
            logger.info(f"검색 결과: {len(results['documents'])}개 문서 찾음")
            
            for i, (doc, meta, distance, id) in enumerate(zip(
                results["documents"],
                results["metadatas"],
                results["distances"],
                results["ids"]
            )):
                logger.info(f"결과 #{i+1}:")
                logger.info(f"  ID: {id}")
                logger.info(f"  원본 ID: {meta.get('original_id', 'N/A')}")
                logger.info(f"  유사도 점수: {distance:.4f}")
                logger.info(f"  타입: {meta.get('type', 'N/A')}")
                logger.info(f"  제목: {meta.get('title', 'N/A')}")
                logger.info(f"  내용 미리보기: {doc[:100]}...")
                logger.info("---")
            
            return True
        else:
            logger.warning("검색 결과가 없습니다.")
            return False
            
    except Exception as e:
        logger.error(f"검색 테스트 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    logger.info("Qdrant 벡터 DB 테스트 시작")
    
    # 문서 수 확인
    total_count = test_count()
    
    if total_count > 0:
        # ID 변환 테스트
        test_id_conversion()
        
        # 검색 테스트
        logger.info("검색 테스트 시작")
        search_success = test_search()
        if search_success:
            logger.info("검색 테스트 성공")
        else:
            logger.error("검색 테스트 실패")
    else:
        logger.error("저장된 문서가 없어 검색 테스트를 진행할 수 없습니다.")
    
    logger.info("테스트 완료")
