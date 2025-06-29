#!/usr/bin/env python3
"""
/init 엔드포인트의 새로운 모델 관리 시스템 테스트

LangChain 기반 Use Case별 모델 자동 선택이 제대로 작동하는지 확인합니다.
"""

import asyncio
import sys
import os
sys.path.append('/Users/alan/GitHub/project-a/backend')

import logging
from core.llm.manager import get_llm_manager
from core.search.adapters import InitHybridAdapter
from core.search.hybrid import HybridSearchManager

# 로그 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_init_model_switching():
    """
    /init 엔드포인트의 요약 생성에서 새로운 모델 시스템 테스트
    """
    
    print("🚀 /init 엔드포인트 모델 시스템 테스트 시작!")
    print("=" * 50)
    
    try:
        # LLM Manager 초기화
        llm_manager = get_llm_manager()
        
        # 현재 설정 확인
        print("📋 현재 모델 설정:")
        use_cases = ["realtime", "batch", "summarization"]
        for use_case in use_cases:
            config = llm_manager.config_manager.get_use_case_config(use_case)
            if config:
                print(f"  {use_case:<12}: {config['provider']:<8} | {config['model']:<20} | tokens: {config['max_tokens']}")
        print()
        
        # 테스트용 티켓 데이터
        test_ticket_data = {
            "id": "test_12345",
            "subject": "사용자 로그인 문제",
            "description_text": "사용자가 로그인할 때 오류가 발생합니다. 비밀번호가 맞는데도 접속이 안 됩니다.",
            "conversations": [],
            "tenant_id": "test_tenant",
            "platform": "freshdesk",
            "metadata": {
                "priority": "High",
                "status": "Open",
                "category": "Technical Issue"
            }
        }
        
        # InitHybridAdapter를 통한 요약 생성 테스트
        print("🎯 InitHybridAdapter 요약 생성 테스트:")
        print("-" * 50)
        
        hybrid_manager = HybridSearchManager()
        hybrid_adapter = InitHybridAdapter()
        
        # 요약만 생성 (검색은 비활성화)
        result = await hybrid_adapter.execute_hybrid_init(
            hybrid_manager=hybrid_manager,
            llm_manager=llm_manager,
            ticket_data=test_ticket_data,
            tenant_id="test_tenant",
            platform="freshdesk",
            include_summary=True,  # 요약 활성화
            include_similar_tickets=False,  # 검색 비활성화
            include_kb_docs=False,  # 검색 비활성화
            top_k_tickets=0,
            top_k_kb=0
        )
        
        # 결과 분석
        print("\n📊 요약 생성 결과:")
        if result.get("summary"):
            summary_result = result["summary"]
            print(f"   ✅ 요약 생성 성공!")
            print(f"   📝 요약 타입: {type(summary_result)}")
            
            if isinstance(summary_result, dict):
                print(f"   🔧 결과 구조: {list(summary_result.keys())}")
                
                # 실제 요약 텍스트 추출
                summary_text = None
                for field in ["summary", "result", "content", "text", "response"]:
                    if field in summary_result and summary_result[field]:
                        if isinstance(summary_result[field], dict):
                            nested = summary_result[field]
                            for nested_field in ["ticket_summary", "summary", "content", "text"]:
                                if nested_field in nested:
                                    summary_text = nested[nested_field]
                                    break
                        else:
                            summary_text = str(summary_result[field])
                        break
                
                if summary_text:
                    print(f"   💬 요약 내용: {summary_text[:100]}...")
                else:
                    print(f"   ⚠️  요약 텍스트 추출 실패")
                    
            else:
                print(f"   💬 요약 내용: {str(summary_result)[:100]}...")
        else:
            print("   ❌ 요약 생성 실패")
            print(f"   🔍 전체 결과: {result}")
        
        print("\n" + "=" * 50)
        print("🎉 테스트 완료!")
        print("\n💡 이제 환경변수만 바꾸면 /init 엔드포인트의 요약 모델이 즉시 변경됩니다:")
        print("   REALTIME_MODEL_NAME=claude-3-haiku")
        print("   REALTIME_MODEL_PROVIDER=anthropic")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류: {e}", exc_info=True)
        print(f"❌ 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_init_model_switching())
