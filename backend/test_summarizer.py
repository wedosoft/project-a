#!/usr/bin/env python3
"""
요약기 직접 테스트용 스크립트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from core.llm.optimized_summarizer import generate_optimized_summary

async def test_summarizer():
    """요약기 테스트"""
    
    # 샘플 티켓 내용
    sample_ticket = """
    From: sohyun.choi@widusoft.co.kr
    Date: 2024-11-26
    Subject: 일본어 번역 파일 업로드 문제
    
    안녕하세요, 위두소프트의 최소현입니다.
    
    Freshdesk에서 일본어 번역 파일(yml)을 업로드했는데, 다운로드 시 기본 파일이 나타나는 문제가 발생했습니다.
    
    - 일본어 언어 추가 완료
    - 번역 파일 업로드 시도
    - 다운로드 시 원본 파일이 아닌 기본 파일이 표시됨
    
    2024년 11월 26일부터 지속되는 문제입니다.
    파일 형식 문제인지 확인이 필요합니다.
    
    --
    최소현
    위두소프트
    sohyun.choi@widusoft.co.kr
    """
    
    print("=== 요약기 테스트 시작 ===")
    print(f"원본 길이: {len(sample_ticket)} 문자")
    print()
    
    try:
        # 첫 번째 테스트: 기본 요약 (metadata 없이)
        print("--- 테스트 1: 기본 요약 ---")
        summary_only = await generate_optimized_summary(
            content=sample_ticket,
            content_type="ticket", 
            subject="일본어 번역 파일 업로드 문제",
            metadata={
                'status': 'Open',
                'priority': 'Medium',
                'created_at': '2024-11-26',
                'ticket_id': '12345',
                'attachments': [
                    {
                        'id': 5174859785,
                        'name': 'japanese_translation.yml',
                        'content_type': 'application/x-yaml',
                        'size': 15420,
                        'ticket_id': 12345,
                        'conversation_id': None,
                        'attachment_url': 'https://widusoft.freshdesk.com/helpdesk/attachments/5174859785'
                    },
                    {
                        'id': 5174859786,
                        'name': 'screenshot_error.png',
                        'content_type': 'image/png',
                        'size': 245680,
                        'ticket_id': 12345,
                        'conversation_id': None,
                        'attachment_url': 'https://s3.amazonaws.com/freshdesk-prod/attachments/screenshot_error.png'
                    },
                    {
                        'id': 5174859787,
                        'name': 'system_log.txt',
                        'content_type': 'text/plain',
                        'size': 8420,
                        'ticket_id': 12345,
                        'conversation_id': 67890
                    }
                ]
            },
            ui_language="ko"
        )
        
        print(summary_only)
        print("\n" + "="*60 + "\n")
        
        # 두 번째 테스트: metadata와 함께 반환
        print("--- 테스트 2: 메타데이터와 함께 ---")
        result = await generate_optimized_summary(
            content=sample_ticket,
            content_type="ticket", 
            subject="일본어 번역 파일 업로드 문제",
            metadata={
                'status': 'Open',
                'priority': 'Medium',
                'created_at': '2024-11-26',
                'ticket_id': '12345',
                'attachments': [
                    {
                        'id': 5174859785,
                        'name': 'japanese_translation.yml',
                        'content_type': 'application/x-yaml',
                        'size': 15420,
                        'ticket_id': 12345,
                        'conversation_id': None,
                        'attachment_url': 'https://widusoft.freshdesk.com/helpdesk/attachments/5174859785'
                    },
                    {
                        'id': 5174859786,
                        'name': 'screenshot_error.png',
                        'content_type': 'image/png',
                        'size': 245680,
                        'ticket_id': 12345,
                        'conversation_id': None,
                        'attachment_url': 'https://s3.amazonaws.com/freshdesk-prod/attachments/screenshot_error.png'
                    },
                    {
                        'id': 5174859787,
                        'name': 'system_log.txt',
                        'content_type': 'text/plain',
                        'size': 8420,
                        'ticket_id': 12345,
                        'conversation_id': 67890
                    }
                ]
            },
            ui_language="ko",
            return_metadata=True
        )
        
        if isinstance(result, tuple):
            summary, metadata = result
            print("=== 생성된 요약 ===")
            print(summary)
            print("\n=== 반환된 메타데이터 ===")
            import json
            print(json.dumps(metadata, indent=2, ensure_ascii=False))
        else:
            summary = result
            print("=== 생성된 요약 (메타데이터 없음) ===")
            print(summary)
        print()
        
        # 문제 체크
        problematic_phrases = [
            "원문에서 충분한 정보가 제공되지 않아",
            "해결 과정이 아직 시작되지 않았습니다",
            "추가 정보 제공 시",
            "insufficient information",
            "more information needed",
            "위두소프트 (Widusoft)",
            "(English",
            "(한글"
        ]
        
        # 요약 텍스트 선택 (metadata와 함께 반환된 경우 첫 번째 요소 사용)
        summary_text = summary if isinstance(result, str) else result[0] if isinstance(result, tuple) else summary_only
        
        found_issues = []
        for phrase in problematic_phrases:
            if phrase in summary_text:
                found_issues.append(phrase)
        
        if found_issues:
            print("❌ 발견된 문제:")
            for issue in found_issues:
                print(f"  - '{issue}' 발견됨")
        else:
            print("✅ 문제 없음: fallback 문구와 불필요한 병기 표현이 없습니다")
            
        # 고객사 식별 체크
        if "위두소프트" in summary_text and "최소현" in summary_text:
            print("✅ 고객사 정보 정확히 식별됨")
        else:
            print("❌ 고객사 정보 식별에 문제가 있을 수 있습니다")
            
        # 메타데이터 체크
        if isinstance(result, tuple) and len(result) == 2:
            summary, metadata = result
            print("\n=== 메타데이터 검증 ===")
            if 'attachments' in metadata:
                print(f"✅ 첨부파일 정보: {len(metadata['attachments'])}개")
                for i, att in enumerate(metadata['attachments']):
                    print(f"  {i+1}. {att.get('name', 'Unknown')} (ID: {att.get('id', 'N/A')})")
                    if 'attachment_url' in att:
                        print(f"     URL: {att['attachment_url']}")
            else:
                print("❌ 첨부파일 정보가 메타데이터에 없습니다")
        else:
            print("ℹ️  메타데이터 반환 테스트를 실행하지 않았습니다")
            
    except Exception as e:
        print(f"❌ 요약 생성 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_summarizer())
