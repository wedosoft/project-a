#!/usr/bin/env python3
"""
개선된 첨부파일 선별 시스템 테스트
"""

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_improved_attachment_filter():
    """개선된 첨부파일 선별 시스템 테스트"""
    print("🧪 개선된 첨부파일 선별 시스템 테스트 시작...")
    
    try:
        from core.llm.summarizer.attachment.selector import AttachmentSelector
        
        selector = AttachmentSelector()
        
        # 테스트용 첨부파일 리스트
        test_attachments = [
            {"name": "ja-JP.yml", "content_type": "text/yaml", "size": 2048},
            {"name": "user_manual.pdf", "content_type": "application/pdf", "size": 1024000},
            {"name": "new_ticket_jp.PNG", "content_type": "image/png", "size": 512000},
            {"name": "error_log.log", "content_type": "text/plain", "size": 8192},
            {"name": "random_file.txt", "content_type": "text/plain", "size": 1024}
        ]
        
        print(f"📎 테스트 첨부파일: {len(test_attachments)}개")
        for att in test_attachments:
            print(f"  - {att['name']} ({att['content_type']})")
        print()
        
        # 테스트 1: 일본어 번역 관련 (관련성 높음)
        content1 = """
        일본어 번역 파일에 문제가 있습니다.
        ja-JP.yml 파일에서 일부 키값이 누락되어 있어서
        일본어 사용자들이 웹사이트를 이용할 때 텍스트가 제대로 표시되지 않습니다.
        new_ticket_jp.PNG 파일에서 확인할 수 있듯이 빈 텍스트가 나타납니다.
        에러 로그도 첨부했습니다.
        """
        
        result1 = selector.select_relevant_attachments(test_attachments, content1, "일본어 번역 파일 문제")
        print("테스트 1 - 일본어 번역 관련:")
        for att in result1:
            print(f"  📎 {att['name']} ({att['content_type']})")
        print()
        
        # 테스트 2: 시스템 오류 관련 (중간 관련성)
        content2 = """
        시스템에서 알 수 없는 오류가 발생하고 있습니다.
        사용자들이 로그인할 때마다 500 에러가 나타납니다.
        문제를 파악하기 위해 로그 파일을 확인해야 할 것 같습니다.
        """
        
        result2 = selector.select_relevant_attachments(test_attachments, content2, "시스템 오류 문제")
        print("테스트 2 - 시스템 오류 관련:")
        for att in result2:
            print(f"  📎 {att['name']} ({att['content_type']})")
        print()
        
        # 테스트 3: 비밀번호 재설정 (관련성 없음)
        content3 = """
        고객이 비밀번호 재설정을 요청했습니다.
        계정이 잠겨있어서 새로운 임시 비밀번호를 발급해주세요.
        이메일로 새 비밀번호를 전송해달라고 합니다.
        """
        
        result3 = selector.select_relevant_attachments(test_attachments, content3, "비밀번호 재설정")
        print("테스트 3 - 관련성 없는 티켓 (비밀번호 재설정):")
        if result3:
            for att in result3:
                print(f"  📎 {att['name']} ({att['content_type']})")
        else:
            print("  ✅ 관련성 없는 첨부파일이 올바르게 제외됨")
        print()
        
        # 테스트 4: 일반적인 문의 (관련성 매우 낮음)
        content4 = """
        제품 사용법에 대해 문의드립니다.
        기본적인 기능 사용 방법을 알고 싶습니다.
        매뉴얼이 있나요?
        """
        
        result4 = selector.select_relevant_attachments(test_attachments, content4, "제품 사용법 문의")
        print("테스트 4 - 일반 문의:")
        if result4:
            for att in result4:
                print(f"  📎 {att['name']} ({att['content_type']})")
        else:
            print("  ✅ 관련성 없는 첨부파일이 올바르게 제외됨")
        
        print("✅ 개선된 첨부파일 선별 시스템 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_improved_attachment_filter()
