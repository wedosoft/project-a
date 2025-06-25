#!/usr/bin/env python3
"""
마이그레이션 레이어 디버깅 스크립트
"""

import os
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """마이그레이션 레이어 디버깅"""
    
    # 환경변수 설정
    os.environ['USE_ORM'] = 'true'
    print(f"🔧 USE_ORM 환경변수: {os.getenv('USE_ORM')}")
    
    # 마이그레이션 레이어 import
    from core.migration_layer import get_migration_layer, store_integrated_object_with_migration
    
    # 마이그레이션 레이어 인스턴스 확인
    migration_layer = get_migration_layer()
    print(f"🔍 마이그레이션 레이어 use_orm: {migration_layer.use_orm}")
    
    # 간단한 테스트 객체
    test_object = {
        'id': 'debug_test_789',
        'object_type': 'integrated_ticket',
        'subject': 'Debug Test',
        'integrated_text': 'Debug test content',
        'all_attachments': [],
        'conversations': []
    }
    
    # 저장 테스트
    print("💾 마이그레이션 레이어 저장 테스트...")
    success = store_integrated_object_with_migration(
        integrated_object=test_object,
        company_id='debug_test_company',
        platform='freshdesk'
    )
    
    if success:
        print("✅ 저장 성공!")
        
        # 조회 테스트
        from core.database.manager import get_db_manager
        from core.repositories.integrated_object_repository import IntegratedObjectRepository
        
        db_manager = get_db_manager("debug_test_company")
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            found_obj = repo.get_by_original_id(
                company_id='debug_test_company',
                original_id='debug_test_789'
            )
            
            if found_obj:
                print(f"✅ 조회 성공: {found_obj.original_id}")
            else:
                print("❌ 조회 실패")
    else:
        print("❌ 저장 실패")

if __name__ == "__main__":
    main()
