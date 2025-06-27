#!/usr/bin/env python3
"""
ORM 호환성 테스트 스크립트

migration_layer.py의 ORM 기능을 테스트하고 문제를 진단합니다.
"""

import os
import sys
import logging

# 백엔드 경로 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

# 환경변수 설정
os.environ['USE_ORM'] = 'true'
os.environ['LOG_LEVEL'] = 'INFO'

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_orm_compatibility():
    """ORM 호환성 테스트"""
    
    try:
        logger.info("🧪 ORM 호환성 테스트 시작")
        
        # 1. 환경변수 확인
        use_orm = os.getenv('USE_ORM', 'false').lower() == 'true'
        logger.info(f"📋 USE_ORM 환경변수: {use_orm}")
        
        # 2. 마이그레이션 레이어 초기화
        from core.migration_layer import get_migration_layer
        migration_layer = get_migration_layer()
        logger.info(f"✅ 마이그레이션 레이어 초기화 완료: use_orm={migration_layer.use_orm}")
        
        # 3. 데이터베이스 매니저 테스트
        from core.database.manager import get_db_manager
        db_manager = get_db_manager(tenant_id="test_company")
        logger.info(f"✅ DB 매니저 생성: {db_manager.database_url}")
        
        # 4. 테이블 생성 테스트
        try:
            db_manager.create_database()
            logger.info("✅ 데이터베이스 테이블 생성 성공")
        except Exception as e:
            logger.error(f"❌ 테이블 생성 실패: {e}")
            return False
        
        # 5. 테이블 존재 확인
        from sqlalchemy import inspect
        inspector = inspect(db_manager.engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"📋 생성된 테이블 목록: {existing_tables}")
        
        if 'integrated_objects' in existing_tables:
            logger.info("✅ integrated_objects 테이블 확인됨")
        else:
            logger.error("❌ integrated_objects 테이블이 없음")
            return False
        
        # 6. 테이블 스키마 확인
        columns = inspector.get_columns('integrated_objects')
        column_names = [col['name'] for col in columns]
        logger.info(f"📋 integrated_objects 컬럼: {column_names}")
        
        # 7. ORM 모델 테스트
        try:
            with db_manager.get_session() as session:
                from core.repositories.integrated_object_repository import IntegratedObjectRepository
                repo = IntegratedObjectRepository(session)
                
                # 기존 데이터 조회 테스트 (빈 결과라도 성공)
                objects = repo.get_by_company(tenant_id="test_company")
                logger.info(f"✅ Repository 조회 성공: {len(objects)}개 객체")
                
        except Exception as e:
            logger.error(f"❌ Repository 테스트 실패: {e}")
            return False
        
        # 8. 마이그레이션 레이어 저장 테스트
        test_object = {
            'id': 'test_123',
            'object_type': 'integrated_ticket',
            'integrated_text': 'Test content',
            'summary': 'Test summary',
            'subject': 'Test Subject',
            'status': 'Open',
            'created_at': '2025-06-27T00:00:00Z'
        }
        
        try:
            result = migration_layer.store_integrated_object(
                integrated_object=test_object,
                tenant_id="test_company",
                platform="freshdesk"
            )
            
            if result:
                logger.info("✅ 마이그레이션 레이어 저장 성공")
            else:
                logger.error("❌ 마이그레이션 레이어 저장 실패")
                return False
                
        except Exception as e:
            logger.error(f"❌ 마이그레이션 레이어 테스트 실패: {e}")
            return False
        
        logger.info("🎉 모든 ORM 호환성 테스트 통과!")
        return True
        
    except Exception as e:
        logger.error(f"❌ ORM 호환성 테스트 중 오류: {e}")
        return False

if __name__ == "__main__":
    success = test_orm_compatibility()
    if success:
        print("\n✅ ORM 호환성 문제가 해결되었습니다!")
    else:
        print("\n❌ ORM 호환성 문제가 여전히 존재합니다.")
    
    sys.exit(0 if success else 1)
