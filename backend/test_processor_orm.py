#!/usr/bin/env python3
"""
Processor ORM 통합 테스트

실제 processor.py에서 ORM 마이그레이션 레이어가 잘 작동하는지 테스트합니다.
"""

import os
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 환경변수 먼저 설정
os.environ['USE_ORM'] = 'true'
os.environ['ENVIRONMENT'] = 'development'

from core.ingest.integrator import create_integrated_ticket_object
from core.migration_layer import store_integrated_object_with_migration
from core.database.manager import get_db_manager
from core.repositories.integrated_object_repository import IntegratedObjectRepository

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_processor_orm_integration():
    """실제 processor 로직에서 ORM 통합 테스트"""
    
    try:
        logger.info("🚀 Processor ORM 통합 테스트 시작")
        
        company_id = "processor_test_company"
        platform = "freshdesk"
        
        # 테이블 생성
        db_manager = get_db_manager(company_id)
        db_manager.create_database()
        logger.info("✅ 데이터베이스 테이블 생성 완료")
        
        # 기존 테스트 데이터 정리
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            existing_objs = repo.get_by_company(company_id)
            for obj in existing_objs:
                session.delete(obj)
            session.commit()
            logger.info(f"🧹 기존 테스트 데이터 {len(existing_objs)}개 정리 완료")
        
        # 실제 Freshdesk 티켓 데이터 모사 (processor.py에서 사용하는 형태)
        mock_ticket = {
            'id': 12345,
            'subject': 'Processor ORM Test Ticket',
            'description': 'This is a test ticket for processor ORM integration',
            'status': 2,
            'priority': 1,
            'type': 'Question',
            'created_at': '2025-06-26T00:35:00Z',
            'updated_at': '2025-06-26T00:35:00Z',
            'requester_id': 67890,
            'responder_id': 11111,
            'source': 2,
            'company_id': 22222,
            'group_id': 33333,
            'fr_escalated': False,
            'spam': False,
            'email_config_id': None,
            'fwd_emails': [],
            'reply_cc_emails': [],
            'cc_emails': [],
            'is_escalated': False,
            'fr_due_by': '2025-06-27T00:35:00Z',
            'due_by': '2025-06-27T00:35:00Z',
            'conversations': [
                {
                    'id': 111,
                    'body': '<div>Initial customer inquiry</div>',
                    'body_text': 'Initial customer inquiry',
                    'incoming': True,
                    'private': False,
                    'user_id': 67890,
                    'support_email': 'support@test.com',
                    'source': 0,
                    'created_at': '2025-06-26T00:35:00Z',
                    'updated_at': '2025-06-26T00:35:00Z',
                    'attachments': []
                },
                {
                    'id': 222,
                    'body': '<div>Agent response</div>',
                    'body_text': 'Agent response',
                    'incoming': False,
                    'private': False,
                    'user_id': 11111,
                    'support_email': 'support@test.com',
                    'source': 0,
                    'created_at': '2025-06-26T00:36:00Z',
                    'updated_at': '2025-06-26T00:36:00Z',
                    'attachments': []
                }
            ]
        }
        
        logger.info("=" * 60)
        logger.info("🎯 1단계: 통합 객체 생성 (integrator.py 로직)")
        
        # create_integrated_ticket_object 함수 사용 (실제 processor.py에서 사용하는 방식)
        integrated_ticket = create_integrated_ticket_object(
            ticket=mock_ticket,
            company_id=company_id
        )
        
        logger.info(f"✅ 통합 티켓 객체 생성 완료")
        logger.info(f"   - ID: {integrated_ticket.get('id')}")
        logger.info(f"   - 제목: {integrated_ticket.get('subject')}")
        logger.info(f"   - 대화 수: {len(integrated_ticket.get('conversations', []))}")
        logger.info(f"   - 첨부파일 수: {len(integrated_ticket.get('all_attachments', []))}")
        
        logger.info("=" * 60)
        logger.info("🎯 2단계: 마이그레이션 레이어 저장 (processor.py 로직)")
        
        # store_integrated_object_with_migration 함수 사용 (실제 processor.py에서 사용하는 방식)
        success = store_integrated_object_with_migration(
            integrated_object=integrated_ticket,
            company_id=company_id,
            platform=platform
        )
        
        if success:
            logger.info("✅ 마이그레이션 레이어 저장 성공")
        else:
            logger.error("❌ 마이그레이션 레이어 저장 실패")
            return False
        
        logger.info("=" * 60)
        logger.info("🎯 3단계: ORM Repository로 검증")
        
        # 새로운 세션으로 저장된 데이터 확인
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 전체 객체 조회
            all_objects = repo.get_by_company(company_id)
            logger.info(f"📊 저장된 전체 객체 수: {len(all_objects)}")
            
            # 특정 객체 조회
            found_obj = repo.get_by_original_id(
                company_id=company_id,
                original_id=str(mock_ticket['id'])
            )
            
            if found_obj:
                logger.info(f"✅ 저장된 티켓 확인: {found_obj.original_id}")
                logger.info(f"   - DB ID: {found_obj.id}")
                logger.info(f"   - 제목: {found_obj.tenant_metadata.get('subject') if found_obj.tenant_metadata else 'N/A'}")
                logger.info(f"   - 객체 타입: {found_obj.object_type}")
                logger.info(f"   - 플랫폼: {found_obj.platform}")
                logger.info(f"   - 생성일: {found_obj.created_at}")
                
                # 메타데이터 확인
                if found_obj.tenant_metadata:
                    metadata = found_obj.tenant_metadata
                    logger.info(f"   - 대화 수: {metadata.get('conversation_count', 0)}")
                    logger.info(f"   - 첨부파일 수: {metadata.get('attachment_count', 0)}")
                    logger.info(f"   - 상태: {metadata.get('status')}")
                    logger.info(f"   - 우선순위: {metadata.get('priority')}")
                
            else:
                logger.error("❌ 저장된 티켓을 찾을 수 없음")
                return False
        
        logger.info("=" * 60)
        logger.info("🎉 Processor ORM 통합 테스트 성공!")
        logger.info("✅ 실제 프로덕션 환경에서 사용할 준비 완료")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Processor ORM 통합 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_processor_orm_integration()
    if success:
        logger.info("\n🎊 축하합니다! Processor ORM 통합이 성공적으로 완료되었습니다!")
        logger.info("📝 이제 실제 Freshdesk 데이터 수집에서 ORM을 사용할 수 있습니다.")
        exit(0)
    else:
        logger.error("\n💥 Processor ORM 통합 테스트 실패!")
        exit(1)
