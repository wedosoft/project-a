#!/usr/bin/env python3
"""
normalizer.py 기능 점검 테스트
"""

from core.metadata.normalizer import TenantMetadataNormalizer

def test_basic_normalization():
    """기본 정규화 테스트"""
    print('=== 기본 정규화 테스트 ===')
    raw_data = {'status': 'open', 'priority': 3, 'subject': 'Test Subject'}
    normalized = TenantMetadataNormalizer.normalize(raw_data)
    print(f'Status: {normalized["status"]} ({TenantMetadataNormalizer.get_status_text(normalized["status"])})')
    print(f'Priority: {normalized["priority"]}')
    print(f'Subject: {normalized["subject"]}')
    
    assert normalized["status"] == 2  # 'open' -> 2
    assert normalized["priority"] == 3
    assert normalized["subject"] == 'Test Subject'
    print("✅ 기본 정규화 테스트 통과")

def test_invalid_values():
    """비정상 값 정규화 테스트"""
    print('\n=== 비정상 값 정규화 테스트 ===')
    bad_data = {'status': 'invalid', 'priority': -1, 'conversation_count': 'not_a_number'}
    normalized = TenantMetadataNormalizer.normalize(bad_data)
    print(f'Invalid status -> {normalized["status"]} ({TenantMetadataNormalizer.get_status_text(normalized["status"])})')
    print(f'Negative priority -> {normalized["priority"]}')
    print(f'Invalid conversation_count -> {normalized["conversation_count"]}')
    
    assert normalized["status"] == 2  # 기본값 (Open)
    assert normalized["priority"] == 1  # 기본값
    assert normalized["conversation_count"] == 0  # 기본값
    print("✅ 비정상 값 정규화 테스트 통과")

def test_attachments():
    """첨부파일 메타데이터 테스트"""
    print('\n=== 첨부파일 메타데이터 테스트 ===')
    with_attachments = {
        'attachments': [
            {'content_type': 'image/png', 'size': 1024000},
            {'content_type': 'application/pdf', 'size': 8388608}  # 8MB
        ]
    }
    normalized = TenantMetadataNormalizer.normalize(with_attachments)
    print(f'Has attachments: {normalized["has_attachments"]}')
    print(f'Attachment count: {normalized["attachment_count"]}')
    print(f'Has image attachments: {normalized["has_image_attachments"]}')
    print(f'Has document attachments: {normalized["has_document_attachments"]}')
    print(f'Large attachments: {normalized["large_attachments"]}')
    print(f'Attachment types: {normalized["attachment_types"]}')
    
    assert normalized["has_attachments"] == True
    assert normalized["attachment_count"] == 2
    assert normalized["has_image_attachments"] == True
    assert normalized["has_document_attachments"] == True
    assert normalized["large_attachments"] == True  # 8MB > 5MB
    assert "image" in normalized["attachment_types"]
    assert "application" in normalized["attachment_types"]
    print("✅ 첨부파일 메타데이터 테스트 통과")

def test_complexity_estimation():
    """복잡도 추정 테스트"""
    print('\n=== 복잡도 추정 테스트 ===')
    
    # 낮은 복잡도
    simple_data = {
        'conversations': [],
        'all_attachments': [],
        'priority': 1,
        'description': 'Simple issue'
    }
    normalized = TenantMetadataNormalizer.extract_from_original_data(simple_data)
    print(f'Simple ticket complexity: {normalized["complexity_level"]}')
    assert normalized["complexity_level"] == "low"
    
    # 높은 복잡도
    complex_data = {
        'conversations': [f'conv_{i}' for i in range(15)],  # 많은 대화
        'all_attachments': [f'att_{i}' for i in range(7)],  # 많은 첨부파일
        'priority': 4,  # 높은 우선순위
        'description': 'A' * 1500  # 긴 설명
    }
    normalized = TenantMetadataNormalizer.extract_from_original_data(complex_data)
    print(f'Complex ticket complexity: {normalized["complexity_level"]}')
    assert normalized["complexity_level"] == "high"
    
    print("✅ 복잡도 추정 테스트 통과")

def test_ai_processing_info():
    """AI 처리 정보 업데이트 테스트"""
    print('\n=== AI 처리 정보 업데이트 테스트 ===')
    
    base_metadata = TenantMetadataNormalizer.normalize({})
    updated = TenantMetadataNormalizer.update_ai_processing_info(
        base_metadata, 
        model_used="gpt-4o", 
        quality_score=0.85
    )
    
    print(f'AI summary generated: {updated["ai_summary_generated"]}')
    print(f'AI model used: {updated["ai_model_used"]}')
    print(f'Quality score: {updated["summary_quality_score"]}')
    print(f'Timestamp: {updated["ai_summary_timestamp"]}')
    
    assert updated["ai_summary_generated"] == True
    assert updated["ai_model_used"] == "gpt-4o"
    assert updated["summary_quality_score"] == 0.85
    assert updated["ai_summary_timestamp"] is not None
    print("✅ AI 처리 정보 업데이트 테스트 통과")

def test_null_and_empty_handling():
    """None/빈값 처리 테스트"""
    print('\n=== None/빈값 처리 테스트 ===')
    
    # None 처리
    normalized = TenantMetadataNormalizer.normalize(None)
    print(f'None input - status: {normalized["status"]}')
    assert normalized["status"] == 2  # 기본값
    
    # 빈 dict 처리
    normalized = TenantMetadataNormalizer.normalize({})
    print(f'Empty dict - status: {normalized["status"]}')
    assert normalized["status"] == 2  # 기본값
    
    # JSON 문자열 처리
    normalized = TenantMetadataNormalizer.normalize('{"status": "closed"}')
    print(f'JSON string - status: {normalized["status"]} ({TenantMetadataNormalizer.get_status_text(normalized["status"])})')
    assert normalized["status"] == 5  # closed
    
    print("✅ None/빈값 처리 테스트 통과")

if __name__ == "__main__":
    try:
        test_basic_normalization()
        test_invalid_values()
        test_attachments()
        test_complexity_estimation()
        test_ai_processing_info()
        test_null_and_empty_handling()
        
        print("\n🎉 모든 normalizer 테스트 통과!")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
