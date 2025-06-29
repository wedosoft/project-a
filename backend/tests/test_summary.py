#!/usr/bin/env python3
"""
요약 시스템 테스트 스크립트
"""

import asyncio
import logging
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm.manager import get_llm_manager

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_summary():
    try:
        print("=== LLM 매니저 요약 테스트 ===")
        llm_manager = get_llm_manager()
        
        # 테스트 티켓 데이터 (첨부파일 포함)
        ticket_data = {
            'id': 'test_001',
            'subject': '이메일 시스템 문제',
            'description': 'ABC회사 이메일 시스템에 문제가 있습니다.',
            'integrated_text': 'ABC회사의 홍길동입니다. 저희 회사 이메일 시스템에 문제가 있습니다. 도메인: abc-company.com MX 레코드 설정을 확인해주세요. Google Apps 연동이 안되고 있습니다.',
            'status': '진행중',
            'priority': '높음',
            'attachments': [
                {'name': 'error_log.txt', 'content_type': 'text/plain', 'size': 1024},
                {'name': 'screenshot.png', 'content_type': 'image/png', 'size': 204800},
                {'name': 'config.xml', 'content_type': 'application/xml', 'size': 512}
            ],
            'tenant_metadata': {
                'has_attachments': True, 
                'attachment_count': 3,
                'attachments': [
                    {'name': 'error_log.txt', 'content_type': 'text/plain', 'size': 1024},
                    {'name': 'screenshot.png', 'content_type': 'image/png', 'size': 204800},
                    {'name': 'config.xml', 'content_type': 'application/xml', 'size': 512}
                ]
            }
        }
        
        print("테스트 데이터:")
        print(f"  - 제목: {ticket_data['subject']}")
        print(f"  - 내용 길이: {len(ticket_data['integrated_text'])}자")
        print()
        
        print("요약 생성 시작...")
        result = await llm_manager.generate_ticket_summary(ticket_data)
        
        print(f"결과 타입: {type(result)}")
        print(f"결과 키들: {list(result.keys()) if isinstance(result, dict) else 'Not dict'}")
        
        if isinstance(result, dict) and 'summary' in result:
            summary = result['summary']
            print(f"요약 길이: {len(summary)}자")
            print("=" * 50)
            print("생성된 요약:")
            print(summary)
            print("=" * 50)
            
            # 요약이 유의미한지 확인
            error_messages = [
                "요약 생성에 실패했습니다.",
                "LLM 요약 생성 중 오류가 발생했습니다.",
                "요약 내용이 비어있습니다.",
                "분석할 내용이 없습니다."
            ]
            
            is_error = any(error_msg in summary for error_msg in error_messages)
            print(f"오류 메시지 여부: {is_error}")
            print(f"유효한 요약 여부: {not is_error and len(summary.strip()) > 20}")
            
        else:
            print(f"요약 없음: {result}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_summary())
