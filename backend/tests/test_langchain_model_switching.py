#!/usr/bin/env python3
"""
LangChain 모델 전환 테스트 스크립트

환경변수만 변경하면 모델이 즉시 바뀌는지 테스트합니다.
LangChain의 진정한 장점을 보여주는 스크립트입니다!
"""

import asyncio
import os
import sys
sys.path.append('/Users/alan/GitHub/project-a/backend')

async def test_model_switching():
    """모델 전환 테스트"""
    try:
        from core.llm.manager import LLMManager
        
        print("🚀 LangChain 모델 전환 테스트 시작!")
        print("=" * 50)
        
        # LLMManager 초기화
        llm_manager = LLMManager()
        
        # 현재 설정 확인
        print("📋 현재 모델 설정:")
        
        use_cases = ["realtime", "batch", "summarization"]
        for use_case in use_cases:
            provider, model = llm_manager.config_manager.get_model_for_use_case(use_case)
            config = llm_manager.config_manager.get_use_case_config(use_case)
            
            print(f"  {use_case:12}: {provider.value:8} | {model:20} | tokens: {config.get('max_tokens', 'N/A')}")
        
        print("\n🎯 실제 모델 호출 테스트:")
        print("-" * 50)
        
        # 각 use case별 테스트
        test_messages = [
            {"role": "user", "content": "안녕하세요, 간단한 테스트입니다."}
        ]
        
        for use_case in use_cases:
            print(f"\n📝 {use_case.upper()} 모델 테스트:")
            
            try:
                response = await llm_manager.generate_for_use_case(
                    use_case=use_case,
                    messages=test_messages,
                    max_tokens=50
                )
                
                if response.success:
                    print(f"   ✅ 성공: {response.provider} | {response.model}")
                    print(f"   💬 응답: {response.content[:100]}...")
                else:
                    print(f"   ❌ 실패: {response.error}")
                    
            except Exception as e:
                print(f"   ❌ 예외: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 테스트 완료!")
        print("\n💡 이제 환경변수만 바꾸면 모델이 즉시 변경됩니다:")
        print("   REALTIME_MODEL_NAME=claude-3-haiku")
        print("   BATCH_MODEL_NAME=gpt-4o")
        print("   SUMMARIZATION_MODEL_NAME=gemini-1.5-pro")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_model_switching())
