#!/usr/bin/env python3
"""
속도 최우선 LLM Router 테스트 스크립트
Gemini Flash 2.0 우선순위와 작업별 모델 차등 적용 테스트
"""

import asyncio
import os
import sys

# 현재 디렉토리를 Python 경로에 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

async def test_llm_router():
    """LLM Router 기본 동작 테스트"""
    try:
        from core.llm_router import LLMRouter
        
        print("🚀 속도 최우선 LLM Router 테스트 시작")
        print("=" * 60)
        
        # LLM Router 인스턴스 생성
        router = LLMRouter()
        
        # 1. 기본 생성 테스트 - 중량 작업으로 처리됨
        print("1️⃣ 기본 텍스트 생성 테스트 (중량 작업)")
        response = await router.generate(
            prompt="안녕하세요! 간단한 인사말을 생성해주세요.",
            max_tokens=100
        )
        
        print(f"   📝 응답: {response.text[:100]}...")
        print(f"   🤖 사용 모델: {response.model_used}")
        print(f"   ⏱️  응답 시간: {response.duration_ms:.0f}ms")
        print(f"   🔄 시도 횟수: {response.attempt_count}")
        print()
        
        # 2. 작업 타입 감지 테스트
        print("2️⃣ 작업 타입 감지 테스트")
        
        # 경량 작업 테스트
        light_task = router.get_task_type_from_operation("ticket_summary")
        print(f"   📋 'ticket_summary' -> {light_task} 작업")
        
        # 중량 작업 테스트  
        heavy_task = router.get_task_type_from_operation("agent_chat")
        print(f"   💬 'agent_chat' -> {heavy_task} 작업")
        
        # 미지정 작업 테스트
        unknown_task = router.get_task_type_from_operation("unknown_operation")
        print(f"   ❓ 'unknown_operation' -> {unknown_task} 작업")
        print()
        
        # 3. 작업별 모델 차등 적용 테스트
        if hasattr(router, 'generate_with_task_type'):
            print("3️⃣ 작업별 모델 차등 적용 테스트")
            
            # 경량 작업 테스트
            print("   🏃‍♂️ 경량 작업 테스트 (요약/분류)")
            light_response = await router.generate_with_task_type(
                prompt="이 티켓을 간단히 요약해주세요: 로그인 문제 발생",
                task_type="light",
                max_tokens=50
            )
            
            print(f"   📝 응답: {light_response.text[:50]}...")
            print(f"   🤖 사용 모델: {light_response.metadata.get('model_used', 'N/A')}")
            print(f"   ⏱️  응답 시간: {light_response.duration_ms:.0f}ms")
            print()
            
            # 중량 작업 테스트
            print("   🚀 중량 작업 테스트 (상담/채팅)")
            heavy_response = await router.generate_with_task_type(
                prompt="고객과의 상담에서 복잡한 기술 문제를 설명해주세요.",
                task_type="heavy",
                max_tokens=200
            )
            
            print(f"   📝 응답: {heavy_response.text[:50]}...")
            print(f"   🤖 사용 모델: {heavy_response.metadata.get('model_used', 'N/A')}")
            print(f"   ⏱️  응답 시간: {heavy_response.duration_ms:.0f}ms")
            print()
        else:
            print("❌ generate_with_task_type 메서드가 없습니다.")
        
        # 4. 제공자 우선순위 확인
        print("4️⃣ 제공자 우선순위 확인")
        print(f"   🥇 우선순위: {router.providers_priority}")
        
        # 5. 환경변수 설정 확인
        print("5️⃣ 환경변수 설정 확인")
        print(f"   ⏱️  글로벌 타임아웃: {os.getenv('LLM_GLOBAL_TIMEOUT', 'N/A')}초")
        print(f"   🏃‍♂️ 경량 모델: {os.getenv('LLM_LIGHT_MODEL', 'N/A')}")
        print(f"   🚀 중량 모델: {os.getenv('LLM_HEAVY_MODEL', 'N/A')}")
        
        print("\n✅ 모든 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_router())
