#!/usr/bin/env python3
"""
수정된 메타데이터 로직으로 벡터 DB 재동기화 테스트
"""
import sys
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from core.database.vectordb import vector_db
from core.ingest.processor import sync_summaries_to_vector_db
import asyncio

async def test_metadata_fix():
    try:
        print("=== 1. 기존 벡터 DB 데이터 확인 ===")
        collection_info = vector_db.client.get_collection("documents")
        print(f"삭제 전 벡터 수: {collection_info.points_count}")
        
        print("\n=== 2. 기존 데이터 삭제 ===")
        # wedosoft/freshdesk 데이터만 삭제
        delete_result = vector_db.client.delete(
            collection_name="documents",
            points_selector={
                "filter": {
                    "must": [
                        {"key": "tenant_id", "match": {"value": "wedosoft"}},
                        {"key": "platform", "match": {"value": "freshdesk"}}
                    ]
                }
            },
            wait=True
        )
        print(f"삭제 결과: {delete_result}")
        
        collection_info = vector_db.client.get_collection("documents")
        print(f"삭제 후 벡터 수: {collection_info.points_count}")
        
        print("\n=== 3. 수정된 로직으로 재동기화 ===")
        result = await sync_summaries_to_vector_db('wedosoft', 'freshdesk')
        print(f"동기화 결과: {result}")
        
        print("\n=== 4. 최종 확인 ===")
        collection_info = vector_db.client.get_collection("documents")
        print(f"최종 벡터 수: {collection_info.points_count}")
        
        # 저장된 데이터 샘플 확인
        search_result = vector_db.client.scroll(
            collection_name="documents",
            limit=3,
            with_payload=True,
            with_vectors=False
        )
        
        print(f"\n저장된 {len(search_result[0])}개 레코드 (샘플):")
        for i, point in enumerate(search_result[0]):
            payload = point.payload
            print(f"\n{i+1}. ID: {point.id}")
            print(f"   tenant_id: {payload.get('tenant_id')}")
            print(f"   platform: {payload.get('platform')}")
            print(f"   original_id: {payload.get('original_id')}")
            print(f"   doc_type: {payload.get('doc_type')}")
            
            # 타입별 중요 필드 확인
            if payload.get('doc_type') == 'integrated_article':
                print(f"   title: {payload.get('title', 'N/A')}")
                print(f"   description: {payload.get('description', 'N/A')[:50]}...")
            elif payload.get('doc_type') == 'integrated_ticket':
                print(f"   subject: {payload.get('subject', 'N/A')}")
                print(f"   status: {payload.get('status')} (타입: {type(payload.get('status'))})")
                print(f"   priority: {payload.get('priority')} (타입: {type(payload.get('priority'))})")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_metadata_fix())
