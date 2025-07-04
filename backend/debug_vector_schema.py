#!/usr/bin/env python3
"""
벡터DB 스키마 및 필터링 조건 디버깅
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# 직접 Qdrant 클라이언트로 접근
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv

load_dotenv()

# Qdrant 설정
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

print("=== 벡터DB 디버깅 ===")
print(f"Qdrant URL: {QDRANT_URL}")

try:
    # Qdrant 클라이언트 연결
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=60
    )
    
    collection_name = "documents"
    
    # 1. 컬렉션 정보
    info = client.get_collection(collection_name)
    print(f"컬렉션 '{collection_name}' 정보:")
    print(f"  벡터 수: {info.points_count}")
    print(f"  벡터 차원: {info.config.params.vectors.size}")
    
    # 2. 샘플 데이터 조회 (처음 5개)
    result = client.scroll(
        collection_name=collection_name,
        limit=5,
        with_payload=True,
        with_vectors=False
    )
    
    points = result[0] if result else []
    print(f"\n샘플 데이터 ({len(points)}개):")
    
    tenant_ids = set()
    platforms = set()
    doc_types = set()
    
    for i, point in enumerate(points):
        payload = point.payload
        
        tenant_id = payload.get("tenant_id")
        platform = payload.get("platform")  
        doc_type = payload.get("doc_type")
        
        # 레거시 필드들도 확인
        legacy_type = payload.get("type")
        source_type = payload.get("source_type")
        
        tenant_ids.add(tenant_id)
        platforms.add(platform)
        doc_types.add(doc_type)
        
        print(f"\n문서 #{i+1} (ID: {point.id}):")
        print(f"  tenant_id: '{tenant_id}'")
        print(f"  platform: '{platform}'")
        print(f"  doc_type: '{doc_type}'")
        print(f"  type (legacy): '{legacy_type}'")
        print(f"  source_type: '{source_type}'")
        
        # 제목 확인
        title = payload.get("title") or payload.get("subject") or "N/A"
        print(f"  title/subject: '{title[:50]}...'")
    
    print(f"\n=== 발견된 값들 ===")
    print(f"tenant_ids: {sorted([t for t in tenant_ids if t])}")
    print(f"platforms: {sorted([p for p in platforms if p])}")
    print(f"doc_types: {sorted([d for d in doc_types if d])}")
    
    # 3. 테스트 검색 (현재 UI에서 사용하는 조건)
    test_tenant = "wedosoft"
    test_platform = "freshdesk"
    test_doc_type = "ticket"
    
    print(f"\n=== 테스트 검색 ===")
    print(f"조건: tenant_id='{test_tenant}', platform='{test_platform}', doc_type='{test_doc_type}'")
    
    # 필터 조건 구성
    filter_conditions = [
        FieldCondition(key="tenant_id", match=MatchValue(value=test_tenant))
    ]
    
    if test_platform:
        filter_conditions.append(
            FieldCondition(key="platform", match=MatchValue(value=test_platform))
        )
    
    if test_doc_type:
        filter_conditions.append(
            FieldCondition(key="doc_type", match=MatchValue(value=test_doc_type))
        )
    
    search_filter = Filter(must=filter_conditions)
    
    # count로 매칭되는 문서 수 확인
    count_result = client.count(
        collection_name=collection_name,
        count_filter=search_filter
    )
    
    print(f"매칭 문서 수: {count_result.count}")
    
    # 4. 각 조건별로 개별 테스트
    print(f"\n=== 개별 조건 테스트 ===")
    
    # tenant_id만
    tenant_filter = Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=test_tenant))])
    tenant_count = client.count(collection_name=collection_name, count_filter=tenant_filter)
    print(f"tenant_id='{test_tenant}' 문서 수: {tenant_count.count}")
    
    # platform만 (tenant_id 포함)
    if test_platform:
        platform_filter = Filter(must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=test_tenant)),
            FieldCondition(key="platform", match=MatchValue(value=test_platform))
        ])
        platform_count = client.count(collection_name=collection_name, count_filter=platform_filter)
        print(f"tenant_id='{test_tenant}' + platform='{test_platform}' 문서 수: {platform_count.count}")
    
    # 5. 가능한 모든 tenant_id와 platform 조합 확인
    print(f"\n=== 실제 데이터 기반 추천 ===")
    
    valid_tenants = [t for t in tenant_ids if t and t != "None"]
    valid_platforms = [p for p in platforms if p and p != "None"]
    
    if valid_tenants and valid_platforms:
        rec_tenant = sorted(valid_tenants)[0]
        rec_platform = sorted(valid_platforms)[0]
        
        rec_filter = Filter(must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=rec_tenant)),
            FieldCondition(key="platform", match=MatchValue(value=rec_platform))
        ])
        rec_count = client.count(collection_name=collection_name, count_filter=rec_filter)
        
        print(f"추천 조합: tenant_id='{rec_tenant}', platform='{rec_platform}'")
        print(f"해당 조합 문서 수: {rec_count.count}")
        
        # UI 설정 추천
        print(f"\n🔧 UI 테스트 설정 추천:")
        print(f"  Tenant ID: {rec_tenant}")
        print(f"  Platform: {rec_platform}")
    
except Exception as e:
    print(f"❌ 오류: {e}")
    import traceback
    traceback.print_exc()