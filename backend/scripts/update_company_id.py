#!/usr/bin/env python3
"""
Qdrant 컬렉션의 company_id를 default에서 kyexpert로 업데이트하는 스크립트
"""

import logging
import os
import sys
from typing import Any, Dict, List

# 백엔드 모듈 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vectordb import vector_db
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_company_id_from_default_to_kyexpert() -> bool:
    """
    Qdrant 컬렉션의 모든 점들의 company_id를 default에서 kyexpert로 업데이트
    
    Returns:
        성공 여부 (bool)
    """
    try:
        # 현재 collection_name 확인
        collection_name = vector_db.collection_name
        logger.info(f"컬렉션 '{collection_name}' 처리 시작")
        
        # company_id가 "default"인 모든 포인트 조회
        logger.info("company_id가 'default'인 포인트들 검색 중...")
        
        # 필터 조건: company_id = "default"
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value="default")
                )
            ]
        )
        
        # 스크롤로 모든 점들 가져오기
        points_to_update = []
        offset = None
        limit = 100
        total_found = 0
        
        while True:
            # scroll API로 점들 조회
            scroll_result = vector_db.client.scroll(
                collection_name=collection_name,
                scroll_filter=filter_condition,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=True
            )
            
            points, next_offset = scroll_result
            
            if not points:
                break
                
            total_found += len(points)
            logger.info(f"발견된 포인트 수: {len(points)}, 총계: {total_found}")
            
            # 각 포인트의 company_id를 "kyexpert"로 변경
            for point in points:
                # 기존 payload 복사
                updated_payload = dict(point.payload)
                updated_payload["company_id"] = "kyexpert"
                
                # 업데이트할 포인트 구조 생성
                updated_point = PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=updated_payload
                )
                points_to_update.append(updated_point)
            
            # 다음 배치로 이동
            if next_offset is None:
                break
            offset = next_offset
        
        if not points_to_update:
            logger.info("업데이트할 포인트가 없습니다 (company_id='default'인 포인트가 없음)")
            return True
        
        logger.info(f"총 {len(points_to_update)}개 포인트의 company_id를 'default' → 'kyexpert'로 업데이트 중...")
        
        # 배치 단위로 업데이트 (Qdrant upsert 사용)
        batch_size = 100
        for i in range(0, len(points_to_update), batch_size):
            batch = points_to_update[i:i + batch_size]
            
            logger.info(f"배치 {i//batch_size + 1}/{(len(points_to_update) + batch_size - 1)//batch_size} 업데이트 중... ({len(batch)}개 포인트)")
            
            # upsert로 포인트들 업데이트
            vector_db.client.upsert(
                collection_name=collection_name,
                points=batch
            )
        
        logger.info(f"✅ 성공적으로 {len(points_to_update)}개 포인트의 company_id를 업데이트했습니다!")
        
        # 업데이트 후 확인
        logger.info("업데이트 후 확인 중...")
        
        # kyexpert 포인트 수 확인
        kyexpert_filter = Filter(
            must=[
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value="kyexpert")
                )
            ]
        )
        
        kyexpert_scroll = vector_db.client.scroll(
            collection_name=collection_name,
            scroll_filter=kyexpert_filter,
            limit=1,
            with_payload=False,
            with_vectors=False
        )
        
        # count API가 없으므로 전체 스크롤로 개수 확인
        kyexpert_count = 0
        offset = None
        while True:
            scroll_result = vector_db.client.scroll(
                collection_name=collection_name,
                scroll_filter=kyexpert_filter,
                limit=1000,
                offset=offset,
                with_payload=False,
                with_vectors=False
            )
            points, next_offset = scroll_result
            kyexpert_count += len(points)
            if next_offset is None:
                break
            offset = next_offset
        
        logger.info(f"업데이트 후 company_id='kyexpert'인 포인트 수: {kyexpert_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"company_id 업데이트 중 오류 발생: {e}")
        return False

def verify_company_ids() -> Dict[str, int]:
    """
    컬렉션의 company_id별 포인트 수 확인
    
    Returns:
        company_id별 포인트 수 딕셔너리
    """
    try:
        collection_name = vector_db.collection_name
        logger.info(f"컬렉션 '{collection_name}'의 company_id 분포 확인 중...")
        
        company_id_counts = {}
        
        # 전체 포인트 스캔하여 company_id 분포 확인
        offset = None
        limit = 1000
        
        while True:
            scroll_result = vector_db.client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_offset = scroll_result
            
            if not points:
                break
            
            for point in points:
                company_id = point.payload.get("company_id", "unknown")
                company_id_counts[company_id] = company_id_counts.get(company_id, 0) + 1
            
            if next_offset is None:
                break
            offset = next_offset
        
        logger.info("📊 Company ID 분포:")
        for company_id, count in company_id_counts.items():
            logger.info(f"  - {company_id}: {count}개")
        
        return company_id_counts
        
    except Exception as e:
        logger.error(f"company_id 분포 확인 중 오류 발생: {e}")
        return {}

def main():
    """메인 함수"""
    logger.info("🚀 Company ID 업데이트 스크립트 시작")
    
    # 업데이트 전 상태 확인
    logger.info("=== 업데이트 전 상태 ===")
    verify_company_ids()
    
    # 사용자 확인
    response = input("\ncompany_id를 'default' → 'kyexpert'로 업데이트하시겠습니까? (y/N): ")
    if response.lower() != 'y':
        logger.info("업데이트가 취소되었습니다.")
        return
    
    # 업데이트 실행
    logger.info("\n=== 업데이트 실행 ===")
    success = update_company_id_from_default_to_kyexpert()
    
    if success:
        # 업데이트 후 상태 확인
        logger.info("\n=== 업데이트 후 상태 ===")
        verify_company_ids()
        logger.info("🎉 업데이트가 완료되었습니다!")
    else:
        logger.error("❌ 업데이트가 실패했습니다.")

if __name__ == "__main__":
    main()
