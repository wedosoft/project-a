#!/usr/bin/env python3
"""
최종 성능 비교 테스트 - 규칙 기반 vs LLM 기반 첨부파일 선별

현재 10초로 개선된 상황에서 추가로 몇 초를 더 단축할 수 있는지 측정

사용법:
    python test_final_performance_comparison.py
"""

import asyncio
import time
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_attachment_selection_only():
    """첨부파일 선별만 따로 테스트"""
    print("🎯 첨부파일 선별 단독 성능 테스트")
    print("="*50)
    
    # 실제 시나리오와 유사한 샘플 데이터
    sample_attachments = [
        {
            "name": "error_system.log",
            "size": 1024 * 75,
            "content_type": "text/plain",
            "id": "att_001"
        },
        {
            "name": "login_failure_screenshot.png", 
            "size": 1024 * 420,
            "content_type": "image/png",
            "id": "att_002"
        },
        {
            "name": "server_config.json",
            "size": 1024 * 28,
            "content_type": "application/json",
            "id": "att_003"
        },
        {
            "name": "database_backup.sql",
            "size": 1024 * 1024 * 8,  # 8MB
            "content_type": "application/sql",
            "id": "att_004"
        },
        {
            "name": "browser_console_error.png",
            "size": 1024 * 185,
            "content_type": "image/png", 
            "id": "att_005"
        }
    ]
    
    content = """
    긴급 문의드립니다. 오늘 오전부터 모든 사용자가 시스템 로그인이 안 되고 있습니다.
    
    증상:
    - 로그인 버튼 클릭 시 "Authentication failed" 오류
    - 서버 로그에서 database connection error 확인됨
    - 브라우저 콘솔에서도 500 에러 발생
    
    첨부파일:
    - error_system.log: 서버 오류 로그
    - login_failure_screenshot.png: 로그인 실패 화면
    - server_config.json: 현재 서버 설정
    - browser_console_error.png: 브라우저 콘솔 오류
    
    database_backup.sql 파일도 함께 첨부했습니다만 참고용입니다.
    빠른 해결 부탁드립니다.
    """
    
    subject = "긴급 - 전체 시스템 로그인 불가 (error_system.log 첨부)"
    
    print(f"📝 테스트 시나리오:")
    print(f"   티켓 내용: {len(content)}자")
    print(f"   첨부파일: {len(sample_attachments)}개")
    print(f"   직접 언급된 파일: error_system.log")
    print(f"   관련 파일들: screenshot, config, console error")
    
    # 1. 규칙 기반 선별 테스트
    print(f"\n⚡ 1. 규칙 기반 선별:")
    
    from core.llm.summarizer.attachment.selector import AttachmentSelector
    
    rule_selector = AttachmentSelector()
    
    rule_times = []
    for i in range(5):  # 5회 측정
        start_time = time.time()
        rule_selected = rule_selector.select_relevant_attachments(
            attachments=sample_attachments,
            content=content,
            subject=subject
        )
        end_time = time.time()
        rule_times.append(end_time - start_time)
    
    avg_rule_time = sum(rule_times) / len(rule_times)
    
    print(f"   평균 처리 시간: {avg_rule_time:.6f}초 (5회 평균)")
    print(f"   선별된 파일: {len(rule_selected)}개")
    for i, att in enumerate(rule_selected, 1):
        name = att.get('name', 'unknown')
        print(f"     {i}. {name}")
    
    # 2. LLM 기반 선별 테스트
    print(f"\n🤖 2. LLM 기반 선별:")
    
    try:
        from core.llm.summarizer.attachment.llm_selector import LLMAttachmentSelector
        
        llm_selector = LLMAttachmentSelector()
        
        llm_times = []
        for i in range(3):  # 3회 측정 (시간이 오래 걸려서)
            start_time = time.time()
            llm_selected = await llm_selector.select_relevant_attachments(
                attachments=sample_attachments,
                content=content,
                subject=subject
            )
            end_time = time.time()
            llm_times.append(end_time - start_time)
            print(f"     {i+1}회차: {end_time - start_time:.4f}초")
        
        avg_llm_time = sum(llm_times) / len(llm_times)
        
        print(f"   평균 처리 시간: {avg_llm_time:.6f}초 (3회 평균)")
        print(f"   선별된 파일: {len(llm_selected)}개")
        for i, att in enumerate(llm_selected, 1):
            name = att.get('name', 'unknown')
            print(f"     {i}. {name}")
        
        # 성능 비교
        speedup = avg_llm_time / avg_rule_time
        time_saved = avg_llm_time - avg_rule_time
        
        print(f"\n📊 성능 비교 결과:")
        print(f"   규칙 기반: {avg_rule_time:.6f}초")
        print(f"   LLM 기반: {avg_llm_time:.6f}초")
        print(f"   시간 절약: {time_saved:.6f}초")
        print(f"   속도 개선: {speedup:.0f}배")
        print(f"   성능 향상률: {((time_saved/avg_llm_time)*100):.1f}%")
        
        return avg_rule_time, avg_llm_time, len(rule_selected), len(llm_selected)
        
    except Exception as e:
        print(f"   ❌ LLM 기반 선별 테스트 실패: {e}")
        return avg_rule_time, None, len(rule_selected), 0

async def test_real_world_impact():
    """실제 워크플로우에서의 영향 측정"""
    print(f"\n🌍 실제 워크플로우 영향 분석")
    print("="*50)
    
    # 실제 /init 엔드포인트와 유사한 워크플로우 시뮬레이션
    
    rule_time, llm_time, rule_count, llm_count = await test_attachment_selection_only()
    
    # 현재 10초 워크플로우에서의 영향 계산
    current_total_time = 10.0  # 현재 총 소요 시간
    
    if llm_time:
        # LLM 기반을 사용했을 때 예상 시간
        llm_workflow_time = current_total_time + llm_time
        
        # 규칙 기반을 사용했을 때 예상 시간  
        rule_workflow_time = current_total_time + rule_time
        
        print(f"💡 실제 워크플로우에서의 예상 영향:")
        print(f"   현재 총 시간: {current_total_time}초")
        print(f"   + LLM 선별 시: {llm_workflow_time:.2f}초")
        print(f"   + 규칙 선별 시: {rule_workflow_time:.2f}초")
        print(f"   추가 단축 가능: {llm_time:.3f}초")
        print(f"   최종 목표 달성: {'✅' if rule_workflow_time <= 8.0 else '❌'}")
        
        if rule_workflow_time <= 8.0:
            print(f"   🎉 8초 목표 달성! (실제: {rule_workflow_time:.2f}초)")
        else:
            remaining = rule_workflow_time - 8.0
            print(f"   ⚠️  8초 목표까지 {remaining:.2f}초 추가 최적화 필요")
    
    # 품질 분석
    print(f"\n🎯 선별 품질 분석:")
    print(f"   규칙 기반: {rule_count}개 선별")
    print(f"   LLM 기반: {llm_count}개 선별")
    
    if rule_count > 0 and llm_count > 0:
        quality_ratio = rule_count / llm_count
        if quality_ratio >= 0.7:
            print(f"   품질 평가: ✅ 양호 (LLM 대비 {quality_ratio:.1f}배)")
        elif quality_ratio >= 0.5:
            print(f"   품질 평가: ⚠️  보통 (LLM 대비 {quality_ratio:.1f}배)")
        else:
            print(f"   품질 평가: ❌ 개선 필요 (LLM 대비 {quality_ratio:.1f}배)")
    
    return rule_workflow_time if llm_time else current_total_time

async def main():
    """메인 테스트 실행"""
    print("🚀 최종 첨부파일 선별 성능 비교 테스트")
    print("="*60)
    print("현재 상황: 24초 → 10초로 개선 완료")
    print("목표: 추가 최적화로 8초 이하 달성")
    print("="*60)
    
    # 첨부파일 선별 성능 테스트
    final_time = await test_real_world_impact()
    
    # 최종 권장사항
    print(f"\n💡 최종 권장사항")
    print("="*50)
    
    if final_time <= 8.0:
        print("✅ 규칙 기반 첨부파일 선별 사용 적극 권장")
        print("   - 성능 목표 달성")
        print("   - 안정적이고 빠른 처리")
        print("   - API 비용 절약")
    elif final_time <= 10.0:
        print("⚠️  규칙 기반 사용 권장하지만 추가 최적화 필요")
        print("   - 성능 개선은 있으나 목표 미달성")
        print("   - 다른 병목 지점 확인 필요")
    else:
        print("❌ 다른 최적화 방안 검토 필요")
        print("   - 첨부파일 선별 외 다른 병목 존재")
        print("   - 전체 아키텍처 재검토 권장")
    
    print(f"\n🎯 성과 요약:")
    print(f"   최초: 24초")
    print(f"   중간: 10초 (58% 개선)")
    print(f"   최종: {final_time:.2f}초 (예상)")
    print(f"   전체 개선률: {((24 - final_time) / 24 * 100):.1f}%")

if __name__ == "__main__":
    asyncio.run(main())