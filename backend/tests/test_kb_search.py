#!/usr/bin/env python3
"""
수정된 vectordb.py의 KB 검색 기능 테스트
"""

import asyncio
import sys
from pathlib import Path

# 백엔드 경로 추가
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

async def test_kb_search():
    """KB 검색 테스트"""
    print('🔍 KB 검색 테스트 시작')
    
    try:
        from core.embedder import generate_embedding
        from core.vectordb import QdrantAdapter
        
        vector_db = QdrantAdapter()
        
        # 임베딩 생성
        query_embedding = await generate_embedding('티켓 자동 종료')
        
        # KB 문서 검색 (doc_type 명시)
        results = vector_db.search(
            query_embedding=query_embedding,
            top_k=5,
            company_id='wedosoft',
            doc_type='kb'
        )
        
        print(f'✅ KB 검색 결과: {len(results.get("results", []))}개')
        
        for i, doc in enumerate(results.get('results', [])):
            print(f'  {i+1}. ID: {doc.get("id")}, Title: {doc.get("title", "N/A")[:50]}')
            print(f'      Score: {doc.get("score", 0):.3f}')
        
        # 티켓 검색도 테스트
        print('\n🎫 티켓 검색 테스트 시작')
        ticket_results = vector_db.search(
            query_embedding=query_embedding,
            top_k=3,
            company_id='wedosoft',
            doc_type='ticket'
        )
        
        print(f'✅ 티켓 검색 결과: {len(ticket_results.get("results", []))}개')
        
        for i, doc in enumerate(ticket_results.get('results', [])):
            print(f'  {i+1}. ID: {doc.get("id")}, Title: {doc.get("title", "N/A")[:50]}')
            print(f'      Score: {doc.get("score", 0):.3f}')
        
    except Exception as e:
        print(f'❌ 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_kb_search())
