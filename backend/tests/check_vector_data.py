#!/usr/bin/env python3
"""
벡터DB 데이터 확인 스크립트
실제 데이터의 tenant_id와 doc_type을 확인하여 올바른 테스트를 위한 정보를 제공합니다.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.database.vectordb import vector_db

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_vector_data():
    """벡터DB 실제 데이터 확인"""
    
    print("=" * 60)
    print("=== 벡터DB 데이터 확인 ===")
    print("=" * 60)
    
    try:
        # 1. 전체 문서 수 확인
        total_count = vector_db.count()
        logger.info(f"총 문서 수: {total_count}개")
        
        if total_count == 0:
            logger.warning("벡터DB에 데이터가 없습니다.")
            return
        
        # 2. 샘플 데이터 조회 (처음 10개)
        logger.info("샘플 데이터 조회 중...")
        
        scroll_result = vector_db.client.scroll(
            collection_name=vector_db.collection_name,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0] if scroll_result else []
        
        if not points:
            logger.warning("샘플 데이터를 조회할 수 없습니다.")
            return
            
        print(f"\n총 {total_count}개 문서 중 처음 {len(points)}개 샘플:")
        print("-" * 60)
        
        tenant_ids = set()
        doc_types = set()
        platforms = set()
        
        for i, point in enumerate(points):
            payload = point.payload
            
            tenant_id = payload.get("tenant_id", "없음")
            doc_type = payload.get("doc_type", "없음") 
            platform = payload.get("platform", "없음")
            original_id = payload.get("original_id", "없음")
            object_type = payload.get("object_type", "없음")
            
            # 레거시 필드들
            legacy_type = payload.get("type", "없음")
            source_type = payload.get("source_type", "없음")
            status = payload.get("status", "없음")
            
            tenant_ids.add(tenant_id)
            doc_types.add(doc_type)
            platforms.add(platform)
            
            print(f"문서 #{i+1}:")
            print(f"  - ID: {point.id}")
            print(f"  - tenant_id: {tenant_id}")
            print(f"  - platform: {platform}")
            print(f"  - doc_type: {doc_type}")
            print(f"  - original_id: {original_id}")
            print(f"  - object_type: {object_type}")
            print(f"  - 레거시 필드:")
            print(f"    - type: {legacy_type}")
            print(f"    - source_type: {source_type}")
            print(f"    - status: {status}")
            print()
        
        # 3. 통계 정보
        print("=" * 60)
        print("=== 데이터 통계 ===")
        print(f"발견된 tenant_id 목록: {sorted(tenant_ids)}")
        print(f"발견된 doc_type 목록: {sorted(doc_types)}")
        print(f"발견된 platform 목록: {sorted(platforms)}")
        
        # 4. 각 tenant_id별 문서 수 확인
        print("\n=== tenant_id별 문서 수 ===")
        for tenant_id in sorted(tenant_ids):
            if tenant_id != "없음":
                count = vector_db.count(tenant_id=tenant_id)
                print(f"  - {tenant_id}: {count}개")
        
        # 5. doc_type별 문서 수 확인 (메모리 스캔)
        print("\n=== doc_type별 문서 수 (전체 스캔) ===")
        doc_type_counts = {}
        
        # 전체 데이터 스캔
        offset = 0
        batch_size = 100
        
        while True:
            batch_result = vector_db.client.scroll(
                collection_name=vector_db.collection_name,
                offset=offset,
                limit=batch_size,
                with_payload=True,
                with_vectors=False
            )
            
            batch_points = batch_result[0] if batch_result else []
            if not batch_points:
                break
                
            for point in batch_points:
                payload = point.payload
                doc_type = payload.get("doc_type", "없음")
                
                # 레거시 지원
                if doc_type == "없음":
                    legacy_type = payload.get("type")
                    if legacy_type == 1 or legacy_type == "1":
                        doc_type = "kb"
                    elif legacy_type == "ticket":
                        doc_type = "ticket"
                    else:
                        doc_type = f"레거시_{legacy_type}"
                
                doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1
            
            offset += len(batch_points)
        
        for doc_type, count in sorted(doc_type_counts.items()):
            print(f"  - {doc_type}: {count}개")
        
        # 6. 테스트 추천
        print("\n=" * 60)
        print("=== 테스트 추천 설정 ===")
        
        # 가장 많은 데이터를 가진 tenant_id 찾기
        valid_tenant_ids = [t for t in tenant_ids if t != "없음"]
        if valid_tenant_ids:
            recommended_tenant = sorted(valid_tenant_ids)[0]  # 첫 번째 tenant_id
            print(f"추천 tenant_id: '{recommended_tenant}'")
            
            # 해당 tenant의 데이터 확인
            tenant_count = vector_db.count(tenant_id=recommended_tenant)
            print(f"'{recommended_tenant}' 문서 수: {tenant_count}개")
            
            # 각 doc_type별 검색 테스트 제안
            print(f"\n테스트용 검색 명령어:")
            print(f"  - 티켓 검색: doc_type='ticket', tenant_id='{recommended_tenant}'")
            print(f"  - 아티클 검색: doc_type='article', tenant_id='{recommended_tenant}'")
            
            if "kb" in doc_type_counts:
                print(f"  - KB 검색 (레거시): doc_type='kb', tenant_id='{recommended_tenant}'")
        else:
            print("유효한 tenant_id를 찾을 수 없습니다.")
            
    except Exception as e:
        logger.error(f"데이터 확인 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(check_vector_data())
