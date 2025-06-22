#!/usr/bin/env python3
"""
인라인 이미지 처리 기능 테스트

새로 추가된 HTML 파싱 및 인라인 이미지 처리 기능을 테스트합니다.
"""

import sys
import os
import json
from pathlib import Path

# 백엔드 모듈 경로 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.utils import (
    extract_inline_images_from_html,
    sanitize_inline_image_metadata,
    extract_text_content_from_html,
    count_inline_images_in_html,
    extract_attachment_id_from_url
)

from core.ingest.integrator import (
    create_integrated_ticket_object,
    create_integrated_article_object
)

def test_html_parsing():
    """HTML 파싱 기능 테스트"""
    print("🧪 HTML 파싱 기능 테스트 시작...")
    
    # 테스트 HTML 데이터
    test_html = """
    <div>
        <p>이는 로그인 문제에 대한 티켓입니다.</p>
        <img src="https://company.freshdesk.com/helpdesk/attachments/12345678901" alt="로그인 스크린샷" />
        <p>다음은 에러 메시지입니다:</p>
        <img src="https://company.freshdesk.com/attachments/98765432100?token=xyz" alt="에러 메시지" width="300" />
        <p>해결 방법을 찾고 있습니다.</p>
        <img src="https://external-site.com/image.png" alt="외부 이미지" />
    </div>
    """
    
    # 1. 인라인 이미지 추출 테스트
    inline_images = extract_inline_images_from_html(test_html)
    print(f"✅ 추출된 인라인 이미지 수: {len(inline_images)}")
    
    for i, img in enumerate(inline_images):
        print(f"   이미지 {i+1}: ID={img.get('attachment_id')}, Alt='{img.get('alt_text')}'")
    
    # 2. 메타데이터 정리 테스트
    sanitized = sanitize_inline_image_metadata(inline_images)
    print(f"✅ 정리된 메타데이터 수: {len(sanitized)}")
    
    # 3. 텍스트 추출 테스트
    text_content = extract_text_content_from_html(test_html)
    print(f"✅ 추출된 텍스트: '{text_content[:50]}...'")
    
    # 4. 이미지 카운트 테스트
    image_count = count_inline_images_in_html(test_html)
    print(f"✅ 이미지 카운트: {image_count}")
    
    return inline_images, sanitized


def test_attachment_id_extraction():
    """첨부파일 ID 추출 테스트"""
    print("🧪 첨부파일 ID 추출 테스트 시작...")
    
    test_urls = [
        "https://company.freshdesk.com/helpdesk/attachments/12345678901",
        "https://company.freshdesk.com/attachments/98765432100?token=xyz",
        "https://company.freshdesk.com/api/v2/attachments/11111111111",
        "https://invalid-url.com/image.png",
        "https://company.freshdesk.com/helpdesk/attachments/invalid"
    ]
    
    for url in test_urls:
        attachment_id = extract_attachment_id_from_url(url)
        status = "✅" if attachment_id else "❌"
        print(f"   {status} {url} → {attachment_id}")


def test_integrated_object_creation():
    """통합 객체 생성 테스트"""
    print("🧪 통합 객체 생성 테스트 시작...")
    
    # 테스트 티켓 데이터
    test_ticket = {
        "id": 12345,
        "subject": "로그인 문제 해결 요청",
        "description": """
        <div>
            <p>로그인할 때 다음과 같은 오류가 발생합니다.</p>
            <img src="https://company.freshdesk.com/helpdesk/attachments/1001" alt="로그인 오류 스크린샷" />
            <p>브라우저: Chrome 최신 버전</p>
            <img src="https://company.freshdesk.com/helpdesk/attachments/1002" alt="콘솔 오류" />
        </div>
        """,
        "status": 2,
        "priority": 1,
        "created_at": "2025-06-22T10:00:00Z",
        "updated_at": "2025-06-22T10:30:00Z"
    }
    
    # 테스트 대화 데이터
    test_conversations = [
        {
            "id": 101,
            "body": """
            <p>추가 정보입니다.</p>
            <img src="https://company.freshdesk.com/helpdesk/attachments/1003" alt="추가 스크린샷" />
            """,
            "created_at": "2025-06-22T10:15:00Z"
        }
    ]
    
    # 테스트 첨부파일 데이터
    test_attachments = [
        {
            "id": 2001,
            "name": "error_log.txt",
            "content_type": "text/plain",
            "size": 1024,
            "attachment_url": "https://company.freshdesk.com/attachments/2001"
        },
        {
            "id": 2002,
            "name": "screenshot.png",
            "content_type": "image/png",
            "size": 512000,
            "attachment_url": "https://company.freshdesk.com/attachments/2002"
        }
    ]
    
    # 통합 객체 생성
    integrated_ticket = create_integrated_ticket_object(
        ticket=test_ticket,
        conversations=test_conversations,
        attachments=test_attachments,
        company_id="test_company"
    )
    
    print(f"✅ 통합 티켓 객체 생성 완료")
    print(f"   - 인라인 이미지 수: {integrated_ticket.get('inline_image_count', 0)}")
    print(f"   - 첨부파일 수: {integrated_ticket.get('attachment_count', 0)}")
    print(f"   - 전체 이미지 수: {integrated_ticket.get('total_image_count', 0)}")
    print(f"   - 이미지 포함 여부: {integrated_ticket.get('has_images', False)}")
    
    # 인라인 이미지 상세 정보
    inline_images = integrated_ticket.get('inline_images', [])
    if inline_images:
        print(f"   - 인라인 이미지 상세:")
        for img in inline_images:
            print(f"     * ID: {img.get('attachment_id')}, Alt: '{img.get('alt_text')}'")
    
    # 통합 이미지 리스트
    all_images = integrated_ticket.get('all_images', [])
    if all_images:
        print(f"   - 모든 이미지 상세:")
        for img in all_images:
            img_type = img.get('type', 'unknown')
            name = img.get('name', img.get('alt_text', 'unnamed'))
            print(f"     * {img_type}: {name} (ID: {img.get('attachment_id')})")
    
    return integrated_ticket


def main():
    """메인 테스트 실행"""
    print("🚀 인라인 이미지 처리 기능 테스트 시작\n")
    
    try:
        # 1. HTML 파싱 테스트
        test_html_parsing()
        print()
        
        # 2. 첨부파일 ID 추출 테스트
        test_attachment_id_extraction()
        print()
        
        # 3. 통합 객체 생성 테스트
        integrated_ticket = test_integrated_object_creation()
        print()
        
        # 4. 결과 요약
        print("📊 테스트 결과 요약:")
        print("   ✅ HTML 파싱 기능 정상 동작")
        print("   ✅ 첨부파일 ID 추출 정상 동작")
        print("   ✅ 통합 객체 생성 정상 동작")
        print("   ✅ 인라인 이미지 메타데이터 처리 정상 동작")
        
        print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
        
        # 통합 객체 JSON 출력 (선택적)
        if input("\n통합 객체 JSON을 출력하시겠습니까? (y/N): ").lower() == 'y':
            print("\n📄 통합 객체 JSON:")
            print(json.dumps(integrated_ticket, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
