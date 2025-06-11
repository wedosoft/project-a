#!/usr/bin/env python3
"""
DeepSeek 단독 테스트 스크립트
10초 타임아웃으로 DeepSeek의 실제 응답을 확인합니다.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.llm_router import LLMRouter


async def test_deepseek_only():
    """DeepSeek 모델만을 사용하여 응답 테스트"""
    print("🧪 DeepSeek 단독 테스트 시작...")
    print(f"📝 환경변수 LLM_DEEPSEEK_TIMEOUT: {os.getenv('LLM_DEEPSEEK_TIMEOUT', '기본값')}")
    
    router = LLMRouter()
    
    # DeepSeek만 활성화 (다른 제공자들 일시적으로 비활성화)
    original_weights = router.provider_selector.provider_weights.copy()
    
    # 다른 제공자들을 0 가중치로 설정하여 DeepSeek만 사용하도록 함
    for provider_name in ["anthropic", "openai", "gemini"]:
        if provider_name in router.provider_selector.provider_weights:
            current_weight = router.provider_selector.provider_weights[provider_name]
            current_weight.base_weight = 0.0
            current_weight.performance_multiplier = 0.0
    
    test_prompt = "안녕하세요! 간단한 인사말을 해주세요."
    
    try:
        print(f"🚀 DeepSeek에게 질문 중: '{test_prompt}'")
        start_time = time.time()
        
        response = await router.generate(
            prompt=test_prompt,
            system_prompt="당신은 친절한 AI 어시스턴트입니다.",
            max_tokens=100
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n✅ DeepSeek 응답 성공!")
        print(f"📊 응답 시간: {duration:.2f}초")
        print(f"🤖 사용된 모델: {response.model_used}")
        print(f"💬 응답 내용: {response.text}")
        print(f"🔄 폴백 여부: {response.is_fallback}")
        print(f"📈 토큰 사용량: {response.tokens_used}")
        
        if response.is_fallback:
            print(f"⚠️  주의: 이것은 폴백 응답입니다. 이전 제공자 오류: {response.previous_provider_error}")
        
    except Exception as e:
        print(f"❌ DeepSeek 테스트 실패: {type(e).__name__} - {str(e)}")
        
        # 제공자 상태 확인
        deepseek_provider = router.provider_instances["deepseek"]
        print(f"🏥 DeepSeek 건강 상태: {deepseek_provider.is_healthy()}")
        print(f"📊 DeepSeek 통계:")
        print(f"   - 총 요청 수: {deepseek_provider.stats.total_requests}")
        print(f"   - 성공 요청 수: {deepseek_provider.stats.successful_requests}")
        print(f"   - 실패 요청 수: {deepseek_provider.stats.failed_requests}")
        print(f"   - 연속 실패 수: {deepseek_provider.stats.consecutive_failures}")
        print(f"   - 평균 지연 시간: {deepseek_provider.stats.average_latency_ms:.2f}ms")
        
    finally:
        # 원래 가중치 복원
        router.provider_selector.provider_weights = original_weights

async def main():
    """메인 함수"""
    print("=" * 60)
    print("🧠 DeepSeek R1 Distilled 실제 응답 테스트")
    print("=" * 60)
    
    await test_deepseek_only()
    
    print("\n" + "=" * 60)
    print("✨ 테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
