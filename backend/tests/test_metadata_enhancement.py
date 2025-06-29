"""
확장된 Tenant Metadata 시스템 테스트 스크립트

비정상 값 처리, 정규화, 확장 필드 등을 테스트합니다.
"""

import sys
import json
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from core.metadata.normalizer import TenantMetadataNormalizer

def test_normalizer():
    """메타데이터 정규화 테스트"""
    
    print("🧪 Tenant Metadata 정규화 테스트 시작")
    print("=" * 60)
    
    # 테스트 케이스 1: 비정상 값 처리
    print("\n📋 테스트 1: 비정상 값 처리")
    abnormal_data = {
        "conversation_count": "invalid",  # 문자열 (숫자여야 함)
        "has_attachments": "yes",         # 문자열 (불린이어야 함) 
        "priority": 10,                   # 범위 벗어남 (1-5여야 함)
        "complexity_level": "extreme",    # 허용되지 않는 값
        "attachments": "not_a_list",      # 리스트가 아님
        "unknown_field": "should_ignore"  # 알려지지 않은 필드
    }
    
    normalized = TenantMetadataNormalizer.normalize(abnormal_data)
    
    print(f"입력: {abnormal_data}")
    print(f"정규화 결과:")
    print(f"  conversation_count: {normalized['conversation_count']} (타입: {type(normalized['conversation_count'])})")
    print(f"  has_attachments: {normalized['has_attachments']} (타입: {type(normalized['has_attachments'])})")
    print(f"  priority: {normalized['priority']}")
    print(f"  complexity_level: {normalized['complexity_level']}")
    print(f"  attachments: {normalized['attachments']}")
    print(f"  unknown_field 포함 여부: {'unknown_field' in normalized}")
    
    # 테스트 케이스 2: JSON 문자열 파싱
    print("\n📋 테스트 2: JSON 문자열 파싱")
    json_string = json.dumps({
        "subject": "테스트 티켓",
        "has_attachments": True,
        "attachment_count": 2
    })
    
    parsed_normalized = TenantMetadataNormalizer.normalize(json_string)
    print(f"JSON 입력: {json_string}")
    print(f"파싱 결과: subject={parsed_normalized['subject']}, has_attachments={parsed_normalized['has_attachments']}")
    
    # 테스트 케이스 3: 원본 데이터에서 메타데이터 추출
    print("\n📋 테스트 3: 원본 데이터에서 메타데이터 추출")
    original_ticket_data = {
        "subject": "로그인 문제 해결 요청",
        "status": "open",
        "priority": 3,
        "company": {"name": "ABC Corporation"},
        "requester": {"email": "user@abc.com"},
        "responder": {"name": "김지원"},
        "group": {"name": "IT지원팀"},
        "category": "기술지원",
        "product": {"name": "v2.1.0"},
        "conversations": [{"id": 1}, {"id": 2}, {"id": 3}],  # 3개 대화
        "all_attachments": [
            {"name": "error.log", "content_type": "text/plain", "size": 1024},
            {"name": "screenshot.png", "content_type": "image/png", "size": 6*1024*1024}  # 6MB
        ],
        "description": "시스템 로그인이 되지 않습니다. " * 50  # 긴 설명
    }
    
    extracted = TenantMetadataNormalizer.extract_from_original_data(original_ticket_data)
    
    print("추출된 메타데이터:")
    print(f"  고객사: {extracted['company_name']}")
    print(f"  고객 이메일: {extracted['customer_email']}")
    print(f"  담당자: {extracted['agent_name']}")
    print(f"  부서: {extracted['department']}")
    print(f"  카테고리: {extracted['ticket_category']}")
    print(f"  복잡도: {extracted['complexity_level']}")
    print(f"  대화 수: {extracted['conversation_count']}")
    print(f"  첨부파일 수: {extracted['attachment_count']}")
    print(f"  이미지 첨부파일: {extracted['has_image_attachments']}")
    print(f"  대용량 첨부파일: {extracted['large_attachments']}")
    print(f"  첨부파일 유형: {extracted['attachment_types']}")
    
    # 테스트 케이스 4: AI 처리 정보 업데이트
    print("\n📋 테스트 4: AI 처리 정보 업데이트")
    updated = TenantMetadataNormalizer.update_ai_processing_info(
        extracted, 
        model_used="gpt-4o-mini-2024-07-18",
        quality_score=4.2
    )
    
    print(f"AI 요약 생성됨: {updated['ai_summary_generated']}")
    print(f"사용된 모델: {updated['ai_model_used']}")
    print(f"품질 점수: {updated['summary_quality_score']}")
    print(f"처리 시각: {updated['ai_summary_timestamp']}")
    
    # 테스트 케이스 5: 메타데이터 버전 확인
    print("\n📋 테스트 5: 메타데이터 버전 및 정규화 정보")
    print(f"메타데이터 버전: {updated['metadata_version']}")
    print(f"마지막 정규화 시각: {updated['last_normalized_at']}")
    
    print("\n✅ 모든 테스트 완료!")
    print("=" * 60)
    
    return updated

def test_prompt_integration():
    """프롬프트 빌더와의 통합 테스트"""
    print("\n🔗 프롬프트 빌더 통합 테스트")
    
    # 샘플 메타데이터
    sample_metadata = {
        "company_name": "테크 솔루션",
        "customer_email": "admin@techsol.com", 
        "agent_name": "박기술",
        "department": "개발팀",
        "ticket_category": "버그 리포트",
        "complexity_level": "high",
        "product_version": "v3.2.1",
        "priority": 4,
        "status": "in_progress",
        "attachments": [
            {"name": "error_trace.log", "content_type": "text/plain"},
            {"name": "system_info.json", "content_type": "application/json"}
        ]
    }
    
    # 프롬프트 빌더 로직 시뮬레이션
    formatted_metadata = []
    
    if sample_metadata.get('company_name'):
        formatted_metadata.append(f"고객사: {sample_metadata['company_name']}")
    
    if sample_metadata.get('customer_email'):
        formatted_metadata.append(f"고객 연락처: {sample_metadata['customer_email']}")
    
    if sample_metadata.get('agent_name'):
        formatted_metadata.append(f"담당자: {sample_metadata['agent_name']}")
    
    if sample_metadata.get('department'):
        formatted_metadata.append(f"부서: {sample_metadata['department']}")
    
    if sample_metadata.get('ticket_category'):
        formatted_metadata.append(f"카테고리: {sample_metadata['ticket_category']}")
    
    if sample_metadata.get('complexity_level'):
        formatted_metadata.append(f"복잡도: {sample_metadata['complexity_level']}")
    
    if sample_metadata.get('product_version'):
        formatted_metadata.append(f"제품 버전: {sample_metadata['product_version']}")
    
    result = "; ".join(formatted_metadata)
    
    print("프롬프트에 포함될 메타데이터:")
    print(f"'{result}'")
    
    return result

if __name__ == "__main__":
    try:
        # 정규화 테스트
        final_metadata = test_normalizer()
        
        # 프롬프트 통합 테스트
        prompt_result = test_prompt_integration()
        
        print(f"\n🎯 최종 메타데이터 필드 수: {len(final_metadata)}")
        print(f"🎯 프롬프트 메타데이터 길이: {len(prompt_result)} 문자")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
