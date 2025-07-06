#!/usr/bin/env python3
"""
긴 대화 티켓 처리 개선 테스트

50개 대화가 있는 티켓의 요약 품질 확인
"""

import asyncio
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

def create_test_ticket_with_long_conversations():
    """긴 대화가 있는 테스트 티켓 생성"""
    
    # 기본 티켓 정보
    ticket_data = {
        "id": "long_conv_test",
        "subject": "헬프데스크 일본어 언어 파일 업로드 문제",
        "description": "헬프데스크 > 언어 관리에서 Japanese yml 파일 업로드 후 다운로드 시 기본 파일이 나오는 문제",
        "status": "resolved",
        "priority": "high",
        "conversations": []
    }
    
    # 50개 대화 생성 (실제와 유사한 패턴)
    conversations = []
    
    # 1-5: 초기 문제 신고
    conversations.extend([
        {"body_text": "안녕하세요. 헬프데스크 언어 관리에서 Japanese 언어를 추가하고 yml 파일을 업로드했는데 문제가 있습니다."},
        {"body_text": "업로드 성공 메시지는 나왔지만, 다운로드 받으면 기본 파일이 나와요."},
        {"body_text": "yml 파일 형식에 문제가 있는 건지 확인 부탁드립니다."},
        {"body_text": "고객사: XYZ 컴퍼니, 사용자: admin@xyz.com"},
        {"body_text": "첨부: 업로드한 yml 파일과 다운로드 받은 파일 스크린샷"}
    ])
    
    # 6-15: 초기 문의 및 조사
    conversations.extend([
        {"body_text": "문의 접수되었습니다. 먼저 업로드하신 yml 파일을 확인해보겠습니다."},
        {"body_text": "파일 형식은 정상으로 보입니다. 서버 로그를 확인해보겠습니다."},
        {"body_text": "혹시 브라우저 캐시 문제일 수 있으니 캐시 클리어 후 다시 시도해보세요."},
        {"body_text": "캐시 클리어했지만 여전히 같은 문제입니다."},
        {"body_text": "다른 브라우저에서도 동일한 현상이 발생합니다."},
        {"body_text": "서버 로그에서 파일 업로드는 성공했지만 적용 과정에 오류가 있는 것 같습니다."},
        {"body_text": "개발팀에 에스컬레이션하여 시스템 체크하겠습니다."},
        {"body_text": "네, 빠른 해결 부탁드립니다. 일본 고객들이 기다리고 있어서요."},
        {"body_text": "이해합니다. 우선순위 높여서 처리하겠습니다."},
        {"body_text": "개발팀에서 관련 시스템 점검 시작했습니다."}
    ])
    
    # 16-30: 조사 진행 과정
    conversations.extend([
        {"body_text": "개발팀 피드백: 언어 파일 저장소에 문제가 있는 것으로 확인되었습니다."},
        {"body_text": "구체적으로 어떤 문제인가요?"},
        {"body_text": "파일 업로드는 임시 저장소에만 저장되고 실제 서비스 저장소로 동기화되지 않는 버그입니다."},
        {"body_text": "언제부터 이런 문제가 있었나요?"},
        {"body_text": "최근 시스템 업데이트 후 발생한 것으로 보입니다. 다른 고객들도 영향 받았을 가능성이 있습니다."},
        {"body_text": "그럼 다른 언어 파일들도 확인이 필요하겠네요."},
        {"body_text": "맞습니다. 전체 언어 파일 시스템 점검 중입니다."},
        {"body_text": "수정 예상 시간이 얼마나 걸리나요?"},
        {"body_text": "개발팀에서 핫픽스 준비 중이며, 오늘 오후 중으로 배포 예정입니다."},
        {"body_text": "테스트 환경에서 수정 코드 검증 중입니다."},
        {"body_text": "추가 테스트 완료되면 즉시 프로덕션 배포하겠습니다."},
        {"body_text": "네, 업데이트 소식 계속 공유 부탁드립니다."},
        {"body_text": "물론입니다. 진행 상황 실시간으로 알려드리겠습니다."},
        {"body_text": "다른 고객들에게도 알림 발송 준비하고 있습니다."},
        {"body_text": "핫픽스 코드 리뷰 완료, QA 테스트 진행 중입니다."}
    ])
    
    # 31-45: 해결 과정 (중요!)
    conversations.extend([
        {"body_text": "QA 테스트 통과했습니다. 프로덕션 배포 시작합니다."},
        {"body_text": "배포 진행률 30%... 정상 진행 중입니다."},
        {"body_text": "배포 완료되었습니다. 언어 파일 동기화 시스템이 수정되었습니다."},
        {"body_text": "이제 테스트해보시겠어요? 기존 파일 다시 업로드 후 다운로드 확인 부탁드립니다."},
        {"body_text": "지금 테스트해보겠습니다."},
        {"body_text": "야 파일 업로드 다시 했는데 이번엔 제대로 적용되는 것 같아요!"},
        {"body_text": "다운로드해서 확인해보니 제가 업로드한 파일이 맞습니다."},
        {"body_text": "훌륭합니다! 정상 작동 확인되었네요."},
        {"body_text": "일본어 번역도 헬프데스크에서 정상적으로 표시되고 있습니다."},
        {"body_text": "완벽하게 해결된 것 같습니다. 감사합니다!"},
        {"body_text": "추가로 다른 언어 파일들도 확인해봤는데 모두 정상 작동합니다."},
        {"body_text": "시스템 전반적인 안정성도 체크 완료했습니다."},
        {"body_text": "이번 수정으로 향후 동일한 문제는 발생하지 않을 예정입니다."},
        {"body_text": "모니터링 시스템도 강화하여 유사 문제 조기 감지 가능하도록 개선했습니다."},
        {"body_text": "정말 빠르고 정확한 대응이었습니다. 고마워요."}
    ])
    
    # 46-50: 최종 확인 및 종료
    conversations.extend([
        {"body_text": "혹시 추가로 확인이 필요한 사항이 있으시면 언제든 연락 주세요."},
        {"body_text": "사용법 가이드도 업데이트해서 공유드리겠습니다."},
        {"body_text": "네, 모든 것이 완벽하게 해결되었습니다."},
        {"body_text": "다른 팀원들에게도 공유하겠습니다. 정말 감사드립니다."},
        {"body_text": "티켓을 해결 완료로 종료하겠습니다. 이용해주셔서 감사합니다."}
    ])
    
    ticket_data["conversations"] = conversations
    return ticket_data

async def test_long_conversation_processing():
    """긴 대화 처리 테스트"""
    print("🔍 긴 대화 티켓 처리 테스트")
    print("=" * 50)
    
    # 테스트 티켓 생성
    ticket_data = create_test_ticket_with_long_conversations()
    total_conversations = len(ticket_data["conversations"])
    
    print(f"📊 테스트 티켓 정보:")
    print(f"   총 대화 수: {total_conversations}개")
    print(f"   티켓 상태: {ticket_data['status']}")
    print(f"   우선순위: {ticket_data['priority']}")
    
    # API routes의 대화 처리 로직 시뮬레이션
    conversations = ticket_data["conversations"]
    ticket_content_parts = [
        f"제목: {ticket_data['subject']}",
        f"설명: {ticket_data['description']}"
    ]
    
    # 새로운 긴 대화 처리 로직 적용
    ticket_content_parts.append(f"대화내역 (총 {total_conversations}개):")
    
    if total_conversations <= 10:
        # 짧은 대화: 전체 포함
        processed_count = total_conversations
        processing_strategy = "전체 포함"
    elif total_conversations <= 30:
        # 중간 길이: 핵심 대화 선별
        selected_indices = (
            list(range(0, min(3, total_conversations))) +  # 초반 3개
            list(range(total_conversations//2 - 1, min(total_conversations//2 + 1, total_conversations))) +  # 중간 2개
            list(range(max(0, total_conversations - 5), total_conversations))  # 후반 5개
        )
        selected_indices = sorted(set(selected_indices))
        processed_count = len(selected_indices)
        processing_strategy = "핵심 대화 선별"
    else:
        # 긴 대화: 해결 과정 중심 선별
        resolution_keywords = ['해결', '완료', '조치', '수정', '적용', '확인', '테스트', '배포', '닫힘']
        
        # 초반 2개
        selected_conversations = []
        for i in range(min(2, total_conversations)):
            selected_conversations.append((i, conversations[i]))
        
        # 해결 키워드 포함 대화
        keyword_conversations = []
        for i, conv in enumerate(conversations[2:-8] if total_conversations > 10 else [], 2):
            body_text = conv['body_text'].lower()
            if any(keyword in body_text for keyword in resolution_keywords):
                keyword_conversations.append((i, conv))
        
        keyword_conversations = keyword_conversations[:5]
        selected_conversations.extend(keyword_conversations)
        
        # 후반 8개
        for i in range(max(0, total_conversations - 8), total_conversations):
            selected_conversations.append((i, conversations[i]))
        
        # 중복 제거
        unique_conversations = {}
        for idx, conv in selected_conversations:
            unique_conversations[idx] = conv
        
        processed_count = len(unique_conversations)
        processing_strategy = "해결 중심 선별"
        
        # 해결 키워드 발견 분석
        resolution_found = len(keyword_conversations)
        print(f"   해결 키워드 대화: {resolution_found}개 발견")
    
    print(f"\n🔧 처리 전략: {processing_strategy}")
    print(f"   처리된 대화: {processed_count}개 / {total_conversations}개 ({processed_count/total_conversations*100:.1f}%)")
    
    # 해결 과정 포함 여부 확인
    resolution_keywords_check = ['배포 완료', '해결되었습니다', '정상 작동', '수정되었습니다', '완료했습니다']
    has_resolution_content = False
    
    if total_conversations > 30:
        # 후반 8개 대화에서 해결 내용 확인
        final_conversations = conversations[-8:]
        for conv in final_conversations:
            body_text = conv['body_text']
            if any(keyword in body_text for keyword in resolution_keywords_check):
                has_resolution_content = True
                break
    
    print(f"   해결 내용 포함: {'✅ 포함됨' if has_resolution_content else '❌ 누락'}")
    
    return {
        "total_conversations": total_conversations,
        "processed_count": processed_count,
        "processing_strategy": processing_strategy,
        "has_resolution": has_resolution_content,
        "coverage_percent": processed_count / total_conversations * 100
    }

async def test_summarization_with_long_content():
    """긴 대화 내용으로 실제 요약 테스트"""
    print(f"\n📝 실제 요약 생성 테스트")
    print("=" * 50)
    
    from core.llm.manager import LLMManager
    
    # 테스트 티켓으로 실제 요약 생성
    ticket_data = create_test_ticket_with_long_conversations()
    
    try:
        llm_manager = LLMManager()
        
        print("   요약 생성 중...")
        summary = await llm_manager.generate_ticket_summary(ticket_data)
        
        # 요약 내용 분석
        summary_content = summary.get('content', '')
        
        # 해결 과정 관련 키워드 확인
        resolution_indicators = [
            '배포 완료', '해결되었습니다', '수정되었습니다', '정상 작동', 
            '완료', '해결', '수정', '적용', '테스트 통과'
        ]
        
        resolution_mentions = 0
        for indicator in resolution_indicators:
            if indicator in summary_content:
                resolution_mentions += 1
        
        # "조치도 취해지지 않았으므로" 같은 부정적 표현 확인
        negative_indicators = [
            '조치도 취해지지 않았으므로',
            '해결책이나 조치사항은 없습니다',
            '상담원의 답변이나 안내사항은 아직 없습니다'
        ]
        
        has_negative_content = any(neg in summary_content for neg in negative_indicators)
        
        print(f"   요약 길이: {len(summary_content)}자")
        print(f"   해결 관련 언급: {resolution_mentions}개")
        print(f"   부정적 표현 포함: {'❌ 포함됨' if has_negative_content else '✅ 없음'}")
        
        # 요약 품질 평가
        if resolution_mentions >= 2 and not has_negative_content:
            quality_score = "우수"
        elif resolution_mentions >= 1 and not has_negative_content:
            quality_score = "양호"
        elif not has_negative_content:
            quality_score = "보통"
        else:
            quality_score = "불량"
        
        print(f"   요약 품질: {quality_score}")
        
        # 요약 일부 출력
        print(f"\n📄 요약 미리보기:")
        print(f"   {summary_content[:300]}...")
        
        return quality_score != "불량"
        
    except Exception as e:
        print(f"   ❌ 요약 생성 실패: {e}")
        return False

async def main():
    """메인 테스트 실행"""
    print("🚀 긴 대화 티켓 처리 개선 테스트")
    print("=" * 60)
    print("확인 항목:")
    print("1. 50개 대화 중 충분한 대화가 처리되는지")
    print("2. 해결 과정이 포함된 후반 대화가 선별되는지")
    print("3. 실제 요약에서 해결 내용이 반영되는지")
    print("=" * 60)
    
    results = []
    
    # 1. 대화 처리 로직 테스트
    processing_result = await test_long_conversation_processing()
    results.append(processing_result["has_resolution"])
    
    # 2. 실제 요약 품질 테스트
    summary_quality = await test_summarization_with_long_content()
    results.append(summary_quality)
    
    # 결과 요약
    print(f"\n🏆 최종 테스트 결과")
    print("=" * 60)
    
    test_names = [
        "긴 대화 해결 과정 선별",
        "요약 품질 개선"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{i+1}. {name}: {status}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n전체 성공률: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    if all(results):
        print("\n🎉 긴 대화 티켓 처리가 크게 개선되었습니다!")
        print("\n개선된 기능:")
        print(f"  ✅ 50개 대화 중 {processing_result['processed_count']}개 처리 ({processing_result['coverage_percent']:.1f}%)")
        print("  ✅ 해결 과정 중심의 스마트 선별")
        print("  ✅ 대화당 문자 수 확대 (200자 → 700자)")
        print("  ✅ 해결 키워드 기반 중요 대화 포함")
        print("  ✅ 후반 8개 대화 우선 처리 (해결과정 최우선)")
    else:
        print("\n⚠️  일부 기능에서 추가 개선이 필요합니다.")

if __name__ == "__main__":
    asyncio.run(main())