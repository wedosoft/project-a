"""
문서 검색 모듈

이 모듈은 벡터 데이터베이스(Qdrant)를 사용하여 임베딩된 문서를 검색하는 기능을 제공합니다.
쿼리 임베딩과 유사도가 높은 문서를 효율적으로 검색합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import logging
from typing import List, Dict, Any, Optional
from vectordb import vector_db

# 로깅 설정
logger = logging.getLogger(__name__)

# 현재 인증된 사용자의 회사 ID (임시: 실제 구현에서는 인증 시스템에서 제공받아야 함)
DEFAULT_COMPANY_ID = "default"


def get_vector_collection(collection_name: str = "documents") -> Any:
    """
    벡터 데이터베이스 컬렉션을 반환합니다.
    
    Args:
        collection_name: 컬렉션 이름
        
    Returns:
        벡터 데이터베이스 인터페이스 인스턴스
    """
    return vector_db


def retrieve_top_k_docs(query_embedding: List[float], top_k: int, company_id: str = DEFAULT_COMPANY_ID) -> dict:
    """
    쿼리 임베딩을 이용해 VectorDB에서 top_k 문서를 검색합니다.

    Args:
        query_embedding: 검색에 사용할 쿼리 임베딩 벡터
        top_k: 검색할 최대 문서 수
        company_id: 회사 ID (데이터 격리에 사용)

    Returns:
        검색 결과를 포함하는 딕셔너리:
        - documents: 검색된 문서 텍스트 목록
        - metadatas: 검색된 문서의 메타데이터 목록
        - ids: 검색된 문서의 ID 목록
        - distances: 검색된 문서의 유사도 점수 목록
    """
    if not company_id:
        logger.warning("회사 ID가 제공되지 않아 기본 ID를 사용합니다.")
        company_id = DEFAULT_COMPANY_ID
    
    try:
        # 벡터 검색 수행
        results = vector_db.search(
            query_embedding=query_embedding,
            top_k=top_k,
            company_id=company_id
        )
        
        return results
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {str(e)}")
        # 오류 발생시 빈 결과 반환
        return {
            "documents": [],
            "metadatas": [],
            "distances": [],
            "ids": []
        }
