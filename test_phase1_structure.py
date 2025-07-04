#!/usr/bin/env python3
"""
Phase 1 기본 구조 테스트 스크립트

상담원 채팅 기능의 Phase 1에서 구현한 기본 구조들을 테스트합니다.
- AnthropicIntentAnalyzer
- Constitutional AI 프롬프트 로드
- AnthropicSearchOrchestrator 초기화
"""

import asyncio
import sys
import os
from pathlib import Path

# 백엔드 경로 추가
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

async def test_intent_analyzer():
    """의도 분석기 테스트"""
    print("=== 의도 분석기 테스트 ===")
    
    try:
        # boto3 의존성 없이 테스트하기 위해 mock 처리
        import sys
        from unittest.mock import MagicMock
        
        # boto3 mock
        sys.modules['boto3'] = MagicMock()
        
        from core.search.anthropic.intent_analyzer import AnthropicIntentAnalyzer
        
        analyzer = AnthropicIntentAnalyzer()
        
        # 테스트 케이스들
        test_queries = [
            "API 연동 오류 티켓 찾아줘",
            "이번 주 해결된 VIP 고객 케이스",
            "로그인 문제 해결 가이드",
            "긴급한 결제 문제 해결 방법",
            "오늘 생성된 티켓들 보여줘"
        ]
        
        for query in test_queries:
            print(f"\n쿼리: {query}")
            context = await analyzer.analyze_search_intent(query)
            print(f"  의도: {context.intent}")
            print(f"  우선순위: {context.urgency}")
            print(f"  키워드: {context.keywords}")
            print(f"  필터: {context.filters}")
            print(f"  정제된 쿼리: {context.clean_query}")
        
        print("✅ 의도 분석기 테스트 성공")
        return True
        
    except Exception as e:
        print(f"❌ 의도 분석기 테스트 실패: {e}")
        return False

def test_constitutional_prompts():
    """Constitutional AI 프롬프트 로드 테스트"""
    print("\n=== Constitutional AI 프롬프트 테스트 ===")
    
    try:
        import yaml
        prompts_path = backend_path / "core" / "search" / "prompts" / "constitutional_search.yaml"
        
        if not prompts_path.exists():
            print(f"❌ 프롬프트 파일이 없습니다: {prompts_path}")
            return False
        
        with open(prompts_path, 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        
        # 필수 섹션 확인
        required_sections = [
            'constitutional_principles',
            'system_prompt',
            'intent_prompts',
            'safety_guidelines'
        ]
        
        for section in required_sections:
            if section not in prompts:
                print(f"❌ 필수 섹션 누락: {section}")
                return False
            print(f"✓ {section} 섹션 존재")
        
        # 의도별 프롬프트 확인
        intent_prompts = prompts.get('intent_prompts', {})
        required_intents = ['problem_solving', 'info_gathering', 'learning', 'analysis', 'general']
        
        for intent in required_intents:
            if intent in intent_prompts:
                print(f"✓ {intent} 프롬프트 존재")
            else:
                print(f"⚠️ {intent} 프롬프트 누락")
        
        print("✅ Constitutional AI 프롬프트 테스트 성공")
        return True
        
    except Exception as e:
        print(f"❌ Constitutional AI 프롬프트 테스트 실패: {e}")
        return False

async def test_search_orchestrator():
    """검색 오케스트레이터 테스트"""
    print("\n=== 검색 오케스트레이터 테스트 ===")
    
    try:
        # 의존성 mock
        import sys
        from unittest.mock import MagicMock
        
        sys.modules['boto3'] = MagicMock()
        sys.modules['yaml'] = MagicMock()
        
        from core.search.anthropic.search_orchestrator import AnthropicSearchOrchestrator
        
        # 기본 초기화 테스트 (의존성 없이)
        orchestrator = AnthropicSearchOrchestrator()
        
        # 프롬프트 로드 확인
        if orchestrator.prompts:
            print("✓ Constitutional AI 프롬프트 로드 성공")
        else:
            print("⚠️ 프롬프트 로드 실패, 기본값 사용")
        
        # 의도 분석기 확인
        if orchestrator.intent_analyzer:
            print("✓ 의도 분석기 초기화 성공")
        else:
            print("❌ 의도 분석기 초기화 실패")
            return False
        
        print("✅ 검색 오케스트레이터 테스트 성공")
        return True
        
    except Exception as e:
        print(f"❌ 검색 오케스트레이터 테스트 실패: {e}")
        return False

def test_module_imports():
    """모듈 임포트 테스트"""
    print("\n=== 모듈 임포트 테스트 ===")
    
    try:
        # boto3 의존성 없이 테스트하기 위해 mock 처리
        import sys
        from unittest.mock import MagicMock
        
        # 필요한 모듈들 mock
        sys.modules['boto3'] = MagicMock()
        sys.modules['yaml'] = MagicMock()
        
        # __init__.py를 통한 임포트 테스트
        from core.search.anthropic import (
            AnthropicIntentAnalyzer,
            SearchContext,
            AnthropicSearchOrchestrator
        )
        
        print("✓ AnthropicIntentAnalyzer 임포트 성공")
        print("✓ SearchContext 임포트 성공")
        print("✓ AnthropicSearchOrchestrator 임포트 성공")
        
        print("✅ 모듈 임포트 테스트 성공")
        return True
        
    except Exception as e:
        print(f"❌ 모듈 임포트 테스트 실패: {e}")
        return False

async def main():
    """메인 테스트 함수"""
    print("🚀 Phase 1 기본 구조 테스트 시작\n")
    
    # 테스트 실행
    tests = [
        ("모듈 임포트", test_module_imports),
        ("Constitutional AI 프롬프트", test_constitutional_prompts),
        ("의도 분석기", test_intent_analyzer),
        ("검색 오케스트레이터", test_search_orchestrator)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"테스트: {test_name}")
        print(f"{'='*50}")
        
        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()
        
        results.append((test_name, result))
    
    # 결과 요약
    print(f"\n{'='*50}")
    print("📊 테스트 결과 요약")
    print(f"{'='*50}")
    
    passed = 0
    for test_name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n총 {len(results)}개 테스트 중 {passed}개 통과")
    
    if passed == len(results):
        print("🎉 Phase 1 기본 구조 테스트 모두 통과!")
        print("\n✨ Phase 2로 진행할 준비가 완료되었습니다.")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 문제를 해결 후 다시 시도하세요.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)