#!/usr/bin/env python3
"""
벡터 DB에 저장된 데이터 수 확인 스크립트
"""
import sys
import os
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from core.database.vectordb import vector_db

def check_vector_count():
    try:
        # 컬렉션 정보 확인
        collection_info = vector_db.client.get_collection("documents")
        print(f"총 벡터 수: {collection_info.points_count}")
        
        # 최근 몇 개 포인트 조회
        search_result = vector_db.client.scroll(
            collection_name="documents",
            limit=5,
            with_payload=True,
            with_vectors=False
        )
        
        print(f"\n최근 저장된 {len(search_result[0])}개 레코드:")
        for i, point in enumerate(search_result[0]):
            payload = point.payload
            print(f"\n{i+1}. ID: {point.id}")
            print(f"   tenant_id: {payload.get('tenant_id')}")
            print(f"   platform: {payload.get('platform')}")
            print(f"   original_id: {payload.get('original_id')}")
            print(f"   doc_type: {payload.get('doc_type')}")
            
            # tenant_metadata가 문자열로 저장되어 있는지 확인
            if 'tenant_metadata' in payload:
                print(f"   tenant_metadata 타입: {type(payload['tenant_metadata'])}")
                if isinstance(payload['tenant_metadata'], str):
                    print(f"   tenant_metadata: {payload['tenant_metadata'][:100]}...")
                else:
                    print(f"   tenant_metadata: {payload['tenant_metadata']}")
        
        # wedosoft 테넌트의 레코드 수 확인
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        filter_condition = Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value="wedosoft")),
                FieldCondition(key="platform", match=MatchValue(value="freshdesk"))
            ]
        )
        
        wedosoft_result = vector_db.client.scroll(
            collection_name="documents",
            scroll_filter=filter_condition,
            limit=100,
            with_payload=False,
            with_vectors=False
        )
        
        print(f"\nwedosoft/freshdesk 레코드 수: {len(wedosoft_result[0])}")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_vector_count()
