#!/usr/bin/env python3
"""
벡터DB 데이터 빠른 확인
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

try:
    from core.database.vectordb import QdrantAdapter
    
    # Qdrant 연결
    vector_db = QdrantAdapter()
    
    print("=== 벡터DB 연결 테스트 ===")
    
    # 전체 문서 수
    total_count = vector_db.count()
    print(f"총 문서 수: {total_count}")
    
    if total_count > 0:
        # 컬렉션 정보
        info = vector_db.get_collection_info()
        print(f"컬렉션 정보: {info}")
        
        # 샘플 데이터 확인
        result = vector_db.client.scroll(
            collection_name=vector_db.collection_name,
            limit=3,
            with_payload=True,
            with_vectors=False
        )
        
        points = result[0] if result else []
        print(f"\n샘플 데이터 ({len(points)}개):")
        
        for i, point in enumerate(points):
            payload = point.payload
            print(f"  문서 {i+1}:")
            print(f"    tenant_id: {payload.get('tenant_id', 'N/A')}")
            print(f"    platform: {payload.get('platform', 'N/A')}")
            print(f"    doc_type: {payload.get('doc_type', 'N/A')}")
            print(f"    type (legacy): {payload.get('type', 'N/A')}")
    else:
        print("❌ 벡터DB에 데이터가 없습니다!")
        print("데이터 수집이 필요합니다.")
        
except Exception as e:
    print(f"❌ 오류: {e}")