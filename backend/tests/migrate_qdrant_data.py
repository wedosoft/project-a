#!/usr/bin/env python3
"""
Qdrant 데이터 마이그레이션 스크립트

이 스크립트는 Qdrant 데이터베이스에 저장된 문서들의 doc_type과 source_type 필드를
일관성 있게 수정합니다. 특히 KB 문서 검색에 필요한 필드들이 올바르게 설정되도록 합니다.
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("qdrant_migration")

# 환경변수 로드
load_dotenv()

# 벡터 DB 모듈 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database.vectordb import migrate_type_to_doc_type, vector_db


async def run_migration():
    """마이그레이션을 실행합니다."""
    try:
        # 컬렉션 정보 확인
        collection_info = vector_db.get_collection_info()
        logger.info(f"데이터베이스 컬렉션 정보: {collection_info}")

        # 마이그레이션 실행
        logger.info("데이터 마이그레이션 시작...")
        result = migrate_type_to_doc_type()
        
        # 결과 요약
        logger.info("마이그레이션 완료")
        logger.info(f"전체 처리 문서: {result.get('total_processed', 0):,}개")
        logger.info(f"업데이트된 문서: {result.get('migrated_count', 0):,}개")
        logger.info(f"source_type 수정: {result.get('source_type_fixed', 0):,}개")

    except Exception as e:
        logger.error(f"마이그레이션 중 오류 발생: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_migration())
