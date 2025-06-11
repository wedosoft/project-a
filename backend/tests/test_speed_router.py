#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
속도 최우선 LLM Router 테스트 스크립트

OpenAI API 장애 상황 대응으로 DeepSeek R1 Distilled와 Gemini Flash 모델을 추가하여
시스템 전체 응답 속도를 극대화하는 테스트를 수행합니다.
"""

import asyncio
import os
import time
import traceback

from core.llm_router import LLMRouter
from core.settings import ProjectSettings


async def test_speed_router():
    """속도 최우선 LLM Router의 성능을 테스트합니다."""
    print("🚀 속도 최우선 LLM Router 테스트 시작")
    print("="*60)
    
    try:
        # 설정 로드
        settings = ProjectSettings()
        
        # 환경변수에서 타임아웃 설정 가져오기
        llm_timeout = float(os.getenv('LLM_TIMEOUT', '3'))
        gemini_timeout = float(os.getenv('LLM_GEMINI_TIMEOUT', '5'))
        
        print(f"✅ 설정 로드 완료 - LLM 타임아웃: {llm_timeout}초, Gemini 타임아웃: {gemini_timeout}초")
        
        # LLMRouter 초기화 - 속도 최우선 설정
        router = LLMRouter(
            timeout=llm_timeout,      # 환경변수에서 가져온 타임아웃
            gemini_timeout=gemini_timeout  # 환경변수에서 가져온 Gemini 타임아웃
        )
        print("✅ LLMRouter 초기화 완료 (속도 최우선 모드)")
        
        # 테스트 프롬프트
        test_prompt = "안녕하세요! 간단한 인사말로 답변해주세요."
        
        # 속도 테스트용 반복 횟수
        test_count = 3
        
        print(f"\n📊 속도 테스트 시작 ({test_count}회 반복)")
        print("-" * 60)
        
        total_time = 0
        success_count = 0
        
        for i in range(test_count):
            print(f"\n🔄 테스트 {i+1}/{test_count}")
            
            start_time = time.time()
            
            try:
                # LLM 호출 테스트
                response = await router.generate(
                    prompt=test_prompt,
                    system_prompt="당신은 빠르고 정확한 AI 어시스턴트입니다.",
                    max_tokens=100,
                    temperature=0.1
                )
                
                end_time = time.time()
                duration = end_time - start_time
                total_time += duration
                success_count += 1
                
                print(f"✅ 성공 - 응답시간: {duration:.2f}초")
                print(f"📝 사용된 모델: {response.model_used}")
                print(f"⚡ 응답 내용: {response.text[:100]}...")
                print(f"🔢 토큰 사용량: {response.tokens_used}")
                
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                print(f"❌ 실패 - 소요시간: {duration:.2f}초")
                print(f"🚨 오류: {str(e)}")
        
        # 결과 요약
        print("\n" + "="*60)
        print("📈 테스트 결과 요약")
        print("="*60)
        
        if success_count > 0:
            avg_time = total_time / success_count
            print(f"✅ 성공률: {success_count}/{test_count} ({success_count/test_count*100:.1f}%)")
            print(f"⚡ 평균 응답시간: {avg_time:.2f}초")
            print(f"🏆 총 소요시간: {total_time:.2f}초")
            
            # 성능 평가
            if avg_time < 2.0:
                print("🚀 성능 등급: 최고속 (2초 미만)")
            elif avg_time < 4.0:
                print("⚡ 성능 등급: 고속 (4초 미만)")
            elif avg_time < 6.0:
                print("🔥 성능 등급: 보통 (6초 미만)")
            else:
                print("🐌 성능 등급: 느림 (6초 이상)")
                
        else:
            print("❌ 모든 테스트 실패")
        
        # 제공자별 통계 출력
        print("\n📊 제공자별 성능 통계:")
        print("-" * 40)
        
        # DeepSeek 제공자 확인
        if hasattr(router, 'deepseek_provider') and router.deepseek_provider:
            stats = router.deepseek_provider.stats
            print(f"🥇 DeepSeek: 요청 {stats.total_requests}회, "
                  f"성공률 {stats.success_rate:.1%}, "
                  f"평균 지연시간 {stats.average_latency_ms:.0f}ms")
        
        # Gemini 제공자 확인
        if hasattr(router, 'gemini_provider') and router.gemini_provider:
            stats = router.gemini_provider.stats
            print(f"🥈 Gemini: 요청 {stats.total_requests}회, "
                  f"성공률 {stats.success_rate:.1%}, "
                  f"평균 지연시간 {stats.average_latency_ms:.0f}ms")
        
        # OpenAI 제공자 확인
        if hasattr(router, 'openai_provider') and router.openai_provider:
            stats = router.openai_provider.stats
            print(f"🥉 OpenAI: 요청 {stats.total_requests}회, "
                  f"성공률 {stats.success_rate:.1%}, "
                  f"평균 지연시간 {stats.average_latency_ms:.0f}ms")
        
        print("\n🎯 속도 최우선 LLM Router 테스트 완료!")
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생:")
        print(f"🚨 오류 내용: {str(e)}")
        print(f"📍 오류 위치:")
        traceback.print_exc()


def main():
    """메인 함수"""
    try:
        asyncio.run(test_speed_router())
    except KeyboardInterrupt:
        print("\n\n⏹️  사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    main()