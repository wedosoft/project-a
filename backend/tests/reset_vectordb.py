#!/usr/bin/env python3
"""
벡터DB 초기화 스크립트

기존 벡터DB를 완전히 삭제하고 새로운 최적화된 메타데이터 구조로 재생성합니다.
39개 필드 → 6개 필수 필드 + tenant_metadata JSON으로 최적화
"""

import logging
import sys
from pathlib import Path

# 백엔드 루트 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.database.vectordb import QdrantAdapter
from core.config import get_settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_vector_database():
    """벡터DB 초기화 (백업 없이 완전 삭제)"""
    
    try:
        logger.info("🔄 벡터DB 초기화 시작")
        
        # QdrantAdapter 인스턴스 생성
        settings = get_settings()
        adapter = QdrantAdapter()
        
        # 현재 컬렉션 정보 확인
        logger.info("📊 현재 벡터DB 상태 확인")
        try:
            collection_info = adapter.get_collection_info()
            logger.info(f"  - 컬렉션: {collection_info.get('name')}")
            logger.info(f"  - 문서 수: {collection_info.get('points_count', 0):,}개")
            logger.info(f"  - 벡터 차원: {collection_info.get('vector_size')}")
            
            # 샘플 메타데이터 확인
            points = adapter.client.scroll('documents', limit=1)[0]
            if points:
                sample_payload = points[0].payload
                logger.info(f"  - 현재 메타데이터 필드 수: {len(sample_payload)}개")
                logger.info(f"  - 필드 목록: {list(sample_payload.keys())}")
        except Exception as e:
            logger.warning(f"현재 상태 확인 실패: {e}")
        
        # 컬렉션 완전 삭제 (백업 없이)
        logger.info("🗑️ 기존 컬렉션 삭제 중...")
        success = adapter.reset_collection(
            confirm=True, 
            create_backup=False  # 백업 생성하지 않음
        )
        
        if success:
            logger.info("✅ 벡터DB 초기화 완료!")
            
            # 새로운 컬렉션 정보 확인
            new_info = adapter.get_collection_info()
            logger.info("📊 새로운 벡터DB 상태:")
            logger.info(f"  - 컬렉션: {new_info.get('name')}")
            logger.info(f"  - 문서 수: {new_info.get('points_count', 0):,}개")
            logger.info(f"  - 벡터 차원: {new_info.get('vector_size')}")
            
            logger.info("🎯 이제 새로운 최적화된 메타데이터 구조를 사용합니다:")
            logger.info("  필수 필드 (6개):")
            logger.info("    - tenant_id: 테넌트 ID")
            logger.info("    - platform: 플랫폼 (freshdesk 등)")
            logger.info("    - doc_type: 문서 타입 (ticket/kb)")
            logger.info("    - original_id: 원본 ID")
            logger.info("    - object_type: 객체 타입")
            logger.info("    - summary: 요약 텍스트")
            logger.info("  확장 메타데이터:")
            logger.info("    - tenant_metadata: JSON 객체 (나머지 모든 필드)")
            
            return True
        else:
            logger.error("❌ 벡터DB 초기화 실패")
            return False
            
    except Exception as e:
        logger.error(f"❌ 벡터DB 초기화 중 오류 발생: {e}")
        return False

def main():
    """메인 함수"""
    logger.info("=" * 60)
    logger.info("🚀 벡터DB 메타데이터 최적화 초기화 스크립트")
    logger.info("=" * 60)
    
    # 사용자 확인
    print("\n⚠️  주의: 이 작업은 기존 벡터DB의 모든 데이터를 삭제합니다.")
    print("기존 데이터는 복구할 수 없습니다.")
    print("\n계속하시겠습니까? (y/N): ", end="")
    
    try:
        user_input = input().strip().lower()
        if user_input not in ['y', 'yes']:
            logger.info("사용자가 작업을 취소했습니다.")
            return
    except KeyboardInterrupt:
        logger.info("\n사용자가 작업을 취소했습니다.")
        return
    
    # 벡터DB 초기화 실행
    success = reset_vector_database()
    
    if success:
        logger.info("\n🎉 벡터DB 초기화가 성공적으로 완료되었습니다!")
        logger.info("이제 새로운 데이터 수집 시 최적화된 메타데이터 구조가 적용됩니다.")
    else:
        logger.error("\n💥 벡터DB 초기화가 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()
