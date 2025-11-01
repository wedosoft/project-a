#!/usr/bin/env python3
"""
통합 테스트: Freshdesk → LLM 추출 파이프라인

실제 Freshdesk 티켓을 가져와서 LLM으로 symptom/cause/resolution 추출
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 경로 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.freshdesk import FreshdeskClient
from backend.services.extractor import IssueBlockExtractor, LLMProvider
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def test_integration():
    """
    통합 테스트 실행
    1. Freshdesk에서 최근 티켓 1개 조회
    2. 티켓 대화 내역 조회
    3. LLM으로 이슈 블록 추출 (OpenAI)
    4. Gemini로도 추출 (비교)
    """
    print("\n" + "=" * 60)
    print("🧪 통합 테스트: Freshdesk → LLM 추출 파이프라인")
    print("=" * 60)

    # 1. Freshdesk 클라이언트 초기화
    print("\n[1/5] Freshdesk 클라이언트 초기화...")
    freshdesk = FreshdeskClient()
    print(f"✅ Freshdesk URL: {freshdesk.base_url}")

    # 2. 특정 티켓 조회 (티켓 #11925)
    print("\n[2/5] 티켓 #11925 조회 중...")
    ticket_id = "11925"

    try:
        ticket = await freshdesk.get_ticket(ticket_id)
    except Exception as e:
        print(f"❌ 티켓 조회 실패: {e}")
        return
    print(f"✅ 티켓 조회 완료: #{ticket_id}")
    print(f"   제목: {ticket.get('subject', 'N/A')}")
    print(f"   상태: {ticket.get('status', 'N/A')}")
    print(f"   우선순위: {ticket.get('priority', 'N/A')}")

    # 3. 티켓 대화 내역 조회
    print(f"\n[3/5] 티켓 #{ticket_id} 대화 내역 조회 중...")
    try:
        conversations = await freshdesk.fetch_ticket_conversations(str(ticket_id))
        ticket["conversations"] = conversations
        print(f"✅ 대화 내역 조회 완료: {len(conversations)}개")
    except Exception as e:
        print(f"⚠️  대화 내역 조회 실패 (계속 진행): {e}")
        ticket["conversations"] = []

    # 4. OpenAI로 추출
    print("\n[4/5] OpenAI (gpt-4o-mini)로 이슈 블록 추출 중...")
    extractor_openai = IssueBlockExtractor(provider=LLMProvider.OPENAI)

    try:
        result_openai = await extractor_openai.extract_from_ticket(ticket)
        print("✅ OpenAI 추출 완료:")
        print(f"   📋 Symptom: {result_openai.get('symptom', 'N/A')}")
        print(f"   🔍 Cause: {result_openai.get('cause', 'N/A')}")
        print(f"   ✅ Resolution: {result_openai.get('resolution', 'N/A')}")
    except Exception as e:
        print(f"❌ OpenAI 추출 실패: {e}")
        result_openai = None

    # 5. Gemini로 추출 (비교)
    print("\n[5/5] Google Gemini (2.0 flash)로 이슈 블록 추출 중...")
    extractor_gemini = IssueBlockExtractor(provider=LLMProvider.GEMINI)

    try:
        result_gemini = await extractor_gemini.extract_from_ticket(ticket)
        print("✅ Gemini 추출 완료:")
        print(f"   📋 Symptom: {result_gemini.get('symptom', 'N/A')}")
        print(f"   🔍 Cause: {result_gemini.get('cause', 'N/A')}")
        print(f"   ✅ Resolution: {result_gemini.get('resolution', 'N/A')}")
    except Exception as e:
        print(f"❌ Gemini 추출 실패: {e}")
        result_gemini = None

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 통합 테스트 결과 요약")
    print("=" * 60)

    print(f"\n🎫 티켓 정보:")
    print(f"   ID: #{ticket_id}")
    print(f"   제목: {ticket.get('subject', 'N/A')}")
    print(f"   설명: {ticket.get('description_text', 'N/A')[:100]}...")
    print(f"   대화 수: {len(ticket.get('conversations', []))}")

    if result_openai:
        print(f"\n🤖 OpenAI 추출 결과:")
        print(f"   Symptom: {result_openai['symptom']}")
        print(f"   Cause: {result_openai['cause']}")
        print(f"   Resolution: {result_openai['resolution']}")

    if result_gemini:
        print(f"\n🔮 Gemini 추출 결과:")
        print(f"   Symptom: {result_gemini['symptom']}")
        print(f"   Cause: {result_gemini['cause']}")
        print(f"   Resolution: {result_gemini['resolution']}")

    # 성공 여부
    success = result_openai is not None or result_gemini is not None

    if success:
        print("\n✅ 통합 테스트 성공!")
        print("   Freshdesk → LLM 추출 파이프라인이 정상 작동합니다.")
    else:
        print("\n❌ 통합 테스트 실패!")
        print("   LLM 추출이 모두 실패했습니다.")

    print("=" * 60)
    return success


if __name__ == "__main__":
    try:
        result = asyncio.run(test_integration())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 통합 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
