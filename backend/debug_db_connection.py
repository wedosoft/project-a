#!/usr/bin/env python3
"""
데이터베이스 연결 디버깅 스크립트
"""

import os
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.manager import get_db_manager
from core.repositories.integrated_object_repository import IntegratedObjectRepository

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def debug_database_connection():
    """데이터베이스 연결 디버깅"""
    
    try:
        company_id = "debug_test_company"
        
        # 첫 번째 DB 매니저 생성
        logger.info("=" * 50)
        logger.info("🔍 첫 번째 DB 매니저 생성")
        db_manager1 = get_db_manager(company_id)
        logger.info(f"DB URL: {db_manager1.database_url}")
        logger.info(f"Engine: {db_manager1.engine}")
        
        # 두 번째 DB 매니저 생성
        logger.info("=" * 50)
        logger.info("🔍 두 번째 DB 매니저 생성")
        db_manager2 = get_db_manager(company_id)
        logger.info(f"DB URL: {db_manager2.database_url}")
        logger.info(f"Engine: {db_manager2.engine}")
        
        # 같은 엔진인지 확인
        logger.info(f"같은 엔진? {db_manager1.engine is db_manager2.engine}")
        logger.info(f"같은 URL? {db_manager1.database_url == db_manager2.database_url}")
        
        # 테이블 생성
        db_manager1.create_database()
        
        # 첫 번째 세션에서 데이터 저장
        logger.info("=" * 50)
        logger.info("💾 첫 번째 세션에서 데이터 저장")
        
        test_data = {
            'original_id': 'debug_test_123',
            'company_id': company_id,
            'platform': 'freshdesk',
            'object_type': 'integrated_ticket',
            'original_data': {'test': 'debug_data'},
            'integrated_content': 'Debug test content',
            'tenant_metadata': {'debug': True}
        }
        
        with db_manager1.get_session() as session1:
            repo1 = IntegratedObjectRepository(session1)
            created_obj = repo1.create(test_data)
            logger.info(f"✅ 객체 생성: ID={created_obj.id}")
            
            # 같은 세션에서 즉시 조회
            found_in_same_session = repo1.get_by_original_id(
                company_id=company_id,
                original_id='debug_test_123'
            )
            logger.info(f"같은 세션 조회: {'성공' if found_in_same_session else '실패'}")
        
        # 두 번째 세션에서 데이터 조회
        logger.info("=" * 50)
        logger.info("🔍 두 번째 세션에서 데이터 조회")
        
        with db_manager2.get_session() as session2:
            repo2 = IntegratedObjectRepository(session2)
            
            # 모든 객체 조회
            all_objects = repo2.get_by_company(company_id)
            logger.info(f"전체 객체 수: {len(all_objects)}")
            
            # 특정 객체 조회
            found_in_new_session = repo2.get_by_original_id(
                company_id=company_id,
                original_id='debug_test_123'
            )
            logger.info(f"새 세션 조회: {'성공' if found_in_new_session else '실패'}")
        
        # 직접 SQL 쿼리로 확인
        logger.info("=" * 50)
        logger.info("🔍 직접 SQL 쿼리로 데이터 확인")
        
        with db_manager1.get_session() as session:
            result = session.execute("SELECT COUNT(*) FROM integrated_objects")
            count = result.scalar()
            logger.info(f"직접 SQL 카운트: {count}")
            
            if count > 0:
                result = session.execute("SELECT original_id, company_id FROM integrated_objects LIMIT 5")
                rows = result.fetchall()
                for row in rows:
                    logger.info(f"  - {row}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 디버깅 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    debug_database_connection()
