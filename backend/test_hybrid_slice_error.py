#!/usr/bin/env python3
"""
하이브리드 검색에서 unhashable type: 'slice' 오류 디버깅을 위한 테스트
"""
import sys
import os
sys.path.append('.')

import asyncio
import traceback
from core.search.adapters import InitHybridAdapter
from core.search.hybrid import HybridSearchManager
from core.llm.manager import LLMManager

async def test_hybrid_adapter():
    """하이브리드 어댑터 테스트"""
    print("=== 하이브리드 어댑터 slice 오류 디버깅 ===")
    
    try:
        # 매니저 인스턴스 생성
        print("1. 매니저 인스턴스 생성...")
        hybrid_manager = HybridSearchManager()
        hybrid_adapter = InitHybridAdapter()
        llm_manager = LLMManager()
        print("✅ 매니저 생성 완료")
        
        # 테스트 데이터
        test_ticket_data = {
            'subject': 'Test ticket for slice error debugging',
            'description': 'This is a test ticket to debug the unhashable slice error',
            'priority': 'High',
            'status': 'Open',
            'created_at': '2025-01-28T10:00:00Z'
        }
        
        print("2. 하이브리드 검색 실행...")
        
        # 어댑터 실행
        result = await hybrid_adapter.execute_hybrid_init(
            hybrid_manager=hybrid_manager,
            llm_manager=llm_manager,
            ticket_data=test_ticket_data,
            tenant_id='test_tenant',
            platform='freshdesk',
            include_summary=True,
            include_similar_tickets=True,
            include_kb_docs=True,
            top_k_tickets=5,
            top_k_kb=3
        )
        
        print("3. 결과 분석...")
        print(f"결과 타입: {type(result)}")
        
        if isinstance(result, dict):
            print(f"결과 키들: {list(result.keys())}")
            
            # 각 주요 섹션 분석
            for key in ['summary', 'similar_tickets', 'kb_documents', 'unified_search']:
                if key in result:
                    value = result[key]
                    print(f"{key}: {type(value)} - {str(value)[:100]}...")
                    
                    # 리스트인 경우 슬라이싱 테스트
                    if isinstance(value, list):
                        print(f"  리스트 길이: {len(value)}")
                        try:
                            # 안전한 슬라이싱 테스트
                            test_slice = value[:3]
                            print(f"  슬라이싱 테스트 성공: {len(test_slice)}개 요소")
                        except Exception as slice_e:
                            print(f"  ❌ 슬라이싱 오류: {slice_e}")
        else:
            print(f"결과가 dict가 아님: {result}")
        
        print("✅ 테스트 완료")
        return result
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        print("=== 전체 스택 트레이스 ===")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("하이브리드 검색 slice 오류 디버깅 시작...")
    result = asyncio.run(test_hybrid_adapter())
    
    if result:
        print("\n=== 최종 결과 요약 ===")
        print(f"성공: {result.get('success', 'unknown')}")
        print(f"요약 존재: {'summary' in result}")
        print(f"유사 티켓 존재: {'similar_tickets' in result}")
        print(f"KB 문서 존재: {'kb_documents' in result}")
    else:
        print("결과가 없습니다.")
