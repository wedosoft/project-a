#!/usr/bin/env python3
"""
LLM 요약 시스템 테스트
"""

import sys
import os
import asyncio

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

async def test_llm_summary():
    """LLM 요약 기능 테스트"""
    print("🧪 LLM 요약 시스템 테스트 시작...")
    
    try:
        # LLM 요약 모듈 import
        from core.llm.summarizer import generate_summary
        print("✅ LLM 요약 모듈 import 성공")
        
        # 테스트 데이터
        test_content = """
        고객이 로그인할 때 "비밀번호가 틀렸습니다" 오류가 계속 발생합니다.
        고객은 분명히 올바른 비밀번호를 입력했다고 주장하고 있습니다.
        
        담당자가 확인해본 결과:
        1. 고객 계정이 일시적으로 잠겨있었음
        2. 5회 연속 로그인 실패로 인한 자동 잠금
        3. 계정 잠금을 해제하고 임시 비밀번호 발급
        
        고객에게 새로운 임시 비밀번호로 로그인 후 비밀번호 변경하도록 안내
        문제 해결됨.
        """
        
        test_metadata = {
            'status': 'resolved',
            'priority': 'medium',
            'created_at': '2024-01-15T10:30:00',
            'ticket_id': 'test-12345'
        }
        
        print("📝 요약 생성 시작...")
        
        # 요약 생성 테스트
        summary = await generate_summary(
            content=test_content,
            content_type="ticket",
            subject="로그인 오류 문제",
            metadata=test_metadata
        )
        
        print(f"✅ 요약 생성 성공!")
        print(f"📄 생성된 요약:")
        print(f"{summary}")
        print(f"📊 요약 길이: {len(summary)} 문자")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM 요약 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_llm_summary())
