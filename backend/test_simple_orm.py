#!/usr/bin/env python3
"""
단순화된 ORM 테스트 - 문제 해결용
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_simple_orm():
    """간단한 ORM 테스트"""
    
    try:
        company_id = "simple_test_company"
        original_id = "simple_test_123"
        
        logger.info("🚀 간단한 ORM 테스트 시작")
        
        # DB 매니저 생성
        db_manager = get_db_manager(company_id)
        logger.info(f"📁 DB 파일 경로: {db_manager.database_url}")
        
        # 테이블 생성
        db_manager.create_database()
        logger.info("✅ 데이터베이스 스키마 생성 완료")
        
        # 1단계: 데이터 저장
        logger.info("=" * 50)
        logger.info("💾 1단계: 데이터 저장")
        
        test_data = {
            'original_id': original_id,
            'company_id': company_id,
            'platform': 'freshdesk',
            'object_type': 'integrated_ticket',
            'original_data': {'test': 'simple_data'},
            'integrated_content': 'Simple test content',
            'tenant_metadata': {'simple': True}
        }
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            created_obj = repo.create(test_data)
            logger.info(f"✅ 객체 생성: ID={created_obj.id}, original_id={created_obj.original_id}")
        
        # 2단계: 즉시 새 세션으로 조회
        logger.info("=" * 50)
        logger.info("🔍 2단계: 새 세션으로 즉시 조회")
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            found_obj = repo.get_by_original_id(
                company_id=company_id,
                original_id=original_id
            )
            
            if found_obj:
                logger.info(f"✅ 객체 조회 성공: {found_obj.original_id}")
                logger.info(f"   - DB ID: {found_obj.id}")
                logger.info(f"   - 회사 ID: {found_obj.company_id}")
            else:
                logger.error("❌ 객체 조회 실패")
                return False
        
        # 3단계: 완전히 새로운 DB 매니저로 조회
        logger.info("=" * 50)
        logger.info("🔄 3단계: 새로운 DB 매니저로 조회")
        
        new_db_manager = get_db_manager(company_id)
        with new_db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 전체 객체 수 확인
            all_objects = repo.get_by_company(company_id)
            logger.info(f"📊 전체 객체 수: {len(all_objects)}")
            
            # 특정 객체 조회
            found_obj = repo.get_by_original_id(
                company_id=company_id,
                original_id=original_id
            )
            
            if found_obj:
                logger.info(f"✅ 새 매니저로 조회 성공: {found_obj.original_id}")
                return True
            else:
                logger.error("❌ 새 매니저로 조회 실패")
                
                # 디버깅: 모든 객체 나열
                if all_objects:
                    logger.info("📋 저장된 모든 객체:")
                    for obj in all_objects:
                        logger.info(f"   - ID: {obj.id}, original_id: {obj.original_id}, company_id: {obj.company_id}")
                else:
                    logger.error("⚠️ 저장된 객체가 전혀 없음")
                
                return False
        
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_simple_orm()
    if success:
        logger.info("🎉 간단한 ORM 테스트 성공!")
        exit(0)
    else:
        logger.error("💥 간단한 ORM 테스트 실패!")
        exit(1)
