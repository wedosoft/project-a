"""
티켓 처리 예시 코드 (Python에서 직접 실행)

이 스크립트는 process_single_ticket.py의 기능을
대화형으로 사용할 수 있도록 한 예시입니다.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.freshdesk import FreshdeskClient
from backend.agents.orchestrator import compile_workflow
from backend.models.schemas import TicketContext
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def example_1_fetch_ticket():
    """
    예시 1: 특정 티켓 정보만 조회
    """
    print("\n" + "="*60)
    print("예시 1: 티켓 정보 조회")
    print("="*60)

    freshdesk = FreshdeskClient()

    # 티켓 ID 입력 (실제 티켓 ID로 변경 필요)
    ticket_id = "12345"

    try:
        # 티켓 조회
        ticket = await freshdesk.get_ticket(ticket_id)

        print(f"\n티켓 ID: {ticket.get('id')}")
        print(f"제목: {ticket.get('subject')}")
        print(f"설명: {ticket.get('description_text', '')[:100]}...")
        print(f"상태: {ticket.get('status')}")
        print(f"우선순위: {ticket.get('priority')}")

    except Exception as e:
        print(f"❌ 에러: {e}")


async def example_2_fetch_with_conversations():
    """
    예시 2: 티켓 + 대화 내역 조회
    """
    print("\n" + "="*60)
    print("예시 2: 티켓 + 대화 내역 조회")
    print("="*60)

    freshdesk = FreshdeskClient()
    ticket_id = "12345"

    try:
        # 티켓 조회
        ticket = await freshdesk.get_ticket(ticket_id)
        print(f"\n✅ 티켓 조회 완료: {ticket.get('subject')}")

        # 대화 내역 조회
        conversations = await freshdesk.fetch_ticket_conversations(ticket_id)
        print(f"✅ 대화 내역 조회 완료: {len(conversations)}개")

        # 대화 내역 출력
        for i, conv in enumerate(conversations[:3], 1):
            print(f"\n[대화 {i}]")
            print(f"작성자: {conv.get('user_id')}")
            print(f"내용: {conv.get('body_text', '')[:100]}...")
            print(f"시간: {conv.get('created_at')}")

        if len(conversations) > 3:
            print(f"\n... 외 {len(conversations) - 3}개 대화")

    except Exception as e:
        print(f"❌ 에러: {e}")


async def example_3_run_workflow_with_ticket():
    """
    예시 3: 티켓으로 워크플로우 실행 (검색 스킵)
    """
    print("\n" + "="*60)
    print("예시 3: 워크플로우 실행 (검색 스킵)")
    print("="*60)

    freshdesk = FreshdeskClient()
    ticket_id = "12345"

    try:
        # 1. 티켓 조회
        ticket = await freshdesk.get_ticket(ticket_id)
        conversations = await freshdesk.fetch_ticket_conversations(ticket_id)

        print(f"\n✅ 데이터 수집 완료")
        print(f"   티켓: {ticket.get('subject')}")
        print(f"   대화: {len(conversations)}개")

        # 2. 티켓 컨텍스트 생성 (대화 내역 포함)
        description = ticket.get('description_text', '')

        # 대화 내역을 description에 추가
        if conversations:
            conversation_text = "\n\n=== 대화 내역 ===\n"
            for i, conv in enumerate(conversations, 1):
                body = conv.get('body_text', '')
                conversation_text += f"\n[대화 {i}]\n{body}\n"

            enriched_description = f"{description}\n{conversation_text}"
        else:
            enriched_description = description

        ticket_context = TicketContext(
            ticket_id=str(ticket.get('id')),
            subject=ticket.get('subject', ''),
            description=enriched_description,
            priority=ticket.get('priority', 1),
            status=ticket.get('status', 2)
        )

        # 3. 워크플로우 실행 (검색 스킵)
        print(f"\n워크플로우 실행 중...")

        initial_state = {
            "ticket_context": ticket_context.model_dump(),
            "next_node": "propose_solution",  # 검색 스킵
            "search_results": {
                "similar_cases": [],
                "kb_procedures": [],
                "total_results": 0
            }
        }

        workflow = compile_workflow()
        result = await workflow.ainvoke(initial_state)

        # 4. 결과 출력
        print(f"\n{'='*60}")
        print("AI 분석 결과")
        print(f"{'='*60}")

        proposed_action = result.get("proposed_action", {})
        print(f"\n[AI 응답 초안]")
        print(proposed_action.get("draft_response", "N/A"))

        print(f"\n[신뢰도]")
        confidence = proposed_action.get("confidence", 0.0)
        print(f"{confidence:.2f} ({confidence*100:.0f}%)")

        print(f"\n[필드 업데이트 제안]")
        field_updates = proposed_action.get("proposed_field_updates", {})
        for key, value in field_updates.items():
            print(f"  {key}: {value}")

        print(f"\n{'='*60}")

    except Exception as e:
        print(f"❌ 에러: {e}")
        import traceback
        traceback.print_exc()


async def example_4_custom_context():
    """
    예시 4: 커스텀 컨텍스트로 워크플로우 실행
    (Freshdesk 조회 없이 직접 입력)
    """
    print("\n" + "="*60)
    print("예시 4: 커스텀 컨텍스트로 워크플로우 실행")
    print("="*60)

    # 직접 티켓 컨텍스트 생성
    ticket_context = TicketContext(
        ticket_id="CUSTOM-001",
        subject="로그인 오류 문의",
        description="""
사용자가 로그인을 시도할 때 401 에러가 발생합니다.

=== 대화 내역 ===

[대화 1]
고객: 로그인이 안되고 401 에러가 뜹니다.

[대화 2]
상담원: 비밀번호를 재설정하셨나요?

[대화 3]
고객: 네, 재설정했는데도 같은 에러가 나옵니다.
계정이 잠긴 것 같아요.

[대화 4]
상담원: 확인해보겠습니다.
        """,
        priority=3,  # high
        status=2     # open
    )

    print(f"\n티켓 정보:")
    print(f"  ID: {ticket_context.ticket_id}")
    print(f"  제목: {ticket_context.subject}")
    print(f"  우선순위: {ticket_context.priority}")

    # 워크플로우 실행
    print(f"\n워크플로우 실행 중...")

    initial_state = {
        "ticket_context": ticket_context.model_dump(),
        "next_node": "propose_solution",
        "search_results": {
            "similar_cases": [],
            "kb_procedures": [],
            "total_results": 0
        }
    }

    workflow = compile_workflow()
    result = await workflow.ainvoke(initial_state)

    # 결과 출력
    print(f"\n{'='*60}")
    print("AI 분석 결과")
    print(f"{'='*60}")

    proposed_action = result.get("proposed_action", {})
    print(f"\n{proposed_action.get('draft_response', 'N/A')}")

    print(f"\n신뢰도: {proposed_action.get('confidence', 0.0):.2f}")
    print(f"{'='*60}")


async def main():
    """메인 함수 - 원하는 예시 선택"""
    print("\n" + "="*60)
    print("티켓 처리 예시 스크립트")
    print("="*60)
    print("\n사용 가능한 예시:")
    print("1. 티켓 정보만 조회")
    print("2. 티켓 + 대화 내역 조회")
    print("3. 워크플로우 실행 (검색 스킵)")
    print("4. 커스텀 컨텍스트로 워크플로우 실행")
    print()

    choice = input("실행할 예시 번호 (1-4, 기본값 4): ").strip()

    if choice == "1":
        await example_1_fetch_ticket()
    elif choice == "2":
        await example_2_fetch_with_conversations()
    elif choice == "3":
        await example_3_run_workflow_with_ticket()
    else:  # 기본값 4
        await example_4_custom_context()


if __name__ == "__main__":
    asyncio.run(main())
