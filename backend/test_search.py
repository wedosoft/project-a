#!/usr/bin/env python
"""
벡터 DB 검색 테스트 스크립트
"""

import sys
import random
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# 현재 디렉토리를 모듈 검색 경로에 추가
sys.path.insert(0, '.')
from vectordb import vector_db

# 랜덤 임베딩 생성
dummy_embedding = [random.random() for _ in range(1536)]

try:
    # 검색 실행
    results = vector_db.search(
        query_embedding=dummy_embedding,
        top_k=1,
        company_id='default'
    )
    
    # 결과 출력
    print(f'검색 결과 개수: {len(results.get("documents", []))}')
    
    if results and "documents" in results and len(results["documents"]) > 0:
        print(f'첫 번째 결과 ID: {results["ids"][0]}')
        print(f'첫 번째 결과 원본 ID: {results["metadatas"][0].get("original_id", "N/A")}')
except Exception as e:
    print(f'검색 오류: {e}')
