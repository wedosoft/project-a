#!/usr/bin/env python3
"""
Phase 2 통합 테스트 스크립트

상담원 채팅 기능의 Phase 2 API 통합을 테스트합니다.
- AgentChatRequest/Response 모델
- /api/agent-chat/search 엔드포인트
- /api/agent-chat/suggestions 엔드포인트
- 의존성 주입 확인
"""

import sys
import os
from pathlib import Path

def test_model_imports():
    """API 모델 임포트 테스트"""
    print("=== API 모델 임포트 테스트 ===")
    
    try:
        # 현재 디렉토리에 따라 backend 경로 조정
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            backend_path = Path(".")
        else:
            backend_path = Path("backend")
        
        if backend_path.exists():
            sys.path.insert(0, str(backend_path.absolute()))
        
        # 모델 임포트 테스트
        from api.models.requests import AgentChatRequest
        from api.models.responses import AgentChatResponse, AgentChatSuggestionResponse
        
        print("✓ AgentChatRequest 임포트 성공")
        print("✓ AgentChatResponse 임포트 성공") 
        print("✓ AgentChatSuggestionResponse 임포트 성공")
        
        # 기본 인스턴스 생성 테스트
        request = AgentChatRequest(query="테스트 쿼리")
        print(f"✓ AgentChatRequest 인스턴스 생성: query='{request.query}'")
        
        response = AgentChatResponse(search_context={})
        print("✓ AgentChatResponse 인스턴스 생성 성공")
        
        return True
        
    except Exception as e:
        print(f"❌ API 모델 임포트 실패: {e}")
        return False

def test_route_imports():
    """라우터 임포트 테스트"""
    print("\n=== 라우터 임포트 테스트 ===")
    
    try:
        # 의존성 모킹 (FastAPI 없이 테스트)
        from unittest.mock import MagicMock
        
        # backend 경로가 sys.path에 있는지 확인
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            backend_path = Path(".")
        else:
            backend_path = Path("backend")
        
        if str(backend_path.absolute()) not in sys.path:
            sys.path.insert(0, str(backend_path.absolute()))
        
        # FastAPI 관련 모듈 모킹
        sys.modules['fastapi'] = MagicMock()
        sys.modules['fastapi.responses'] = MagicMock()
        
        # 라우터 임포트 테스트 
        from api.routes.agent_chat import router
        print("✓ agent_chat 라우터 임포트 성공")
        
        # 라우터 속성 확인
        if hasattr(router, 'prefix'):
            print(f"✓ 라우터 prefix: {router.prefix}")
        
        return True
        
    except Exception as e:
        print(f"❌ 라우터 임포트 실패: {e}")
        return False

def test_route_registration():
    """라우터 등록 확인"""
    print("\n=== 라우터 등록 확인 ===")
    
    try:
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            main_py_path = Path("api/main.py")
        else:
            main_py_path = Path("backend/api/main.py")
        
        if not main_py_path.exists():
            print("❌ main.py 파일을 찾을 수 없음")
            return False
        
        with open(main_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 라우터 임포트 확인
        if "from .routes.agent_chat import router as agent_chat_router" in content:
            print("✓ agent_chat_router 임포트 확인")
        else:
            print("❌ agent_chat_router 임포트 누락")
            return False
        
        # 라우터 등록 확인
        if "app.include_router(agent_chat_router" in content:
            print("✓ agent_chat_router 등록 확인")
        else:
            print("❌ agent_chat_router 등록 누락")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 라우터 등록 확인 실패: {e}")
        return False

def test_orchestrator_integration():
    """AnthropicSearchOrchestrator 통합 테스트"""
    print("\n=== Orchestrator 통합 테스트 ===")
    
    try:
        # 의존성 모킹
        from unittest.mock import MagicMock
        
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            backend_path = Path(".")
        else:
            backend_path = Path("backend")
        
        if str(backend_path.absolute()) not in sys.path:
            sys.path.insert(0, str(backend_path.absolute()))
        
        # 필요한 모듈들 모킹
        sys.modules['boto3'] = MagicMock()
        sys.modules['yaml'] = MagicMock()
        sys.modules['fastapi'] = MagicMock()
        
        # Orchestrator 임포트
        from core.search.anthropic import AnthropicSearchOrchestrator
        print("✓ AnthropicSearchOrchestrator 임포트 성공")
        
        # 기본 인스턴스 생성 (의존성 없이)
        orchestrator = AnthropicSearchOrchestrator()
        print("✓ AnthropicSearchOrchestrator 인스턴스 생성 성공")
        
        # 메서드 존재 확인
        if hasattr(orchestrator, 'execute_agent_search'):
            print("✓ execute_agent_search 메서드 존재")
        else:
            print("❌ execute_agent_search 메서드 누락")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator 통합 테스트 실패: {e}")
        return False

def test_endpoint_definitions():
    """엔드포인트 정의 확인"""
    print("\n=== 엔드포인트 정의 확인 ===")
    
    try:
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            agent_chat_py = Path("api/routes/agent_chat.py")
        else:
            agent_chat_py = Path("backend/api/routes/agent_chat.py")
        
        if not agent_chat_py.exists():
            print("❌ agent_chat.py 파일을 찾을 수 없음")
            return False
        
        with open(agent_chat_py, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 필수 엔드포인트 확인
        required_endpoints = [
            '@router.post("/search")',
            '@router.get("/suggestions"',
            'async def agent_search(',
            'async def get_suggestions('
        ]
        
        all_found = True
        for endpoint in required_endpoints:
            if endpoint in content:
                print(f"✓ {endpoint} 정의 확인")
            else:
                print(f"❌ {endpoint} 정의 누락")
                all_found = False
        
        # 스트리밍 지원 확인
        if "StreamingResponse" in content:
            print("✓ StreamingResponse 지원 확인")
        else:
            print("❌ StreamingResponse 지원 누락")
            all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ 엔드포인트 정의 확인 실패: {e}")
        return False

def test_request_validation():
    """요청 모델 검증 테스트"""
    print("\n=== 요청 모델 검증 테스트 ===")
    
    try:
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            backend_path = Path(".")
        else:
            backend_path = Path("backend")
        
        if str(backend_path.absolute()) not in sys.path:
            sys.path.insert(0, str(backend_path.absolute()))
        
        from api.models.requests import AgentChatRequest
        
        # 기본 요청 생성
        basic_request = AgentChatRequest(query="테스트 쿼리")
        print(f"✓ 기본 요청: {basic_request.query}")
        
        # 선택적 필드 포함 요청
        advanced_request = AgentChatRequest(
            query="고급 테스트 쿼리",
            max_results=5,
            stream=False,
            force_intent="problem_solving",
            search_filters={"category": "technical"}
        )
        print(f"✓ 고급 요청: intent={advanced_request.force_intent}")
        
        # 필드 기본값 확인
        assert basic_request.max_results == 10, "기본 max_results 오류"
        assert basic_request.stream == True, "기본 stream 오류"
        assert basic_request.enable_constitutional_ai == True, "기본 constitutional_ai 오류"
        
        print("✓ 모든 기본값 검증 통과")
        
        return True
        
    except Exception as e:
        print(f"❌ 요청 모델 검증 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 Phase 2 통합 테스트 시작\n")
    
    tests = [
        ("API 모델 임포트", test_model_imports),
        ("라우터 임포트", test_route_imports),
        ("라우터 등록 확인", test_route_registration),
        ("Orchestrator 통합", test_orchestrator_integration),
        ("엔드포인트 정의", test_endpoint_definitions),
        ("요청 모델 검증", test_request_validation)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"테스트: {test_name}")
        print(f"{'='*50}")
        
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
        print("🎉 Phase 2 통합 테스트 모두 통과!")
        print("\n✨ 구현된 API 엔드포인트:")
        print("   • POST /api/agent-chat/search - 상담원 자연어 검색")
        print("   • GET /api/agent-chat/suggestions - 검색 제안")
        print("\n🔧 주요 기능:")
        print("   • Constitutional AI 기반 안전한 응답")
        print("   • 스트리밍 및 일반 응답 지원")
        print("   • 의도 분석 및 우선순위 평가")
        print("   • 기존 HybridSearchManager 통합")
        print("\n📋 Phase 3로 진행할 준비가 완료되었습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 문제를 해결 후 다시 시도하세요.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)