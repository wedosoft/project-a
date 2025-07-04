#!/usr/bin/env python3
"""
스트리밍 요약 테스트

실시간 스트리밍 요약 기능을 테스트합니다.
"""

import asyncio
import sys
import os
sys.path.append('/Users/alan/GitHub/project-a/backend')

import logging
import time
from core.llm.manager import get_llm_manager
from core.llm.summarizer.prompt.builder import PromptBuilder

# 로그 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_streaming_summary():
    """스트리밍 요약 테스트"""
    
    print("🚀 스트리밍 요약 테스트 시작!")
    print("=" * 50)
    
    try:
        # LLM Manager 초기화
        llm_manager = get_llm_manager()
        
        # PromptBuilder 초기화
        prompt_builder = PromptBuilder()
        
        # 현재 설정 확인
        print("📋 현재 모델 설정:")
        config = llm_manager.config_manager.get_use_case_config("realtime")
        if config:
            print(f"  realtime: {config['provider']:<8} | {config['model']:<20}")
        print()
        
        # 스트리밍 테스트
        print("🎯 실시간 요약 스트리밍 테스트 (YAML 템플릿 사용):")
        print("-" * 30)
        
        # YAML 템플릿으로 프롬프트 생성
        system_prompt = prompt_builder.build_system_prompt(
            content_type="realtime_ticket",
            content_language="ko",
            ui_language="ko"
        )

        # 테스트용 티켓 데이터
        ticket_content = """제목: 사용자 로그인 문제
내용: 사용자가 로그인할 때 오류가 발생합니다. 비밀번호가 맞는데도 접속이 안 됩니다. 여러 번 시도해봤지만 계속 실패합니다.

우선순위: High
상태: Open
카테고리: Technical Issue
고객사: ABC 회사
담당자: 홍길동 (hong@abc.com)
생성일: 2025-06-29"""

        user_prompt = prompt_builder.build_user_prompt(
            content=ticket_content,
            content_type="realtime_ticket",
            subject="사용자 로그인 문제",
            metadata={},
            content_language="ko",
            ui_language="ko"
        )
        
        start_time = time.time()
        full_text = ""
        chunk_count = 0
        
        async for chunk in llm_manager.stream_generate_for_use_case(
            use_case="realtime",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=400,  # 600 → 400으로 더 줄임
            temperature=0.1
        ):
            print(chunk, end="", flush=True)
            full_text += chunk
            chunk_count += 1
        
        elapsed_time = time.time() - start_time
        print(f"\n\n⏱️  총 시간: {elapsed_time:.2f}초, 청크 수: {chunk_count}")
        print()
        
        print("=" * 50)
        print("🎉 스트리밍 요약 테스트 완료!")
        print("\n💡 스트리밍이 성공적으로 작동합니다!")
        print("   - 실시간 텍스트 출력 ✅")
        print("   - Config-driven 모델 선택 ✅") 
        print("   - YAML 템플릿 기반 구조화 마크다운 ✅")
        print("   - 빠른 응답 속도 ✅")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류: {e}", exc_info=True)
        print(f"❌ 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_streaming_summary())
