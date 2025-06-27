#!/usr/bin/env python3
"""
수정된 요약 생성 로직 테스트 스크립트

ORM 기반으로 수정된 요약 생성 함수를 테스트합니다.
"""

import os
import sys
import logging
import asyncio

# 백엔드 경로 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

# .env 파일 로딩
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_summary_generation():
    """수정된 요약 생성 로직 테스트"""
    
    logger.info("🧪 수정된 요약 생성 로직 테스트 시작")
    
    try:
        # 1. 환경변수 확인
        use_orm = os.getenv('USE_ORM', 'false').lower() == 'true'
        logger.info(f"📋 USE_ORM: {use_orm}")
        
        # 2. 요약 생성 함수 import
        from core.ingest.processor import generate_and_store_summaries
        logger.info("✅ 요약 생성 함수 import 성공")
        
        # 3. 요약 생성 실행
        logger.info("🔄 요약 생성 함수 실행...")
        result = await generate_and_store_summaries(
            tenant_id="wedosoft",
            platform="freshdesk",
            force_update=False
        )
        
        # 4. 결과 확인
        logger.info("📊 요약 생성 결과:")
        logger.info(f"   - 성공: {result.get('success_count', 0)}개")
        logger.info(f"   - 실패: {result.get('failure_count', 0)}개")
        logger.info(f"   - 건너뜀: {result.get('skipped_count', 0)}개")
        logger.info(f"   - 전체 처리: {result.get('total_processed', 0)}개")
        logger.info(f"   - 소요시간: {result.get('processing_time', 0):.2f}초")
        
        if result.get('errors'):
            logger.warning("❌ 오류 목록:")
            for error in result['errors'][:3]:
                logger.warning(f"   - {error}")
        
        # 5. 실제 저장된 요약 확인
        logger.info("\n🔍 저장된 요약 확인:")
        from core.database.manager import get_db_manager
        from core.repositories.integrated_object_repository import IntegratedObjectRepository
        
        db_manager = get_db_manager(tenant_id="wedosoft")
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 요약이 있는 객체들 조회
            objects = repo.get_by_company(tenant_id="wedosoft")
            objects_with_summary = [obj for obj in objects if obj.summary and obj.summary.strip()]
            
            logger.info(f"📊 요약이 있는 객체: {len(objects_with_summary)}개")
            
            for obj in objects_with_summary[:3]:  # 최대 3개만 표시
                summary_preview = obj.summary[:100] + "..." if len(obj.summary) > 100 else obj.summary
                logger.info(f"   - {obj.object_type} {obj.original_id}: {summary_preview}")
        
        # 6. 성공 여부 판단
        success = result.get('success_count', 0) > 0 or len(objects_with_summary) > 0
        
        if success:
            logger.info("🎉 요약 생성 로직 테스트 성공!")
        else:
            logger.warning("⚠️ 요약 생성 로직에서 처리된 항목이 없음")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ 요약 생성 로직 테스트 실패: {e}")
        import traceback
        logger.error(f"스택 트레이스: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_summary_generation())
    if success:
        print("\n✅ 수정된 요약 생성 로직 테스트 성공!")
    else:
        print("\n❌ 수정된 요약 생성 로직 테스트 실패!")
    
    sys.exit(0 if success else 1)
