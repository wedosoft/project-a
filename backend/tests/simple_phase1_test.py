#!/usr/bin/env python3
"""
간소화된 Phase 1 기본 구조 테스트

의존성 없이 파일 구조와 기본 임포트만 테스트합니다.
"""

import sys
import os
from pathlib import Path

def test_file_structure():
    """Phase 1에서 생성한 파일들이 올바른 위치에 있는지 확인"""
    print("=== 파일 구조 테스트 ===")
    
    # 현재 실행 위치에 따라 backend 경로 조정
    current_dir = Path.cwd()
    if current_dir.name == "backend":
        backend_path = Path(".")
    else:
        backend_path = Path("backend")
    
    required_files = [
        "core/search/anthropic/__init__.py",
        "core/search/anthropic/intent_analyzer.py", 
        "core/search/anthropic/search_orchestrator.py",
        "core/search/prompts/constitutional_search.yaml"
    ]
    
    all_exist = True
    for file_path in required_files:
        full_path = backend_path / file_path
        if full_path.exists():
            print(f"✓ {file_path} 존재")
        else:
            print(f"❌ {file_path} 누락")
            all_exist = False
    
    return all_exist

def test_yaml_structure():
    """YAML 파일 구조 확인"""
    print("\n=== YAML 구조 테스트 ===")
    
    try:
        import yaml
        # 현재 실행 위치에 따라 경로 조정
        current_dir = Path.cwd()
        if current_dir.name == "backend":
            yaml_path = Path("core/search/prompts/constitutional_search.yaml")
        else:
            yaml_path = Path("backend/core/search/prompts/constitutional_search.yaml")
        
        if not yaml_path.exists():
            print("❌ YAML 파일 없음")
            return False
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 필수 섹션 확인
        required_sections = [
            'constitutional_principles',
            'system_prompt', 
            'intent_prompts',
            'safety_guidelines'
        ]
        
        all_sections_exist = True
        for section in required_sections:
            if section in data:
                print(f"✓ {section} 섹션 존재")
            else:
                print(f"❌ {section} 섹션 누락")
                all_sections_exist = False
        
        return all_sections_exist
        
    except Exception as e:
        print(f"❌ YAML 테스트 실패: {e}")
        return False

def test_python_syntax():
    """Python 파일들의 기본 문법 확인"""
    print("\n=== Python 문법 테스트 ===")
    
    # 현재 실행 위치에 따라 경로 조정
    current_dir = Path.cwd()
    if current_dir.name == "backend":
        python_files = [
            "core/search/anthropic/__init__.py",
            "core/search/anthropic/intent_analyzer.py",
            "core/search/anthropic/search_orchestrator.py"
        ]
    else:
        python_files = [
            "backend/core/search/anthropic/__init__.py",
            "backend/core/search/anthropic/intent_analyzer.py",
            "backend/core/search/anthropic/search_orchestrator.py"
        ]
    
    all_valid = True
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            # 기본 문법 체크 (컴파일만)
            compile(source, file_path, 'exec')
            print(f"✓ {Path(file_path).name} 문법 올바름")
            
        except SyntaxError as e:
            print(f"❌ {Path(file_path).name} 문법 오류: {e}")
            all_valid = False
        except Exception as e:
            print(f"❌ {Path(file_path).name} 읽기 실패: {e}")
            all_valid = False
    
    return all_valid

def test_class_definitions():
    """클래스 정의 확인 (간단한 텍스트 검색)"""
    print("\n=== 클래스 정의 테스트 ===")
    
    # 현재 실행 위치에 따라 경로 조정
    current_dir = Path.cwd()
    if current_dir.name == "backend":
        class_checks = [
            ("core/search/anthropic/intent_analyzer.py", ["class AnthropicIntentAnalyzer", "class SearchContext"]),
            ("core/search/anthropic/search_orchestrator.py", ["class AnthropicSearchOrchestrator"])
        ]
    else:
        class_checks = [
            ("backend/core/search/anthropic/intent_analyzer.py", ["class AnthropicIntentAnalyzer", "class SearchContext"]),
            ("backend/core/search/anthropic/search_orchestrator.py", ["class AnthropicSearchOrchestrator"])
        ]
    
    all_classes_found = True
    for file_path, class_names in class_checks:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for class_name in class_names:
                if class_name in content:
                    print(f"✓ {class_name} 정의됨")
                else:
                    print(f"❌ {class_name} 누락")
                    all_classes_found = False
                    
        except Exception as e:
            print(f"❌ {file_path} 확인 실패: {e}")
            all_classes_found = False
    
    return all_classes_found

def main():
    """메인 테스트 함수"""
    print("🚀 Phase 1 간소화 구조 테스트 시작\n")
    
    tests = [
        ("파일 구조", test_file_structure),
        ("YAML 구조", test_yaml_structure), 
        ("Python 문법", test_python_syntax),
        ("클래스 정의", test_class_definitions)
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
        print("🎉 Phase 1 기본 구조 테스트 모두 통과!")
        print("\n✨ Phase 2로 진행할 준비가 완료되었습니다.")
        print("\n📋 생성된 파일들:")
        print("   • AnthropicIntentAnalyzer (의도 분석기)")
        print("   • AnthropicSearchOrchestrator (검색 오케스트레이터)")
        print("   • Constitutional AI 프롬프트 템플릿")
        print("   • 모듈 초기화 파일")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 문제를 해결 후 다시 시도하세요.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)