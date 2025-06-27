#!/usr/bin/env python3
"""
데이터 수집 → ORM 저장 과정 추적 스크립트

실제 데이터 수집 과정에서 어디서 문제가 발생하는지 추적합니다.
"""

import os
import sys
import logging

# 백엔드 경로 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

# .env 파일 로딩 (중요!)
try:
    from dotenv import load_dotenv
    env_path = '/Users/alan/GitHub/project-a/backend/.env'
    load_dotenv(env_path, override=True)
    print(f"✅ .env 파일 로딩: {env_path}")
except ImportError:
    print("⚠️ python-dotenv가 설치되지 않음")
except Exception as e:
    print(f"❌ .env 파일 로딩 실패: {e}")

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def trace_data_collection_process():
    """데이터 수집 → ORM 저장 과정 추적"""
    
    logger.info("🔍 데이터 수집 → ORM 저장 과정 추적 시작")
    
    # 1. 환경변수 확인
    logger.info("\n⚙️ 환경변수 확인:")
    use_orm = os.getenv('USE_ORM', 'false').lower() == 'true'
    logger.info(f"   USE_ORM: {os.getenv('USE_ORM')} → 계산 결과: {use_orm}")
    
    # 2. Migration Layer 초기화 테스트
    logger.info("\n🔧 Migration Layer 초기화:")
    try:
        from core.migration_layer import get_migration_layer
        migration_layer = get_migration_layer()
        logger.info(f"   ✅ Migration Layer 초기화 성공: use_orm={migration_layer.use_orm}")
    except Exception as e:
        logger.error(f"   ❌ Migration Layer 초기화 실패: {e}")
        return False
    
    # 3. ORM DB 매니저 테스트
    logger.info("\n🗄️ ORM DB 매니저 테스트:")
    try:
        from core.database.manager import get_db_manager
        db_manager = get_db_manager(tenant_id="wedosoft")
        logger.info(f"   ✅ DB 매니저 생성: {db_manager.database_url}")
        
        # 테이블 생성 확인
        db_manager.create_database()
        logger.info("   ✅ 테이블 생성/검증 완료")
        
    except Exception as e:
        logger.error(f"   ❌ DB 매니저 테스트 실패: {e}")
        return False
    
    # 4. 실제 저장 과정 시뮬레이션
    logger.info("\n💾 실제 저장 과정 시뮬레이션:")
    
    # 실제 데이터와 유사한 구조
    test_integrated_object = {
        'id': 'test_trace_123',
        'object_type': 'integrated_ticket',
        'integrated_text': 'Test content for tracing',
        'summary': 'Test summary',
        'subject': 'Test Subject for Tracing',
        'status': 'Open',
        'priority': 1,
        'created_at': '2025-06-27T08:00:00Z',
        'all_attachments': [],
        'conversations': [
            {
                'id': 'conv_1',
                'body_text': 'Test conversation content',
                'from_email': 'test@example.com',
                'private': False,
                'attachments': []
            }
        ]
    }
    
    try:
        logger.info("   🔄 Migration Layer를 통한 저장 시도...")
        result = migration_layer.store_integrated_object(
            integrated_object=test_integrated_object,
            tenant_id="wedosoft",
            platform="freshdesk"
        )
        
        if result:
            logger.info("   ✅ Migration Layer 저장 성공")
        else:
            logger.error("   ❌ Migration Layer 저장 실패")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ 저장 과정에서 오류: {e}")
        import traceback
        logger.error(f"   스택 트레이스: {traceback.format_exc()}")
        return False
    
    # 5. 저장 후 검증
    logger.info("\n🔍 저장 후 검증:")
    try:
        from core.repositories.integrated_object_repository import IntegratedObjectRepository
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 방금 저장한 객체 조회
            stored_obj = repo.get_by_original_id(
                tenant_id="wedosoft",
                original_id="test_trace_123",
                object_type="integrated_ticket",
                platform="freshdesk"
            )
            
            if stored_obj:
                logger.info(f"   ✅ 저장된 객체 확인: ID={stored_obj.id}, Original_ID={stored_obj.original_id}")
                logger.info(f"   📋 객체 정보: tenant_id={stored_obj.tenant_id}, platform={stored_obj.platform}")
            else:
                logger.error("   ❌ 저장된 객체를 찾을 수 없음")
                return False
            
            # 전체 객체 수 확인
            all_objects = repo.get_by_company(tenant_id="wedosoft")
            logger.info(f"   📊 전체 통합 객체 수: {len(all_objects)}개")
            
    except Exception as e:
        logger.error(f"   ❌ 저장 검증 실패: {e}")
        return False
    
    # 6. 요약 생성 로직에서 사용되는 조회 방법 테스트
    logger.info("\n📝 요약 생성 로직 조회 방법 테스트:")
    try:
        # 요약 생성에서 사용하는 것과 동일한 방법으로 조회
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 요약이 없는 객체들 조회 (요약 생성 대상)
            objects_for_summary = repo.get_by_company(
                tenant_id="wedosoft",
                object_type="integrated_ticket"
            )
            
            # 요약이 필요한 객체 필터링
            need_summary = [obj for obj in objects_for_summary if not obj.summary]
            
            logger.info(f"   📊 요약 생성 대상 객체: {len(need_summary)}개")
            logger.info(f"   📊 전체 티켓 객체: {len(objects_for_summary)}개")
            
            if need_summary:
                logger.info("   ✅ 요약 생성 대상 객체가 있음 - 요약 생성이 진행되어야 함")
                for obj in need_summary[:3]:  # 최대 3개만 표시
                    logger.info(f"      - ID: {obj.original_id}, Summary: {obj.summary is not None}")
            else:
                logger.warning("   ⚠️ 요약 생성 대상 객체가 없음 - 이것이 문제 원인일 수 있음")
            
    except Exception as e:
        logger.error(f"   ❌ 요약 생성 로직 테스트 실패: {e}")
        return False
    
    # 7. 실제 processor.py에서 사용하는 함수 호출 추적
    logger.info("\n🔄 Processor.py 함수 호출 추적:")
    try:
        from core.ingest.storage import store_integrated_object_with_migration
        
        logger.info("   🔍 store_integrated_object_with_migration 함수 호출...")
        result = store_integrated_object_with_migration(
            integrated_object=test_integrated_object,
            tenant_id="wedosoft",
            platform="freshdesk"
        )
        
        if result:
            logger.info("   ✅ store_integrated_object_with_migration 성공")
        else:
            logger.error("   ❌ store_integrated_object_with_migration 실패")
            
    except Exception as e:
        logger.error(f"   ❌ Processor 함수 호출 오류: {e}")
        import traceback
        logger.error(f"   스택 트레이스: {traceback.format_exc()}")
    
    logger.info("\n🎉 데이터 수집 → ORM 저장 과정 추적 완료!")
    return True

if __name__ == "__main__":
    success = trace_data_collection_process()
    if success:
        print("\n✅ 데이터 수집 → ORM 저장 과정 추적 완료!")
    else:
        print("\n❌ 데이터 수집 → ORM 저장 과정에서 문제 발견!")
    
    sys.exit(0 if success else 1)
