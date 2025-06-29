#!/usr/bin/env python3
"""
object_type 필드 수정 검증 스크립트
"""
import asyncio
import logging
from core.ingest.processor import sync_summaries_to_vector_db
from core.database.vectordb import vector_db

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_sync():
    """벡터 DB 재동기화하고 object_type 필드 확인"""
    
    # 기존 데이터 삭제
    print('=== 기존 데이터 삭제 ===')
    try:
        collection_info = vector_db.client.get_collection('documents')
        print(f'삭제 전 벡터 수: {collection_info.points_count}')
        
        delete_result = vector_db.client.delete(
            collection_name='documents',
            points_selector={'filter': {'must': [{'key': 'tenant_id', 'match': {'value': 'wedosoft'}}]}}
        )
        print(f'삭제 결과: {delete_result}')
        
        collection_info = vector_db.client.get_collection('documents')
        print(f'삭제 후 벡터 수: {collection_info.points_count}')
    except Exception as e:
        print(f'삭제 중 오류: {e}')
    
    # 재동기화
    print('\n=== 재동기화 ===')
    result = await sync_summaries_to_vector_db('wedosoft', 'freshdesk')
    print(f'동기화 결과: {result}')
    
    # 최종 확인
    print('\n=== 최종 확인 ===')
    try:
        collection_info = vector_db.client.get_collection('documents')
        print(f'최종 벡터 수: {collection_info.points_count}')
        
        # 샘플 레코드 확인
        points = vector_db.client.scroll(
            collection_name='documents',
            limit=5
        )
        print(f'\n저장된 샘플 레코드:')
        for i, point in enumerate(points[0], 1):
            payload = point.payload
            print(f'\n{i}. ID: {point.id}')
            print(f'   tenant_id: {payload.get("tenant_id")}')
            print(f'   platform: {payload.get("platform")}')
            print(f'   original_id: {payload.get("original_id")}')
            print(f'   doc_type: {payload.get("doc_type")}')
            print(f'   object_type: {payload.get("object_type")}')
            if payload.get("subject"):
                print(f'   subject: {payload.get("subject")[:50]}...')
            if payload.get("title"):
                print(f'   title: {payload.get("title")[:50]}...')
            
    except Exception as e:
        print(f'확인 중 오류: {e}')

if __name__ == "__main__":
    asyncio.run(test_sync())
