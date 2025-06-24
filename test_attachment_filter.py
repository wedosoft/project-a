#!/usr/bin/env python3
"""
첨부파일 필터링 로직 테스트
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.llm.optimized_summarizer import _select_relevant_attachments

def test_attachment_filtering():
    """첨부파일 필터링 테스트"""
    
    # 테스트 데이터
    test_attachments = [
        {
            'id': '1',
            'name': 'ja-JP.yml',
            'content_type': 'text/yaml',
            'size': 2048
        },
        {
            'id': '2', 
            'name': 'new_ticket_jp.PNG',
            'content_type': 'image/png',
            'size': 512000
        },
        {
            'id': '3',
            'name': 'random_file.txt',
            'content_type': 'text/plain',
            'size': 1024
        },
        {
            'id': '4',
            'name': 'error_log.log',
            'content_type': 'text/plain',
            'size': 8192
        },
        {
            'id': '5',
            'name': 'support.skcc.com.har',
            'content_type': 'application/json',
            'size': 1024000
        }
    ]
    
    # 테스트 케이스 1: 일본어 번역 관련 티켓
    content1 = """
    일본어 지원을 위해 티켓 필드 번역 파일(yml) 업로드 후, 
    기본 파일이 계속 다운로드되는 현상 발생.
    ja-JP.yml 파일을 업로드했지만 번역이 적용되지 않음.
    new_ticket_jp.PNG 스크린샷 참조.
    """
    
    result1 = _select_relevant_attachments(test_attachments, content1, "일본어 번역 파일 문제")
    print("테스트 1 - 일본어 번역 관련:")
    for att in result1:
        print(f"  📎 {att['name']} ({att['content_type']})")
    print()
    
    # 테스트 케이스 2: 로그 파일 관련 티켓
    content2 = """
    시스템에 오류가 발생했습니다.
    error_log.log 파일을 확인해보니 데이터베이스 연결 문제가 있습니다.
    """
    
    result2 = _select_relevant_attachments(test_attachments, content2, "시스템 오류 문제")
    print("테스트 2 - 시스템 오류 관련:")
    for att in result2:
        print(f"  📎 {att['name']} ({att['content_type']})")
    print()
    
    # 테스트 케이스 3: 관련성 없는 티켓
    content3 = """
    계정 비밀번호를 잊어버렸습니다.
    비밀번호 재설정 방법을 알려주세요.
    """
    
    result3 = _select_relevant_attachments(test_attachments, content3, "비밀번호 재설정")
    print("테스트 3 - 관련성 없는 티켓:")
    for att in result3:
        print(f"  📎 {att['name']} ({att['content_type']})")
    print()

if __name__ == "__main__":
    test_attachment_filtering()
