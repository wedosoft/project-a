"""
특정 Freshdesk 티켓을 조회하여 에이전트 플로우 실행

벡터 DB 없이도 동작:
1. Freshdesk에서 티켓 + 대화 내역 조회
2. 대화 내역을 컨텍스트로 포함
3. LangGraph 워크플로우 실행
4. AI 분석 결과 출력

사용법:
    python backend/scripts/process_single_ticket.py <ticket_id> [tenant_id]
    python backend/scripts/process_single_ticket.py 12345 default-tenant
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load .env file explicitly
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.freshdesk import FreshdeskClient
from backend.agents.orchestrator import compile_workflow
from backend.models.schemas import TicketContext, TicketStatus, Priority
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Mapping Functions for Freshdesk API
# ============================================================================

def map_freshdesk_status(status_code: int) -> TicketStatus:
    """
    Map Freshdesk status integer to TicketStatus enum.

    Freshdesk status codes:
    2 = Open
    3 = Pending
    4 = Resolved
    5 = Closed
    6 = Waiting on Customer
    7 = Waiting on Third Party

    Args:
        status_code: Freshdesk status integer

    Returns:
        TicketStatus enum value
    """
    status_map = {
        2: TicketStatus.OPEN,
        3: TicketStatus.PENDING,
        4: TicketStatus.RESOLVED,
        5: TicketStatus.CLOSED,
        6: TicketStatus.PENDING,  # Map "Waiting on Customer" to PENDING
        7: TicketStatus.PENDING   # Map "Waiting on Third Party" to PENDING
    }

    return status_map.get(status_code, TicketStatus.OPEN)


def map_freshdesk_priority(priority_code: int) -> Priority:
    """
    Map Freshdesk priority integer to Priority enum.

    Freshdesk priority codes:
    1 = Low
    2 = Medium
    3 = High
    4 = Urgent

    Args:
        priority_code: Freshdesk priority integer

    Returns:
        Priority enum value
    """
    priority_map = {
        1: Priority.LOW,
        2: Priority.MEDIUM,
        3: Priority.HIGH,
        4: Priority.URGENT
    }

    return priority_map.get(priority_code, Priority.MEDIUM)


async def fetch_ticket_with_conversations(
    freshdesk: FreshdeskClient,
    ticket_id: str
) -> Dict[str, Any]:
    """
    Freshdesk에서 티켓과 대화 내역 조회

    Args:
        freshdesk: FreshdeskClient 인스턴스
        ticket_id: 티켓 ID

    Returns:
        티켓 정보 + 대화 내역
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"티켓 조회: {ticket_id}")
    logger.info(f"{'='*60}")

    # 1. 티켓 상세 조회
    ticket = await freshdesk.get_ticket(ticket_id)

    logger.info(f"\n[티켓 정보]")
    logger.info(f"  ID: {ticket.get('id')}")
    logger.info(f"  제목: {ticket.get('subject')}")
    logger.info(f"  상태: {ticket.get('status')}")
    logger.info(f"  우선순위: {ticket.get('priority')}")
    logger.info(f"  생성일: {ticket.get('created_at')}")
    logger.info(f"  태그: {ticket.get('tags', [])}")

    # 2. 대화 내역 조회
    conversations = await freshdesk.fetch_ticket_conversations(ticket_id)

    logger.info(f"\n[대화 내역]")
    logger.info(f"  총 대화 수: {len(conversations)}")

    # 대화 내역 포맷팅
    conversation_text = []
    for i, conv in enumerate(conversations, 1):
        user_id = conv.get('user_id', 'Unknown')
        body = conv.get('body_text', conv.get('body', 'No content'))
        created = conv.get('created_at', 'Unknown time')

        conversation_text.append(
            f"[대화 {i}] ({created})\n"
            f"작성자 ID: {user_id}\n"
            f"내용: {body}\n"
        )

    # 최근 5개 대화만 출력
    for conv_text in conversation_text[:5]:
        logger.info(f"\n{conv_text}")

    if len(conversations) > 5:
        logger.info(f"\n... 외 {len(conversations) - 5}개 대화")

    return {
        "ticket": ticket,
        "conversations": conversations,
        "conversation_summary": "\n".join(conversation_text)
    }


async def build_enriched_context(
    ticket: Dict[str, Any],
    conversations: List[Dict[str, Any]],
    tenant_id: str = "default-tenant"
) -> TicketContext:
    """
    티켓 + 대화 내역으로 enriched context 생성

    Args:
        ticket: 티켓 정보
        conversations: 대화 내역 리스트
        tenant_id: 테넌트 ID (기본값: "default-tenant")

    Returns:
        TicketContext with conversations embedded and proper validation
    """
    # 티켓 본문 추출
    description = ticket.get('description_text', ticket.get('description', ''))

    # 대화 내역을 description에 추가
    if conversations:
        conversation_summary = "\n\n=== 대화 내역 ===\n"
        for i, conv in enumerate(conversations, 1):
            body = conv.get('body_text', conv.get('body', ''))
            conversation_summary += f"\n[대화 {i}]\n{body}\n"

        # description에 대화 내역 추가 (길이 제한 없음)
        enriched_description = f"{description}\n{conversation_summary}"
    else:
        enriched_description = description

    logger.info(f"Total description length: {len(enriched_description):,} characters")

    # Freshdesk integer values를 enum으로 변환
    status_code = ticket.get('status', 2)
    priority_code = ticket.get('priority', 1)

    status_enum = map_freshdesk_status(status_code)
    priority_enum = map_freshdesk_priority(priority_code)

    logger.info(f"Mapped status {status_code} → {status_enum.value}")
    logger.info(f"Mapped priority {priority_code} → {priority_enum.value}")

    # TicketContext 생성
    ticket_context = TicketContext(
        ticket_id=str(ticket.get('id')),
        tenant_id=tenant_id,
        subject=ticket.get('subject', ''),
        description=enriched_description,
        status=status_enum,
        priority=priority_enum,
        tags=ticket.get('tags', [])
    )

    return ticket_context


async def run_workflow_direct(
    ticket_context: TicketContext,
    skip_search: bool = True
) -> Dict[str, Any]:
    """
    워크플로우를 직접 실행 (검색 단계 스킵 옵션)

    Args:
        ticket_context: 티켓 컨텍스트
        skip_search: True면 검색 스킵하고 바로 propose_solution으로

    Returns:
        워크플로우 실행 결과
    """
    logger.info(f"\n{'='*60}")
    logger.info("워크플로우 실행")
    logger.info(f"{'='*60}")
    logger.info(f"검색 단계 스킵: {skip_search}")

    # 초기 상태 생성
    initial_state = {
        "ticket_context": ticket_context.model_dump(),
        "errors": [],
        "metadata": {
            "skip_search": skip_search
        }
    }

    # 검색 스킵하려면 next_node를 propose_solution으로 설정
    if skip_search:
        initial_state["next_node"] = "propose_solution"
        initial_state["search_results"] = {
            "similar_cases": [],
            "kb_procedures": [],
            "total_results": 0
        }
        logger.info("→ 검색 단계를 스킵하고 바로 AI 분석으로 이동합니다.")

    # 워크플로우 컴파일 및 실행
    workflow = compile_workflow()

    logger.info("\n워크플로우 실행 중...")
    result = await workflow.ainvoke(initial_state)

    logger.info("✅ 워크플로우 실행 완료")

    return result


def print_workflow_result(result: Dict[str, Any]):
    """
    워크플로우 결과를 보기 좋게 출력

    Args:
        result: 워크플로우 실행 결과
    """
    logger.info(f"\n{'='*60}")
    logger.info("AI 분석 결과")
    logger.info(f"{'='*60}")

    # 1. 제안된 응답
    proposed_action = result.get("proposed_action", {})
    draft_response = proposed_action.get("draft_response", "N/A")
    confidence = proposed_action.get("confidence", 0.0)

    logger.info(f"\n[AI 응답 초안]")
    logger.info(f"{draft_response}")
    logger.info(f"\n신뢰도: {confidence:.2f} ({confidence*100:.0f}%)")

    # 2. 필드 업데이트 제안
    field_updates = proposed_action.get("proposed_field_updates", {})
    if field_updates:
        logger.info(f"\n[필드 업데이트 제안]")
        for key, value in field_updates.items():
            logger.info(f"  {key}: {value}")

    # 3. 근거
    justification = proposed_action.get("justification", "")
    if justification:
        logger.info(f"\n[근거]")
        logger.info(f"{justification}")

    # 4. 검색 결과 (있다면)
    search_results = result.get("search_results", {})
    similar_cases = search_results.get("similar_cases", [])
    kb_procedures = search_results.get("kb_procedures", [])

    logger.info(f"\n[참조 자료]")
    logger.info(f"  유사 사례: {len(similar_cases)}개")
    logger.info(f"  KB 문서: {len(kb_procedures)}개")

    # 5. 승인 상태
    approval_status = result.get("approval_status", "N/A")
    logger.info(f"\n[승인 상태]")
    logger.info(f"  {approval_status}")

    # 6. 에러 (있다면)
    errors = result.get("errors", [])
    if errors:
        logger.info(f"\n[에러]")
        for error in errors:
            logger.error(f"  - {error}")

    logger.info(f"\n{'='*60}\n")


async def process_ticket(ticket_id: str, tenant_id: str = "default-tenant", skip_search: bool = True):
    """
    특정 티켓을 처리하는 메인 함수

    Args:
        ticket_id: Freshdesk 티켓 ID
        tenant_id: 테넌트 ID (기본값: "default-tenant")
        skip_search: 검색 단계 스킵 여부
    """
    try:
        # 1. Freshdesk 클라이언트 초기화
        logger.info("Freshdesk 클라이언트 초기화...")
        freshdesk = FreshdeskClient()

        # 2. 티켓 + 대화 내역 조회
        data = await fetch_ticket_with_conversations(freshdesk, ticket_id)

        # 3. Enriched context 생성
        logger.info("\n티켓 컨텍스트 생성 중...")
        ticket_context = await build_enriched_context(
            data["ticket"],
            data["conversations"],
            tenant_id=tenant_id
        )

        logger.info(f"✅ 컨텍스트 생성 완료")
        logger.info(f"   테넌트 ID: {ticket_context.tenant_id}")
        logger.info(f"   제목: {ticket_context.subject}")
        logger.info(f"   설명 길이: {len(ticket_context.description)} 문자")
        logger.info(f"   상태: {ticket_context.status.value}")
        logger.info(f"   우선순위: {ticket_context.priority.value}")
        logger.info(f"   포함된 대화 수: {len(data['conversations'])}개")

        # 4. 워크플로우 실행
        result = await run_workflow_direct(ticket_context, skip_search=skip_search)

        # 5. 결과 출력
        print_workflow_result(result)

        # 6. 요약
        logger.info(f"\n{'='*60}")
        logger.info("처리 완료 요약")
        logger.info(f"{'='*60}")
        logger.info(f"티켓 ID: {ticket_id}")
        logger.info(f"대화 수: {len(data['conversations'])}개")

        # proposed_action이 있는 경우에만 신뢰도 출력
        if result.get('proposed_action'):
            confidence = result['proposed_action'].get('confidence', 0.0)
            logger.info(f"AI 신뢰도: {confidence:.2f}")
        else:
            logger.warning("proposed_action이 생성되지 않았습니다.")

        logger.info(f"검색 스킵: {skip_search}")
        logger.info(f"승인 상태: {result.get('approval_status', 'N/A')}")

        # 에러가 있다면 출력
        if result.get('errors'):
            logger.warning(f"에러 발생: {result['errors']}")

        logger.info(f"{'='*60}\n")

        return result

    except Exception as e:
        logger.error(f"\n❌ 처리 실패: {e}", exc_info=True)
        logger.error(f"워크플로우 결과 상태: {result if 'result' in locals() else 'N/A'}")
        raise


async def main():
    """메인 실행 함수"""
    # 환경변수 확인 (디버그)
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        logger.info(f"✅ GOOGLE_API_KEY 환경변수 감지됨 (길이: {len(google_key)})")
    else:
        logger.warning("⚠️  GOOGLE_API_KEY 환경변수가 설정되지 않았습니다")
        logger.warning("   export GOOGLE_API_KEY=your-key 또는 .env 파일에 추가하세요")

    # 커맨드 라인 파라미터 검증
    if len(sys.argv) < 2:
        logger.error("사용법: python backend/scripts/process_single_ticket.py <ticket_id> [tenant_id] [skip_search]")
        logger.error("예시:")
        logger.error("  python backend/scripts/process_single_ticket.py 12345")
        logger.error("  python backend/scripts/process_single_ticket.py 12345 my-tenant")
        logger.error("  python backend/scripts/process_single_ticket.py 12345 my-tenant false")
        logger.error("")
        logger.error("환경변수로도 설정 가능:")
        logger.error("  export TENANT_ID=my-tenant")
        sys.exit(1)

    # 티켓 ID (필수)
    ticket_id = sys.argv[1]

    # 테넌트 ID (선택, 기본값: 환경변수 또는 "default-tenant")
    tenant_id = "default-tenant"
    if len(sys.argv) >= 3:
        tenant_id = sys.argv[2]
    elif os.getenv("TENANT_ID"):
        tenant_id = os.getenv("TENANT_ID")

    # 검색 스킵 여부 (선택, 기본값: True)
    skip_search = True
    if len(sys.argv) >= 4:
        skip_search = sys.argv[3].lower() in ['true', '1', 'yes', 'y']

    logger.info(f"\n{'='*60}")
    logger.info(f"특정 티켓 처리 스크립트")
    logger.info(f"{'='*60}")
    logger.info(f"티켓 ID: {ticket_id}")
    logger.info(f"테넌트 ID: {tenant_id}")
    logger.info(f"검색 스킵: {skip_search}")
    logger.info(f"{'='*60}\n")

    # 티켓 처리
    await process_ticket(ticket_id, tenant_id=tenant_id, skip_search=skip_search)


if __name__ == "__main__":
    asyncio.run(main())
