#!/usr/bin/env python3
"""
수정된 메타데이터로 벡터 DB 재동기화 테스트
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
from qdrant_client.models import Filter, MatchValue

async def test_fixed_vector_sync():
    print("=== 수정된 메타데이터로 벡터 DB 재동기화 테스트 ===")
    
    try:
        # 1. 기존 데이터 삭제
        print("\n=== 1. 기존 벡터 DB 데이터 삭제 ===")
        collection_info = vector_db.client.get_collection("documents")
        print(f"삭제 전 벡터 수: {collection_info.points_count}")
        
        if collection_info.points_count > 0:
            # wedosoft/freshdesk 데이터만 삭제
            delete_result = vector_db.client.delete(
                collection_name="documents",
                points_filter=Filter(
                    must=[
                        MatchValue(key="tenant_id", value="wedosoft"),
                        MatchValue(key="platform", value="freshdesk")
                    ]
                )
            )
            print(f"삭제 결과: operation_id={delete_result.operation_id} status={delete_result.status}")
            
            # 삭제 후 확인
            collection_info = vector_db.client.get_collection("documents")
            print(f"삭제 후 벡터 수: {collection_info.points_count}")
        
        # 2. 수정된 로직으로 재동기화
        print("\n=== 2. 수정된 로직으로 재동기화 ===")
        result = await sync_summaries_to_vector_db('wedosoft', 'freshdesk')
        print(f"동기화 결과: {result}")
        
        # 3. 최종 확인
        print("\n=== 3. 최종 확인 ===")
        collection_info = vector_db.client.get_collection("documents")
        print(f"최종 벡터 수: {collection_info.points_count}")
        
        # 저장된 데이터 샘플 확인
        search_result = vector_db.client.scroll(
            collection_name="documents",
            limit=3,
            with_payload=True,
            with_vectors=False,
            scroll_filter=Filter(
                must=[
                    MatchValue(key="tenant_id", value="wedosoft"),
                    MatchValue(key="platform", value="freshdesk")
                ]
            )
        )
        
        print(f"\n저장된 {len(search_result[0])}개 레코드 샘플:")
        for i, point in enumerate(search_result[0]):
            payload = point.payload
            print(f"\n{i+1}. ID: {point.id}")
            print(f"   tenant_id: {payload.get('tenant_id')}")
            print(f"   platform: {payload.get('platform')}")
            print(f"   original_id: {payload.get('original_id')}")
            print(f"   doc_type: {payload.get('doc_type')}")
            
            # 제목 확인
            title = payload.get('title') or payload.get('subject')
            if title:
                print(f"   제목: {title}")
            else:
                print(f"   제목: 없음")
            
            # 상태/우선순위 타입 확인
            status = payload.get('status')
            priority = payload.get('priority')
            print(f"   status: {status} (타입: {type(status)})")
            print(f"   priority: {priority} (타입: {type(priority)})")
            
            # AI 관련 정보
            ai_generated = payload.get('ai_summary_generated')
            ai_model = payload.get('ai_model_used')
            quality_score = payload.get('summary_quality_score')
            print(f"   AI 요약: {ai_generated}, 모델: {ai_model}, 품질: {quality_score}")
            
            # 불필요한 필드가 없는지 확인
            unwanted_fields = ['department', 'object_type']
            for field in unwanted_fields:
                if field in payload:
                    print(f"   ⚠️ 불필요한 필드 발견: {field} = {payload[field]}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fixed_vector_sync())
