"""
LLM 기반 첨부파일 선별 테스트 및 사용 예시
"""

import asyncio
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_llm_attachment_selection():
    """LLM 기반 첨부파일 선별 테스트"""
    
    # 샘플 첨부파일 데이터
    sample_attachments = [
        {
            "name": "error_log.txt",
            "content_type": "text/plain", 
            "size": 2048,
            "description": "Application error log file"
        },
        {
            "name": "screenshot.png",
            "content_type": "image/png",
            "size": 1024000,
            "alt_text": "Screenshot of error dialog"
        },
        {
            "name": "config.json",
            "content_type": "application/json",
            "size": 512,
            "description": "Application configuration file"
        },
        {
            "name": "user_manual.pdf",
            "content_type": "application/pdf",
            "size": 5000000,
            "description": "User manual document"
        },
        {
            "name": "random_image.jpg",
            "content_type": "image/jpeg",
            "size": 800000,
            "description": "Unrelated image file"
        }
    ]
    
    # 샘플 티켓 내용
    ticket_content = """
    안녕하세요, 애플리케이션 사용 중 오류가 발생했습니다.

    문제 상황:
    - 로그인 후 메인 화면에서 '데이터 로드 실패' 오류 메시지가 표시됩니다
    - 에러 로그를 확인해보니 데이터베이스 연결 관련 오류가 기록되어 있습니다
    - 스크린샷을 첨부했으니 참고해주세요
    - 설정 파일도 함께 첨부합니다

    재현 방법:
    1. 애플리케이션 실행
    2. 사용자 계정으로 로그인 
    3. 메인 대시보드 접근 시도
    4. 오류 메시지 표시됨

    추가 정보:
    - OS: Windows 10
    - 브라우저: Chrome 최신 버전
    - 오류 발생 시간: 오늘 오전 10시경
    """
    
    ticket_subject = "데이터 로드 실패 오류 문의"
    
    print("=" * 60)
    print("🧪 LLM 기반 첨부파일 선별 테스트")
    print("=" * 60)
    
    try:
        # LLM 기반 선별기 테스트
        from backend.core.llm.summarizer.attachment.llm_selector import LLMAttachmentSelector
        
        selector = LLMAttachmentSelector()
        selected = await selector.select_relevant_attachments(
            attachments=sample_attachments,
            content=ticket_content,
            subject=ticket_subject
        )
        
        print("\n📋 LLM 선별 결과:")
        print(f"전체 첨부파일: {len(sample_attachments)}개")
        print(f"선별된 파일: {len(selected)}개")
        print()
        
        for i, att in enumerate(selected, 1):
            print(f"{i}. 📎 {att['name']}")
            print(f"   타입: {att.get('content_type', 'unknown')}")
            print(f"   크기: {att.get('size', 0):,} bytes")
            
            if 'llm_selection' in att:
                llm_info = att['llm_selection']
                print(f"   관련성 점수: {llm_info.get('relevance_score', 0)}/10")
                print(f"   선별 이유: {llm_info.get('reason', 'N/A')}")
            print()
        
        return selected
        
    except ImportError as e:
        print(f"❌ LLM 선별기 로드 실패: {e}")
        return []
    except Exception as e:
        print(f"❌ 테스트 실행 실패: {e}")
        return []


async def compare_selection_methods():
    """Rule-based vs LLM 기반 선별 방식 비교"""
    
    # 다양한 시나리오의 테스트 데이터
    test_scenarios = [
        {
            "name": "기술 문제 (로그 중심)",
            "subject": "서버 에러 문의",
            "content": "서버에서 500 에러가 발생하고 있습니다. 로그 파일을 확인해주세요.",
            "attachments": [
                {"name": "server.log", "content_type": "text/plain", "size": 3000},
                {"name": "config.yml", "content_type": "text/yaml", "size": 1000},
                {"name": "photo.jpg", "content_type": "image/jpeg", "size": 500000}
            ]
        },
        {
            "name": "UI 문제 (스크린샷 중심)",
            "subject": "화면 표시 오류",
            "content": "버튼이 제대로 표시되지 않습니다. 스크린샷을 첨부했습니다.",
            "attachments": [
                {"name": "screenshot.png", "content_type": "image/png", "size": 200000},
                {"name": "debug.log", "content_type": "text/plain", "size": 5000},
                {"name": "manual.pdf", "content_type": "application/pdf", "size": 2000000}
            ]
        },
        {
            "name": "다국어 문제",
            "subject": "Configuration problem",
            "content": "The application fails to start after configuration change. Please check the settings.",
            "attachments": [
                {"name": "app.config", "content_type": "text/plain", "size": 800},
                {"name": "error_message.png", "content_type": "image/png", "size": 150000},
                {"name": "old_config.bak", "content_type": "application/octet-stream", "size": 900}
            ]
        }
    ]
    
    print("\n" + "=" * 80)
    print("🔄 선별 방식 비교 테스트")
    print("=" * 80)
    
    for scenario in test_scenarios:
        print(f"\n📋 시나리오: {scenario['name']}")
        print(f"제목: {scenario['subject']}")
        print(f"내용: {scenario['content'][:100]}...")
        print(f"첨부파일: {len(scenario['attachments'])}개")
        
        try:
            # Rule-based 선별
            from backend.core.llm.summarizer.attachment.selector import select_relevant_attachments
            rule_selected = select_relevant_attachments(
                attachments=scenario['attachments'],
                content=scenario['content'],
                subject=scenario['subject']
            )
            
            # LLM 기반 선별
            from backend.core.llm.summarizer.attachment.llm_selector import LLMAttachmentSelector
            llm_selector = LLMAttachmentSelector()
            llm_selected = await llm_selector.select_relevant_attachments(
                attachments=scenario['attachments'],
                content=scenario['content'],
                subject=scenario['subject']
            )
            
            print(f"\n📊 결과 비교:")
            print(f"Rule-based: {len(rule_selected)}개 선별 → {[f['name'] for f in rule_selected]}")
            print(f"LLM-based:  {len(llm_selected)}개 선별 → {[f['name'] for f in llm_selected]}")
            
            # 차이점 분석
            rule_names = set(f['name'] for f in rule_selected)
            llm_names = set(f['name'] for f in llm_selected)
            
            if rule_names != llm_names:
                print(f"🔍 차이점:")
                if rule_names - llm_names:
                    print(f"  Rule-only: {rule_names - llm_names}")
                if llm_names - rule_names:
                    print(f"  LLM-only:  {llm_names - rule_names}")
            else:
                print("✅ 두 방식 모두 동일한 결과")
                
        except Exception as e:
            print(f"❌ 비교 테스트 실패: {e}")
        
        print("-" * 50)


async def test_summarizer_with_llm_attachment_selection():
    """LLM 첨부파일 선별을 포함한 전체 요약 생성 테스트"""
    
    print("\n" + "=" * 80)
    print("🧠 LLM 첨부파일 선별 + 요약 생성 통합 테스트")
    print("=" * 80)
    
    try:
        from backend.core.llm.summarizer.core.summarizer import CoreSummarizer
        
        # LLM 첨부파일 선별을 활성화한 요약기 생성
        summarizer = CoreSummarizer(use_llm_attachment_selector=True)
        
        # 테스트 데이터
        content = """
        고객 문의: 결제 시스템 연동 오류

        안녕하세요. 온라인 쇼핑몰에서 결제 시스템 연동 중 문제가 발생했습니다.

        증상:
        - 신용카드 결제 시 "결제 승인 실패" 메시지 표시
        - 로그에서 API 통신 오류 확인됨
        - PG사 API 키 설정은 정상적으로 되어있음

        첨부 파일:
        - 에러 로그 파일
        - 결제 실패 화면 스크린샷  
        - PG 연동 설정 화면 캡처
        - API 설정 JSON 파일

        긴급도: 높음 (매출에 직접적 영향)
        """
        
        metadata = {
            "attachments": [
                {
                    "name": "payment_error.log",
                    "content_type": "text/plain",
                    "size": 4096,
                    "description": "Payment system error log"
                },
                {
                    "name": "payment_fail_screen.png", 
                    "content_type": "image/png",
                    "size": 250000,
                    "alt_text": "Screenshot of payment failure"
                },
                {
                    "name": "pg_config_screen.png",
                    "content_type": "image/png", 
                    "size": 180000,
                    "alt_text": "PG configuration screen"
                },
                {
                    "name": "api_config.json",
                    "content_type": "application/json",
                    "size": 1024,
                    "description": "Payment API configuration"
                },
                {
                    "name": "unrelated_doc.pdf",
                    "content_type": "application/pdf",
                    "size": 3000000,
                    "description": "Unrelated documentation"
                }
            ]
        }
        
        summary = await summarizer.generate_summary(
            content=content,
            content_type="ticket",
            subject="결제 시스템 연동 오류 문의",
            metadata=metadata,
            ui_language="ko"
        )
        
        print("✅ 요약 생성 성공!")
        print("\n📄 생성된 요약:")
        print("-" * 40)
        print(summary)
        print("-" * 40)
        
        return summary
        
    except Exception as e:
        print(f"❌ 통합 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """메인 테스트 실행"""
    print("🚀 LLM 기반 첨부파일 선별 시스템 테스트 시작")
    
    # 개별 LLM 선별 테스트
    await test_llm_attachment_selection()
    
    # 선별 방식 비교
    await compare_selection_methods()
    
    # 전체 통합 테스트
    await test_summarizer_with_llm_attachment_selection()
    
    print("\n✅ 모든 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
