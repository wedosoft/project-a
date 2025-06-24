#!/usr/bin/env python3
"""
첨부파일 메타데이터 저장 테스트
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_attachment_metadata():
    """첨부파일 메타데이터 저장 및 요약 생성 테스트"""
    
    from core.llm.optimized_summarizer import generate_optimized_summary
    
    # 테스트 메타데이터 (실제 수집 과정에서 생성되는 형태)
    test_metadata = {
        'ticket_id': 'test-12345',
        'status': 'open',
        'priority': 'high',
        'attachments': [
            {
                'id': '1',
                'name': 'ja-JP.yml',
                'content_type': 'text/yaml',
                'size': 2048,
                'attachment_url': 'https://test.com/attachment/1'
            },
            {
                'id': '2',
                'name': 'new_ticket_jp.PNG', 
                'content_type': 'image/png',
                'size': 512000,
                'attachment_url': 'https://test.com/attachment/2'
            },
            {
                'id': '3',
                'name': 'error_log.log',
                'content_type': 'text/plain', 
                'size': 8192,
                'attachment_url': 'https://test.com/attachment/3'
            }
        ]
    }
    
    # 테스트 티켓 내용
    test_content = """
    안녕하세요. 위두소프트 최소현입니다.
    
    일본어 지원을 위해 티켓 필드 번역 파일(yml) 업로드 후,
    기본 파일이 계속 다운로드되는 현상이 발생했습니다.
    
    ja-JP.yml 파일을 업로드했지만 번역이 적용되지 않고 있습니다.
    new_ticket_jp.PNG 스크린샷을 참조해주세요.
    
    문제가 무엇인지 확인 부탁드립니다.
    """
    
    test_subject = "일본어 번역 파일 적용 문제"
    
    print("🧪 첨부파일 메타데이터 테스트 시작...")
    print(f"📎 첨부파일 개수: {len(test_metadata['attachments'])}개")
    
    try:
        # 요약 생성 테스트
        summary = await generate_optimized_summary(
            content=test_content,
            content_type="ticket",
            subject=test_subject,
            metadata=test_metadata,
            ui_language="ko"
        )
        
        print("\n✅ 요약 생성 완료:")
        print("=" * 50)
        print(summary)
        print("=" * 50)
        
        # 첨부파일이 요약에 포함되었는지 확인
        if "📎" in summary:
            print("\n✅ 첨부파일이 요약에 포함됨!")
            # 포함된 파일명 추출
            import re
            attachment_lines = re.findall(r'📎\s*([^\n]+)', summary)
            for i, filename in enumerate(attachment_lines, 1):
                print(f"  {i}. {filename.strip()}")
        else:
            print("\n❌ 첨부파일이 요약에 포함되지 않음")
            
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_attachment_metadata())
