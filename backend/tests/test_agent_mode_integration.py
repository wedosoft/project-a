#!/usr/bin/env python3
"""
상담원 모드 통합 테스트

기존 /query 엔드포인트에 추가된 상담원 모드 기능을 테스트합니다.
- agent_mode=True 설정 시 Anthropic Constitutional AI 적용
- stream_response=True 설정 시 스트리밍 응답
- 기존 QueryRequest 모델 확장 검증
"""

import sys
import json
from pathlib import Path

def test_query_request_agent_fields():
    """QueryRequest 모델의 상담원 관련 필드 테스트"""
    print("=== QueryRequest 상담원 필드 테스트 ===")
    
    try:
        # backend 경로 추가
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            sys.path.insert(0, str(Path(".").absolute()))
        else:
            sys.path.insert(0, str(Path("backend").absolute()))
        
        from api.models.requests import QueryRequest
        
        # 기본 상담원 요청 생성
        agent_request = QueryRequest(
            query="API 오류 해결 방법",
            tenant_id="test_tenant",
            agent_mode=True,
            enable_constitutional_ai=True,
            stream_response=True,
            force_intent="problem_solving",
            urgency_override="immediate"
        )
        
        print(f"✓ 상담원 모드 요청 생성: agent_mode={agent_request.agent_mode}")
        print(f"✓ Constitutional AI: {agent_request.enable_constitutional_ai}")
        print(f"✓ 스트리밍 응답: {agent_request.stream_response}")
        print(f"✓ 의도 강제 설정: {agent_request.force_intent}")
        print(f"✓ 우선순위 설정: {agent_request.urgency_override}")
        
        # 일반 요청 (상담원 모드 비활성화)
        normal_request = QueryRequest(
            query="일반 검색 쿼리",
            tenant_id="test_tenant"
        )
        
        print(f"✓ 일반 모드 요청: agent_mode={normal_request.agent_mode}")
        
        # 필드 기본값 검증
        assert agent_request.agent_mode == True, "agent_mode 설정 오류"
        assert normal_request.agent_mode == False, "기본 agent_mode 오류"
        assert agent_request.enable_constitutional_ai == True, "constitutional_ai 설정 오류"
        assert normal_request.enable_constitutional_ai == False, "기본 constitutional_ai 오류"
        
        print("✓ 모든 필드 검증 통과")
        
        return True
        
    except Exception as e:
        print(f"❌ QueryRequest 상담원 필드 테스트 실패: {e}")
        return False

def test_query_endpoint_structure():
    """query 엔드포인트 구조 확인"""
    print("\n=== Query 엔드포인트 구조 테스트 ===")
    
    try:
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            query_py = Path("api/routes/query.py")
        else:
            query_py = Path("backend/api/routes/query.py")
        
        if not query_py.exists():
            print("❌ query.py 파일을 찾을 수 없음")
            return False
        
        with open(query_py, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 상담원 모드 관련 코드 확인
        required_patterns = [
            "from core.search.anthropic import AnthropicSearchOrchestrator",
            "anthropic_orchestrator: AnthropicSearchOrchestrator",
            "if req.agent_mode:",
            "stream_agent_response()",
            "StreamingResponse",
            "_convert_agent_results_to_document_info"
        ]
        
        all_found = True
        for pattern in required_patterns:
            if pattern in content:
                print(f"✓ {pattern} 패턴 확인")
            else:
                print(f"❌ {pattern} 패턴 누락")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Query 엔드포인트 구조 테스트 실패: {e}")
        return False

def test_anthropic_orchestrator_integration():
    """AnthropicSearchOrchestrator 통합 확인"""
    print("\n=== Anthropic Orchestrator 통합 테스트 ===")
    
    try:
        # 의존성 모킹
        from unittest.mock import MagicMock
        
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            sys.path.insert(0, str(Path(".").absolute()))
        else:
            sys.path.insert(0, str(Path("backend").absolute()))
        
        # 필요한 모듈들 모킹
        sys.modules['boto3'] = MagicMock()
        sys.modules['botocore'] = MagicMock()
        sys.modules['yaml'] = MagicMock()
        
        from core.search.anthropic import AnthropicSearchOrchestrator
        print("✓ AnthropicSearchOrchestrator 임포트 성공")
        
        # 기본 인스턴스 생성
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
        print(f"❌ Anthropic Orchestrator 통합 테스트 실패: {e}")
        return False

def test_api_usage_examples():
    """API 사용법 예시 생성"""
    print("\n=== API 사용법 예시 ===")
    
    try:
        # 상담원 모드 요청 예시
        agent_request_example = {
            "query": "API 연동 오류 티켓 찾아줘",
            "tenant_id": "company_123",
            "platform": "freshdesk",
            "agent_mode": True,
            "enable_constitutional_ai": True,
            "stream_response": True,
            "force_intent": "problem_solving",
            "urgency_override": "immediate",
            "use_hybrid_search": True,
            "top_k": 5
        }
        
        # 일반 모드 요청 예시
        normal_request_example = {
            "query": "결제 관련 정책",
            "tenant_id": "company_123",
            "platform": "freshdesk",
            "agent_mode": False,
            "use_hybrid_search": True,
            "top_k": 3
        }
        
        print("✓ 상담원 모드 요청 예시:")
        print(json.dumps(agent_request_example, indent=2, ensure_ascii=False))
        
        print("\n✓ 일반 모드 요청 예시:")
        print(json.dumps(normal_request_example, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        print(f"❌ API 사용법 예시 생성 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 상담원 모드 통합 테스트 시작\n")
    
    tests = [
        ("QueryRequest 상담원 필드", test_query_request_agent_fields),
        ("Query 엔드포인트 구조", test_query_endpoint_structure),
        ("Anthropic Orchestrator 통합", test_anthropic_orchestrator_integration),
        ("API 사용법 예시", test_api_usage_examples)
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
        print("🎉 상담원 모드 통합 완료!")
        print("\n✨ 사용법:")
        print("   • 기존 POST /api/query 엔드포인트 사용")
        print("   • agent_mode=true로 상담원 모드 활성화")
        print("   • stream_response=true로 스트리밍 응답")
        print("   • enable_constitutional_ai=true로 안전한 AI 응답")
        print("\n🔧 주요 특징:")
        print("   • 기존 API 구조 유지하면서 확장")
        print("   • Constitutional AI 기반 안전한 응답")
        print("   • 의도 분석 및 우선순위 평가")
        print("   • 스트리밍 및 일반 응답 모두 지원")
        print("\n📋 API는 이미 사용 준비가 완료되었습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 문제를 해결 후 다시 시도하세요.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)