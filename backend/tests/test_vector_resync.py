#!/usr/bin/env python3
"""
벡터 DB 데이터 삭제 후 재동기화 테스트 스크립트
"""
import sys
import asyncio
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from core.database.vectordb import vector_db
from core.ingest.processor import sync_summaries_to_vector_db

async def test_resync():
    try:
        tenant_id = "wedosoft"
        platform = "freshdesk"
        
        print("=== 1. 기존 벡터 DB 데이터 확인 ===")
        collection_info = vector_db.client.get_collection("documents")
        print(f"삭제 전 벡터 수: {collection_info.points_count}")
        
        print("\n=== 2. 기존 데이터 삭제 ===")
        # wedosoft/freshdesk 데이터만 삭제
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        
        delete_filter = Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                ),
                FieldCondition(
                    key="platform", 
                    match=MatchValue(value=platform)
                )
            ]
        )
        
        delete_result = vector_db.client.delete(
            collection_name="documents",
            points_selector=delete_filter
        )
        print(f"삭제 결과: {delete_result}")
        
        # 삭제 후 개수 확인
        collection_info_after = vector_db.client.get_collection("documents")
        print(f"삭제 후 벡터 수: {collection_info_after.points_count}")
        
        print("\n=== 3. 재동기화 ===")
        result = await sync_summaries_to_vector_db(tenant_id, platform)
        print(f"동기화 결과: {result}")
        
        print("\n=== 4. 최종 확인 ===")
        collection_info_final = vector_db.client.get_collection("documents")
        print(f"최종 벡터 수: {collection_info_final.points_count}")
        
        # 최근 몇 개 레코드 확인
        search_result = vector_db.client.scroll(
            collection_name="documents",
            limit=5,
            with_payload=True,
            with_vectors=False,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id)
                    ),
                    FieldCondition(
                        key="platform",
                        match=MatchValue(value=platform)
                    )
                ]
            )
        )
        
        print(f"\n저장된 {len(search_result[0])}개 레코드:")
        for i, point in enumerate(search_result[0]):
            payload = point.payload
            print(f"\n{i+1}. ID: {point.id}")
            print(f"   tenant_id: {payload.get('tenant_id')}")
            print(f"   platform: {payload.get('platform')}")
            print(f"   original_id: {payload.get('original_id')}")
            print(f"   doc_type: {payload.get('doc_type')}")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_resync())
