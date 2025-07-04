#!/usr/bin/env python3
"""
벡터 DB 동기화 테스트 스크립트
"""

import sys
import asyncio
sys.path.append('/Users/alan/GitHub/project-a/backend')

from core.ingest.processor import sync_summaries_to_vector_db

async def test_vector_sync():
    """벡터 DB 동기화 테스트"""
    print("벡터 DB 동기화 테스트 시작...")
    
    try:
        result = await sync_summaries_to_vector_db('wedosoft', 'freshdesk')
        print(f"✅ 동기화 결과: {result}")
    except Exception as e:
        print(f"❌ 동기화 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_vector_sync())
