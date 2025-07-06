#!/usr/bin/env python3
"""
첨부파일 선별 성능 비교 테스트

LLM 기반 vs 규칙 기반 선별의 성능과 품질을 비교합니다.

사용법:
    python test_attachment_selection_performance.py
"""

import asyncio
import time
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.llm.summarizer.core.summarizer import CoreSummarizer
from core.llm.summarizer.attachment.selector import AttachmentSelector

async def test_rule_based_selection_performance():
    """규칙 기반 선별 성능 테스트"""
    print("⚡ 규칙 기반 첨부파일 선별 성능 테스트...")
    
    # 샘플 첨부파일 데이터 (다양한 타입)
    sample_attachments = [
        {
            "name": "error_log.txt",
            "size": 1024 * 50,
            "content_type": "text/plain",
            "id": "1001"
        },
        {
            "name": "user_screenshot.png", 
            "size": 1024 * 300,
            "content_type": "image/png",
            "id": "1002"
        },
        {
            "name": "system_config.json",
            "size": 1024 * 15,
            "content_type": "application/json", 
            "id": "1003"
        },
        {
            "name": "backup_database.sql",
            "size": 1024 * 1024 * 5,  # 5MB
            "content_type": "application/sql",
            "id": "1004"
        },
        {
            "name": "user_manual.pdf",
            "size": 1024 * 1024 * 2,  # 2MB
            "content_type": "application/pdf",
            "id": "1005"
        },
        {
            "name": "temp_file.tmp",
            "size": 1024 * 5,
            "content_type": "application/octet-stream",
            "id": "1006"
        }
    ]
    
    # 샘플 티켓 내용
    content = """
    고객이 로그인 시 오류가 발생한다고 문의했습니다.
    error_log.txt 파일을 확인해보니 authentication failed 메시지가 있습니다.
    스크린샷도 첨부했으니 확인 부탁드립니다.
    시스템 설정도 함께 점검이 필요할 것 같습니다.
    """
    
    subject = "로그인 오류 문의 - error_log.txt 첨부"
    
    # 규칙 기반 선별 테스트
    selector = AttachmentSelector()
    
    start_time = time.time()
    selected_attachments = selector.select_relevant_attachments(
        attachments=sample_attachments,
        content=content,
        subject=subject
    )
    end_time = time.time()
    
    rule_time = end_time - start_time
    
    print(f"📊 규칙 기반 선별 결과:")
    print(f"   처리 시간: {rule_time:.4f}초")
    print(f"   선별된 파일 수: {len(selected_attachments)}/{len(sample_attachments)}")
    
    for i, attachment in enumerate(selected_attachments, 1):
        name = attachment.get('name', 'unknown')
        score = attachment.get('relevance_score', 0)
        print(f"   {i}. {name} (점수: {score})")
    
    return rule_time, selected_attachments

async def test_llm_based_selection_performance():
    """LLM 기반 선별 성능 테스트"""
    print("\n🤖 LLM 기반 첨부파일 선별 성능 테스트...")
    
    try:
        from core.llm.summarizer.attachment.llm_selector import LLMAttachmentSelector
        
        # 동일한 샘플 데이터 사용
        sample_attachments = [
            {
                "name": "error_log.txt",
                "size": 1024 * 50,
                "content_type": "text/plain",
                "id": "1001"
            },
            {
                "name": "user_screenshot.png", 
                "size": 1024 * 300,
                "content_type": "image/png",
                "id": "1002"
            },
            {
                "name": "system_config.json",
                "size": 1024 * 15,
                "content_type": "application/json", 
                "id": "1003"
            },
            {
                "name": "backup_database.sql",
                "size": 1024 * 1024 * 5,
                "content_type": "application/sql",
                "id": "1004"
            },
            {
                "name": "user_manual.pdf",
                "size": 1024 * 1024 * 2,
                "content_type": "application/pdf",
                "id": "1005"
            },
            {
                "name": "temp_file.tmp",
                "size": 1024 * 5,
                "content_type": "application/octet-stream",
                "id": "1006"
            }
        ]
        
        content = """
        고객이 로그인 시 오류가 발생한다고 문의했습니다.
        error_log.txt 파일을 확인해보니 authentication failed 메시지가 있습니다.
        스크린샷도 첨부했으니 확인 부탁드립니다.
        시스템 설정도 함께 점검이 필요할 것 같습니다.
        """
        
        subject = "로그인 오류 문의 - error_log.txt 첨부"
        
        # LLM 기반 선별 테스트
        llm_selector = LLMAttachmentSelector()
        
        start_time = time.time()
        selected_attachments = await llm_selector.select_relevant_attachments(
            attachments=sample_attachments,
            content=content,
            subject=subject
        )
        end_time = time.time()
        
        llm_time = end_time - start_time
        
        print(f"📊 LLM 기반 선별 결과:")
        print(f"   처리 시간: {llm_time:.4f}초")
        print(f"   선별된 파일 수: {len(selected_attachments)}/{len(sample_attachments)}")
        
        for i, attachment in enumerate(selected_attachments, 1):
            name = attachment.get('name', 'unknown')
            score = attachment.get('relevance_score', 0)
            reason = attachment.get('selection_reason', 'N/A')
            print(f"   {i}. {name} (점수: {score}) - {reason}")
        
        return llm_time, selected_attachments
        
    except Exception as e:
        print(f"❌ LLM 기반 선별 테스트 실패: {e}")
        return None, []

async def test_summarizer_performance_comparison():
    """Summarizer 전체 성능 비교"""
    print("\n📈 Summarizer 전체 성능 비교...")
    
    # 샘플 티켓 데이터
    ticket_data = {
        "id": "12345",
        "subject": "로그인 오류 긴급 해결 요청",
        "description": """
        고객사 ABC에서 오늘 오전부터 모든 직원이 시스템에 로그인할 수 없는 상황입니다.
        
        발생 현상:
        - 로그인 버튼 클릭 시 "Authentication failed" 오류
        - 브라우저 콘솔에서 500 에러 확인
        - 다른 브라우저에서도 동일한 현상
        
        첨부 파일:
        - error_log.txt: 서버 로그 파일
        - login_screenshot.png: 오류 화면 캡처
        - browser_console.png: 브라우저 콘솔 오류
        - system_config.json: 현재 시스템 설정
        
        빠른 해결 부탁드립니다.
        """,
        "attachments": [
            {"name": "error_log.txt", "size": 1024*50, "content_type": "text/plain", "id": "2001"},
            {"name": "login_screenshot.png", "size": 1024*300, "content_type": "image/png", "id": "2002"},
            {"name": "browser_console.png", "size": 1024*250, "content_type": "image/png", "id": "2003"},
            {"name": "system_config.json", "size": 1024*20, "content_type": "application/json", "id": "2004"},
        ]
    }
    
    # 1. 규칙 기반 Summarizer 테스트
    print("\n1️⃣ 규칙 기반 Summarizer:")
    rule_summarizer = CoreSummarizer(use_llm_attachment_selector=False)
    
    start_time = time.time()
    try:
        rule_summary = await rule_summarizer.generate_ticket_summary(
            ticket_data=ticket_data,
            use_case="ticket_view",
            ui_language="ko"
        )
        rule_total_time = time.time() - start_time
        print(f"   ✅ 총 처리 시간: {rule_total_time:.4f}초")
        print(f"   📄 요약 길이: {len(rule_summary.get('content', ''))}자")
        
    except Exception as e:
        print(f"   ❌ 규칙 기반 요약 실패: {e}")
        rule_total_time = None
    
    # 2. LLM 기반 Summarizer 테스트
    print("\n2️⃣ LLM 기반 Summarizer:")
    llm_summarizer = CoreSummarizer(use_llm_attachment_selector=True)
    
    start_time = time.time()
    try:
        llm_summary = await llm_summarizer.generate_ticket_summary(
            ticket_data=ticket_data,
            use_case="ticket_view",
            ui_language="ko"
        )
        llm_total_time = time.time() - start_time
        print(f"   ✅ 총 처리 시간: {llm_total_time:.4f}초")
        print(f"   📄 요약 길이: {len(llm_summary.get('content', ''))}자")
        
    except Exception as e:
        print(f"   ❌ LLM 기반 요약 실패: {e}")
        llm_total_time = None
    
    # 성능 비교
    if rule_total_time and llm_total_time:
        time_diff = llm_total_time - rule_total_time
        improvement = (time_diff / llm_total_time) * 100
        
        print(f"\n📊 성능 비교:")
        print(f"   규칙 기반: {rule_total_time:.4f}초")
        print(f"   LLM 기반: {llm_total_time:.4f}초") 
        print(f"   시간 절약: {time_diff:.4f}초 ({improvement:.1f}% 개선)")
    
    return rule_total_time, llm_total_time

async def main():
    """메인 테스트 실행"""
    print("🚀 첨부파일 선별 성능 비교 테스트 시작\n")
    
    # 1. 규칙 기반 선별 성능 테스트
    rule_time, rule_selected = await test_rule_based_selection_performance()
    
    # 2. LLM 기반 선별 성능 테스트
    llm_time, llm_selected = await test_llm_based_selection_performance()
    
    # 3. 전체 Summarizer 성능 비교
    rule_total, llm_total = await test_summarizer_performance_comparison()
    
    # 결과 요약
    print("\n" + "="*60)
    print("📋 종합 성능 분석 결과")
    print("="*60)
    
    if llm_time:
        selection_speedup = llm_time / rule_time if rule_time > 0 else 0
        print(f"📎 첨부파일 선별만:")
        print(f"   규칙 기반: {rule_time:.4f}초")
        print(f"   LLM 기반: {llm_time:.4f}초")
        print(f"   속도 개선: {selection_speedup:.1f}배")
    
    if rule_total and llm_total:
        total_speedup = llm_total / rule_total
        time_saved = llm_total - rule_total
        print(f"\n🏆 전체 Summarizer:")
        print(f"   규칙 기반: {rule_total:.4f}초")
        print(f"   LLM 기반: {llm_total:.4f}초")
        print(f"   시간 절약: {time_saved:.4f}초")
        print(f"   성능 개선: {((time_saved/llm_total)*100):.1f}%")
    
    # 품질 분석
    print(f"\n🎯 선별 품질 분석:")
    print(f"   규칙 기반 선별: {len(rule_selected)}개 파일")
    if rule_selected:
        rule_files = [att.get('name', 'unknown') for att in rule_selected]
        print(f"     선별된 파일: {', '.join(rule_files)}")
    
    if llm_selected:
        print(f"   LLM 기반 선별: {len(llm_selected)}개 파일")
        llm_files = [att.get('name', 'unknown') for att in llm_selected]
        print(f"     선별된 파일: {', '.join(llm_files)}")
        
        # 선별 결과 일치도
        rule_names = set(att.get('name', '') for att in rule_selected)
        llm_names = set(att.get('name', '') for att in llm_selected)
        
        if rule_names and llm_names:
            overlap = len(rule_names & llm_names)
            total_unique = len(rule_names | llm_names)
            similarity = (overlap / total_unique) * 100 if total_unique > 0 else 0
            print(f"     선별 결과 유사도: {similarity:.1f}%")
    
    print(f"\n💡 권장사항:")
    if rule_time and llm_time and llm_time > rule_time * 10:
        print(f"   ✅ 규칙 기반 선별 사용 권장 (성능 중심)")
        print(f"   ⚡ {llm_time:.1f}초 → {rule_time:.4f}초로 대폭 개선")
    else:
        print(f"   🤔 성능 차이가 크지 않아 품질 기준으로 선택 가능")

if __name__ == "__main__":
    asyncio.run(main())