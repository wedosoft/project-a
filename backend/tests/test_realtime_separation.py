#!/usr/bin/env python3
"""
실시간 요약 시스템 분리 확인 테스트

실시간 요약이 기존 유사티켓/지식베이스 프롬프트와 완전히 분리되어 작동하는지 확인
"""

import sys
import os

# 백엔드 모듈 경로 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

def test_prompt_separation():
    """프롬프트 분리 상태 테스트"""
    print("🔍 실시간 요약 시스템 분리 확인 테스트")
    print("=" * 60)
    
    try:
        # 1. 실시간 요약 전용 프롬프트 로더 테스트
        from core.llm.summarizer.prompt.realtime_loader import RealtimePromptLoader
        
        realtime_loader = RealtimePromptLoader()
        realtime_info = realtime_loader.get_prompt_info()
        
        print("✅ 실시간 요약 프롬프트 로더:")
        print(f"   - 타입: {realtime_info['type']}")
        print(f"   - 품질 레벨: {realtime_info['quality_level']}")
        print(f"   - 목적: {realtime_info['purpose']}")
        print(f"   - 특징: {', '.join(realtime_info['features'])}")
        print()
        
        # 2. 기존 유사티켓/지식베이스 프롬프트 로더 테스트
        from core.llm.summarizer.prompt.builder import PromptBuilder
        from core.llm.summarizer.prompt.loader import get_prompt_loader
        
        print("✅ 기존 유사티켓/지식베이스 프롬프트:")
        
        # 기존 프롬프트 로더
        existing_loader = get_prompt_loader()
        
        # 시스템 프롬프트 확인
        ticket_system = existing_loader.get_system_prompt_template("ticket")
        kb_system = existing_loader.get_system_prompt_template("knowledge_base")
        
        print(f"   - 유사티켓 프롬프트: content_type={ticket_system.get('content_type', 'unknown')}")
        print(f"   - 지식베이스 프롬프트: content_type={kb_system.get('content_type', 'unknown')}")
        print()
        
        # 3. 분리 확인
        print("🎯 분리 상태 확인:")
        
        realtime_content_type = realtime_info['type']
        existing_ticket_type = ticket_system.get('content_type', 'unknown')
        existing_kb_type = kb_system.get('content_type', 'unknown')
        
        if realtime_content_type != existing_ticket_type and realtime_content_type != existing_kb_type:
            print("✅ 완벽 분리: 실시간 요약이 기존 프롬프트와 독립적으로 작동")
        else:
            print("❌ 분리 실패: 실시간 요약이 기존 프롬프트와 겹침")
        
        print(f"   - 실시간: {realtime_content_type}")
        print(f"   - 유사티켓: {existing_ticket_type}")
        print(f"   - 지식베이스: {existing_kb_type}")
        print()
        
        # 4. 실시간 요약 체인 테스트
        from core.llm.integrations.langchain.chains.summarization import SummarizationChain
        from core.llm.manager import LLMManager
        
        # LLM Manager 초기화 (실제 API 호출 없이)
        llm_manager = LLMManager()
        summary_chain = SummarizationChain(llm_manager)
        
        print("✅ 실시간 요약 체인 초기화 성공")
        print()
        
        # 5. 프롬프트 파일 존재 확인
        import os
        base_path = "/Users/alan/GitHub/project-a/backend/core/llm/summarizer/prompt/templates"
        
        files_to_check = {
            "실시간 시스템": f"{base_path}/system/realtime_ticket.yaml",
            "실시간 사용자": f"{base_path}/user/realtime_ticket.yaml",
            "유사티켓 시스템": f"{base_path}/system/ticket.yaml",
            "유사티켓 사용자": f"{base_path}/user/ticket.yaml",
            "지식베이스 시스템": f"{base_path}/system/knowledge_base.yaml",
            "지식베이스 사용자": f"{base_path}/user/knowledge_base.yaml"
        }
        
        print("📁 프롬프트 파일 존재 확인:")
        all_exist = True
        for name, path in files_to_check.items():
            if os.path.exists(path):
                print(f"   ✅ {name}: 존재")
            else:
                print(f"   ❌ {name}: 없음 - {path}")
                all_exist = False
        
        print()
        
        # 6. 최종 결과
        print("🏆 최종 결과:")
        if all_exist and realtime_content_type not in [existing_ticket_type, existing_kb_type]:
            print("✅ 완벽한 분리 성공!")
            print("   - 실시간 요약: 독립적 프롬프트 사용")
            print("   - 유사티켓 요약: 기존 프롬프트 보존")
            print("   - 지식베이스 요약: 기존 프롬프트 보존")
            print("   - 모든 시스템이 독립적으로 작동 가능")
        else:
            print("❌ 분리 미완성")
            print("   - 일부 파일이 누락되거나 겹치는 부분이 있습니다.")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_prompt_separation()
