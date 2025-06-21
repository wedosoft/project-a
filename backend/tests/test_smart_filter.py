"""
SmartConversationFilter 테스트 스크립트
실제 대화 데이터로 필터링 성능을 테스트합니다.
"""

import sys
import os
sys.path.append('.')

from core.llm.filters.conversation import SmartConversationFilter

def test_conversation_filtering():
    """대화 필터링 테스트"""
    
    # 테스트 대화 데이터 (실제 Freshdesk 형식과 유사)
    test_conversations = [
        {
            "id": 1,
            "body_text": "안녕하세요",
            "user_id": "user1",
            "created_at": "2025-06-21T10:00:00Z"
        },
        {
            "id": 2, 
            "body_text": "문제가 발생했습니다. 로그인이 안됩니다. 스크린샷을 첨부합니다.",
            "user_id": "user1",
            "created_at": "2025-06-21T10:01:00Z"
        },
        {
            "id": 3,
            "body_text": "확인했습니다.",
            "user_id": None,  # 상담원
            "created_at": "2025-06-21T10:02:00Z"
        },
        {
            "id": 4,
            "body_text": "해결 방법을 시도해보세요. 먼저 브라우저 캐시를 지우고 다시 로그인해보세요.",
            "user_id": None,
            "created_at": "2025-06-21T10:03:00Z"
        },
        {
            "id": 5,
            "body_text": "네",
            "user_id": "user1",
            "created_at": "2025-06-21T10:04:00Z"
        },
        {
            "id": 6,
            "body_text": "여전히 같은 오류가 발생합니다. 추가로 도움이 필요합니다.",
            "user_id": "user1", 
            "created_at": "2025-06-21T10:05:00Z"
        },
        {
            "id": 7,
            "body_text": "해결됐습니다. 감사합니다!",
            "user_id": "user1",
            "created_at": "2025-06-21T10:10:00Z"
        }
    ]
    
    # 필터 초기화
    conversation_filter = SmartConversationFilter()
    
    print("🧪 스마트 대화 필터링 테스트 시작")
    print(f"📊 원본 대화 수: {len(test_conversations)}")
    print("=" * 50)
    
    # 각 대화 분석
    print("📋 원본 대화 분석:")
    for i, conv in enumerate(test_conversations, 1):
        sender = "사용자" if conv.get("user_id") else "상담원"
        print(f"{i}. [{sender}] {conv['body_text'][:50]}...")
    
    print("\n" + "=" * 50)
    
    # 필터링 실행
    filtered_conversations = conversation_filter.filter_conversations_unlimited(test_conversations)
    
    print(f"🎯 필터링 결과: {len(test_conversations)} → {len(filtered_conversations)}")
    print("=" * 50)
    
    # 필터링된 대화 출력
    print("✅ 필터링된 대화:")
    for i, conv in enumerate(filtered_conversations, 1):
        sender = "사용자" if conv.get("user_id") else "상담원"
        print(f"{i}. [{sender}] {conv['body_text']}")
    
    print("\n" + "=" * 50)
    
    # 필터링 통계
    stats = conversation_filter.get_filtering_stats()
    print("📊 필터링 통계:")
    print(f"   - 토큰 예산: {stats['token_budget']}")
    print(f"   - 키워드 패턴 로드: {stats['keyword_patterns_loaded']}")
    print(f"   - 필터링 효율성: {len(filtered_conversations)/len(test_conversations)*100:.1f}%")
    
    # 개별 대화 중요도 점수 테스트
    print("\n📈 개별 대화 중요도 점수:")
    for conv in test_conversations:
        score = conversation_filter._calculate_importance_score(conv)
        sender = "사용자" if conv.get("user_id") else "상담원"
        print(f"   - [{sender}] {score:.2f}: {conv['body_text'][:30]}...")

if __name__ == "__main__":
    test_conversation_filtering()
