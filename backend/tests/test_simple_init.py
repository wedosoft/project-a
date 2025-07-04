#!/usr/bin/env python3
"""
간단한 InitChain 테스트
"""

import asyncio
import sys
from pathlib import Path

# 백엔드 경로 추가
sys.path.insert(0, str(Path(__file__).parent.absolute()))

async def test_init():
    print("🔄 InitChain 간단 테스트...")
    
    try:
        # Import 테스트
        from core.llm.integrations.langchain.chains import execute_init_parallel_chain
        from core.database.vectordb import vector_db
        print("✅ Import 성공")
        
        # 테스트 티켓 데이터
        test_ticket = {
            'id': '12345',
            'subject': '로그인 문제 해결 요청',
            'description': '사용자가 로그인할 때 오류 메시지가 표시됩니다.',
            'conversations': [
                {'body_text': '도움이 필요합니다.', 'created_at': 1640995200}
            ],
            'metadata': {'priority': 'medium', 'status': 'open'}
        }
        
        # InitChain 실행 (간단 버전)
        results = await execute_init_parallel_chain(
            ticket_data=test_ticket,
            qdrant_client=vector_db.client,
            tenant_id='wedosoft',
            include_summary=False,  # 요약 제외
            include_similar_tickets=True,
            include_kb_docs=True,
            top_k_tickets=2,
            top_k_kb=2
        )
        
        print(f"✅ InitChain 실행 성공!")
        print(f"결과 키: {list(results.keys()) if results else 'None'}")
        
        # 결과 분석
        if results and 'unified_search' in results:
            unified = results['unified_search']
            success = unified.get('success', False)
            similar_count = len(unified.get('similar_tickets', []))
            kb_count = len(unified.get('kb_documents', []))
            
            print(f"통합 검색 성공: {success}")
            print(f"유사 티켓: {similar_count}개")
            print(f"KB 문서: {kb_count}개")
            
            if similar_count > 0:
                sample_ticket = unified['similar_tickets'][0]
                print(f"샘플 유사 티켓: {sample_ticket.get('id', 'N/A')} - {sample_ticket.get('title', 'N/A')[:30]}...")
                
            if kb_count > 0:
                sample_kb = unified['kb_documents'][0]
                print(f"샘플 KB: {sample_kb.get('id', 'N/A')} - {sample_kb.get('title', 'N/A')[:30]}...")
        else:
            print("❌ unified_search 결과 없음")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_init())
