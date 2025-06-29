"""
실제 데이터 소스 분석 테스트
"""
import sys
import json
sys.path.append('.')

# normalizer만 임포트
from core.metadata.normalizer import TenantMetadataNormalizer

print("=== 실제 데이터 소스 분석 ===")

# 1. Freshdesk 티켓 데이터 샘플 (실제 구조)
freshdesk_ticket = {
    "id": 12345,
    "subject": None,  # 실제로 이런 경우가 있을 수 있음
    "description": "문제 설명",
    "status": 2,
    "priority": None,  # 이것도 None일 수 있음
    "requester_id": 678,
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z"
}

print("\n--- 1. Freshdesk 티켓 데이터 ---")
print(f"원본 subject: {freshdesk_ticket.get('subject')} (타입: {type(freshdesk_ticket.get('subject'))})")
print(f"원본 priority: {freshdesk_ticket.get('priority')} (타입: {type(freshdesk_ticket.get('priority'))})")

# extract_from_original_data 테스트
extracted = TenantMetadataNormalizer.extract_from_original_data(freshdesk_ticket)
print(f"추출된 subject: '{extracted['subject']}' (타입: {type(extracted['subject'])})")
print(f"추출된 priority: {extracted['priority']} (타입: {type(extracted['priority'])})")

# 2. 빈 데이터
print("\n--- 2. 빈 데이터 ---")
empty_data = {}
extracted_empty = TenantMetadataNormalizer.extract_from_original_data(empty_data)
print(f"빈 데이터의 subject: '{extracted_empty['subject']}' (타입: {type(extracted_empty['subject'])})")
print(f"빈 데이터의 priority: {extracted_empty['priority']} (타입: {type(extracted_empty['priority'])})")

# 3. 직접 normalize 호출
print("\n--- 3. 직접 normalize 호출 ---")
direct_normalized = TenantMetadataNormalizer.normalize({"subject": None, "priority": None})
print(f"직접 normalize된 subject: '{direct_normalized['subject']}' (타입: {type(direct_normalized['subject'])})")
print(f"직접 normalize된 priority: {direct_normalized['priority']} (타입: {type(direct_normalized['priority'])})")

print("\n=== 분석 완료 ===")
