"""
데이터 수집 및 저장 모듈

이 모듈은 Freshdesk에서 티켓과 지식베이스 문서를 가져와 임베딩한 후,
Qdrant 벡터 데이터베이스에 저장하는 기능을 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import asyncio
import logging
import time
import sys
import shutil
import os
import json
from datetime import datetime
from freshdesk.fetcher import fetch_tickets, fetch_kb_articles, FRESHDESK_DOMAIN
from core.embedder import embed_documents, process_documents
from data.attachment_processor import process_attachments as process_attachment_files
from core.vectordb import vector_db
from typing import Dict, Any, Union

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"  # Qdrant 컬렉션 이름
PROCESS_ATTACHMENTS = True  # 첨부파일 처리 여부 설정
DB_PATH = "./qdrant_data"  # 데이터베이스 경로
STATUS_MAPPINGS_FILE = "status_mappings.json"  # 상태 매핑 정보 파일

# 상태 매핑 정보 (기본값)
# 티켓 상태 매핑
TICKET_STATUS_MAP = {
    2: "open",
    3: "pending",
    4: "resolved",
    5: "closed",
    6: "waiting on customer",
    7: "waiting on third party",
}

# 지식베이스 상태 매핑
KB_STATUS_MAP = {1: "draft", 2: "published"}


def load_status_mappings():
    """상태 매핑 정보를 파일에서 로드합니다. 파일이 없으면 기본값을 사용합니다."""
    try:
        if os.path.exists(STATUS_MAPPINGS_FILE):
            with open(STATUS_MAPPINGS_FILE, "r") as f:
                mappings = json.load(f)
                logger.info(f"상태 매핑 파일 로드 완료: {STATUS_MAPPINGS_FILE}")
                return mappings
    except Exception as e:
        logger.warning(f"상태 매핑 파일 로드 실패: {e}. 기본 매핑을 사용합니다.")

    # 기본 매핑 반환
    return {"ticket": TICKET_STATUS_MAP, "kb": KB_STATUS_MAP}


def save_status_mappings(mappings):
    """상태 매핑 정보를 파일에 저장합니다."""
    try:
        with open(STATUS_MAPPINGS_FILE, "w") as f:
            json.dump(mappings, f, indent=2)
            logger.info(f"상태 매핑 파일 저장 완료: {STATUS_MAPPINGS_FILE}")
    except Exception as e:
        logger.error(f"상태 매핑 파일 저장 실패: {e}")


# 상태 매핑 정보 로드
STATUS_MAPPINGS = load_status_mappings()


def backup_database():
    """Qdrant 데이터베이스를 백업합니다."""
    if os.path.exists(DB_PATH) and os.path.isdir(DB_PATH):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{DB_PATH}_backup_{timestamp}"
        try:
            shutil.copytree(DB_PATH, backup_path)
            logger.info(f"데이터베이스 백업 완료: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"데이터베이스 백업 실패: {e}")
            return False
    return False


def verify_database_integrity():
    """Qdrant 데이터베이스의 무결성을 검증합니다."""
    try:
        # 기본 company_id로 문서 수 확인
        DEFAULT_COMPANY_ID = "default"
        count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
        logger.info(f"컬렉션 '{COLLECTION_NAME}' (company_id={DEFAULT_COMPANY_ID}): {count}개 문서")

        # 전체 문서 수 확인
        total_count = vector_db.count()
        logger.info(f"컬렉션 '{COLLECTION_NAME}' 전체: {total_count}개 문서")

        # 샘플 쿼리 실행
        try:
            if total_count > 0:
                # 테스트 임베딩
                test_embedding = embed_documents(["test"])[0]
                # 특정 회사 ID로 문서 검색
                result = vector_db.search(query_embedding=test_embedding, top_k=1, company_id=DEFAULT_COMPANY_ID)
                if not result or "ids" not in result or not result["ids"]:
                    if count > 0:  # 문서가 있는데 결과가 없으면 경고
                        logger.warning(f"컬렉션 '{COLLECTION_NAME}'에 쿼리 결과 없음 (company_id={DEFAULT_COMPANY_ID})")
        except Exception as e:
            logger.error(f"쿼리 테스트 실패: {e}")
            return False

        return True
    except Exception as e:
        logger.error(f"데이터베이스 무결성 검증 실패: {e}")
        return False


def sanitize_metadata(
    metadata: Dict[str, Any],
) -> Dict[str, Union[str, int, float, bool]]:
    """
    메타데이터 값을 Qdrant 호환 형식으로 변환합니다.

    Qdrant는 메타데이터 값으로 문자열, 정수, 소수점, 불리언만 허용합니다.
    이 함수는 다른 형식의 값을 적절하게 변환합니다:
    - 리스트: JSON 문자열로 변환
    - None: 빈 문자열이나 0, False 등 적절한 기본값으로 대체
    - 객체: JSON 문자열로 변환

    Args:
        metadata: 원본 메타데이터 딕셔너리

    Returns:
        Qdrant 호환 형식으로 변환된 메타데이터 딕셔너리
    """
    sanitized = {}

    for key, value in metadata.items():
        # None 값 처리
        if value is None:
            # 필드 타입에 따라 적절한 기본값 설정
            if key in ["tags", "processed_attachments"]:
                sanitized[key] = "[]"  # 빈 리스트는 빈 JSON 배열 문자열로
            elif key in ["priority", "hits", "thumbs_up", "thumbs_down"]:
                sanitized[key] = 0  # 숫자 필드는 0으로
            elif key in [
                "has_attachments",
                "has_conversations",
                "is_escalated",
                "fr_escalated",
            ]:
                sanitized[key] = False  # 불리언 필드는 False로
            else:
                sanitized[key] = ""  # 나머지는 빈 문자열로

        # 리스트 값 처리
        elif isinstance(value, list):
            # 태그 및 리스트 필드는 JSON 문자열로 변환
            try:
                sanitized[key] = json.dumps(value, ensure_ascii=False)
            except TypeError:
                # 변환 실패 시 안전한 대체값 사용
                logger.warning(f"리스트 값 JSON 변환 실패: {key}={value}")
                sanitized[key] = "[]"

        # 딕셔너리 값 처리
        elif isinstance(value, dict):
            try:
                sanitized[key] = json.dumps(value, ensure_ascii=False)
            except TypeError:
                logger.warning(f"딕셔너리 값 JSON 변환 실패: {key}={value}")
                sanitized[key] = "{}"

        # 기본 타입(문자열, 정수, 소수점, 불리언) 유지
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value

        # 그 외 타입은 문자열로 변환
        else:
            try:
                sanitized[key] = str(value)
            except Exception:
                logger.warning(
                    f"알 수 없는 타입 변환 실패: {key}={value}, 타입: {type(value)}"
                )
                sanitized[key] = ""

    return sanitized


async def ingest(
    incremental: bool = True,
    purge: bool = False,
    process_attachments: bool = PROCESS_ATTACHMENTS,
    force_rebuild: bool = False,
) -> None:
    """
    Freshdesk 티켓과 지식베이스 문서를 임베딩 후 Qdrant에 저장합니다.

    Args:
        incremental: 증분 업데이트 모드 여부 (기본값: True)
                    True일 경우 기존 문서는 유지하고 새 문서만 추가합니다.
        purge: 기존 데이터 삭제 여부 (기본값: False)
               True일 경우 기존 데이터를 모두 삭제하고 새로 저장합니다.
        process_attachments: 첨부파일 처리 여부 (기본값: PROCESS_ATTACHMENTS)
                          True일 경우 첨부파일을 다운로드하여 텍스트 추출
        force_rebuild: 데이터베이스 강제 재구축 여부 (기본값: False)
                      True일 경우 기존 데이터베이스를 백업하고 새로 구축합니다.
    """
    start_time = time.time()
    logger.info("데이터 수집 프로세스 시작")

    try:
        # 데이터베이스 강제 재구축 옵션 처리
        if force_rebuild:
            logger.warning("데이터베이스 강제 재구축 모드")
            backup_database()
            # Qdrant는 API를 통해 컬렉션을 재생성합니다
            # DB_PATH는 로컬 Qdrant 인스턴스일 때만 관련이 있습니다
            incremental = False
            purge = True  # 컬렉션 재생성을 위해 purge 플래그 설정
        
        # 기존 컬렉션 정보 로깅 (기본 company_id로 검색)
        DEFAULT_COMPANY_ID = "kyexpert"
        existing_count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
        logger.info(f"기존 컬렉션에 {existing_count}개 문서가 있습니다 (company_id={DEFAULT_COMPANY_ID})")

        # 전체 문서 수 확인
        total_count = vector_db.count()
        logger.info(f"컬렉션 전체 문서 수: {total_count}")
        
        # 무결성 검증
        if total_count == 0 and purge is False:
            logger.warning("컬렉션에 문서가 없습니다. 데이터베이스가 비어있거나 접근에 문제가 있을 수 있습니다.")
            
            # 백업 후 처리 (Qdrant 컬렉션은 재생성하지 않고 데이터만 정리)
            backup_success = backup_database()
            if backup_success:
                logger.info("기존 데이터베이스 초기화 중...")
                incremental = False
                purge = False

            # purge 옵션이 True인 경우 기존 데이터 삭제
            if purge:
                logger.info("기존 데이터 삭제 중...")
                # 회사별 데이터 삭제를 위한 준비
                # 참고: 실제 환경에서는 현재 사용자의 company_id를 사용해야 함
                DEFAULT_COMPANY_ID = "kyexpert"
                
                # 기존 Qdrant 검색으로 문서 ID 가져오기
                # 기본 검색 쿼리로 최대한 많은 문서 ID 획득
                dummy_embedding = embed_documents(["dummy query for retrieval"])[0]
                # 해당 회사의 모든 문서 검색 (최대 1000개)
                search_results = vector_db.search(
                    query_embedding=dummy_embedding,
                    top_k=1000,  # 1000개까지만 검색
                    company_id=DEFAULT_COMPANY_ID
                )
                
                all_ids = search_results.get("ids", [])
                if all_ids:
                    logger.info(f"{len(all_ids)}개 문서 삭제 중...")
                    # 배치로 처리
                    batch_size = 100
                    for i in range(0, len(all_ids), batch_size):
                        batch = all_ids[i : i + batch_size]
                        logger.info(
                            f"문서 일괄 삭제 중... ({i+1}~{i+len(batch)}/{len(all_ids)})"
                        )
                        # 회사 ID 필터 적용하여 삭제
                        vector_db.delete_documents(ids=batch, company_id=DEFAULT_COMPANY_ID)
                incremental = False  # 데이터를 삭제했으므로 증분 업데이트가 아님

        logger.info("Freshdesk 데이터 수집 중...")

        # 티켓과 지식베이스 문서 동시에 가져오기
        tickets_task = asyncio.create_task(fetch_tickets())
        articles_task = asyncio.create_task(fetch_kb_articles())

        # 두 작업 완료 대기
        tickets, articles = await asyncio.gather(tickets_task, articles_task)

        if not tickets and not articles:
            logger.warning("Freshdesk에서 가져온 데이터가 없습니다.")
            return

        # 2. 삭제된 문서 감지 및 처리 (증분 업데이트 모드에서만)
        if incremental:
            # 회사 문서 수 확인 (상세 ID 목록은 Qdrant에서는 직접 조회가 어려움)
            DEFAULT_COMPANY_ID = "kyexpert"
            existing_count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
            logger.info(f"기존 문서 {existing_count}개 확인됨 (company_id={DEFAULT_COMPANY_ID})")
            
            # ID 목록 생성을 위한 검색 수행
            # 참고: Qdrant에서는 전체 ID 목록을 직접 가져올 수 없어 검색을 통해 추정
            dummy_embedding = embed_documents(["get all documents"])[0]
            result = vector_db.search(
                query_embedding=dummy_embedding,
                top_k=1000,  # 최대 1000개까지만 검색 (더 많은 문서가 있으면 모두 처리하지 못할 수 있음)
                company_id=DEFAULT_COMPANY_ID
            )
            existing_ids = set(result.get("ids", []))

            # 현재 Freshdesk에 존재하는 문서 ID 목록 생성
            current_ids = set()
            for t in tickets:
                # 티켓 ID와 청크 ID 모두 포함
                base_id = f"ticket-{t.get('id')}"
                current_ids.add(base_id)

                # 기존에 청킹된 문서도 고려
                for existing_id in existing_ids:
                    if existing_id.startswith(f"{base_id}_chunk_"):
                        current_ids.add(existing_id)

            for a in articles:
                # 지식베이스 ID와 청크 ID 모두 포함
                base_id = f"kb-{a.get('id')}"
                current_ids.add(base_id)

                # 기존에 청킹된 문서도 고려
                for existing_id in existing_ids:
                    if existing_id.startswith(f"{base_id}_chunk_"):
                        current_ids.add(existing_id)

            # 삭제된 문서 식별 (기존에는 있었지만 현재는 없는 ID)
            deleted_ids = existing_ids - current_ids

            if deleted_ids:
                logger.info(f"{len(deleted_ids)}개 삭제된 문서 감지됨")
                # 삭제된 문서 제거
                deleted_ids_list = list(deleted_ids)
                # 배치로 처리
                batch_size = 100
                # 기본 company_id (실제 환경에서는 인증된 사용자의 company_id 사용)
                DEFAULT_COMPANY_ID = "default"
                
                for i in range(0, len(deleted_ids_list), batch_size):
                    batch = deleted_ids_list[i : i + batch_size]
                    logger.info(
                        f"삭제된 문서 제거 중... ({i+1}~{i+len(batch)}/{len(deleted_ids_list)})"
                    )
                    vector_db.delete_documents(ids=batch, company_id=DEFAULT_COMPANY_ID)
                logger.info(
                    f"{len(deleted_ids)}개 삭제된 문서가 데이터베이스에서 제거됨"
                )

        # 3. 문서 준비
        all_documents = []

        # 기존 문서 ID 목록 가져오기 (삭제 후 갱신)
        existing_ids = set()
        if incremental:
            # Qdrant에서는 전체 ID 목록을 직접 가져올 수 없어 검색으로 추정
            DEFAULT_COMPANY_ID = "default"
            dummy_embedding = embed_documents(["get all documents"])[0]
            result = vector_db.search(
                query_embedding=dummy_embedding,
                top_k=1000,  # 최대 1000개까지만 검색
                company_id=DEFAULT_COMPANY_ID
            )
            existing_ids = set(result.get("ids", []))
            existing_count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
            logger.info(f"현재 문서 {existing_count}개 확인됨 (삭제 처리 후, 최대 1000개 ID 샘플링)")

        logger.info("티켓 데이터 처리 중...")
        for t in tickets:
            doc_id = f"ticket-{t.get('id')}"
            ticket_id = t.get("id")

            # 증분 업데이트 모드에서 처리 로직
            # 티켓의 updated_at 값이 변경된 경우 또는 기존에 없는 티켓인 경우 처리
            updated_at = t.get("updated_at")
            if incremental:
                # 기존 문서가 존재하는지 확인
                if doc_id in existing_ids:
                    # 기존 문서의 메타데이터 조회
                    existing_meta = None
                    try:
                        # Qdrant는 get 메서드가 다르게 동작합니다
                        # 회사 ID 필터링과 함께 검색으로 대체
                        result = vector_db.get_by_id(id=doc_id, company_id=DEFAULT_COMPANY_ID)
                        if result and "metadata" in result:
                            existing_meta = result["metadata"]
                    except Exception as e:
                        logger.warning(f"기존 메타데이터 조회 실패: {e}")

                    # 기존 메타데이터의 updated_at과 비교
                    if existing_meta and "updated_at" in existing_meta:
                        if existing_meta["updated_at"] == updated_at:
                            logger.debug(
                                f"티켓 {ticket_id}는 변경되지 않았습니다. 건너뜁니다."
                            )
                            continue
                        else:
                            logger.info(
                                f"티켓 {ticket_id}의 updated_at이 변경되었습니다. 업데이트합니다."
                            )
                    else:
                        logger.info(
                            f"티켓 {ticket_id}의 메타데이터에 updated_at이 없습니다. 업데이트합니다."
                        )

            # 첨부파일 처리
            all_attachments = t.get("all_attachments", [])
            if process_attachments and all_attachments:
                logger.info(
                    f"티켓 {ticket_id}의 첨부파일 {len(all_attachments)}개 처리 중..."
                )
                processed_attachments = await process_attachment_files(all_attachments)
                t["processed_attachments"] = processed_attachments
            else:
                t["processed_attachments"] = []

            # 기본 티켓 정보 처리
            ticket_content = []
            ticket_content.append(f"제목: {t.get('subject', '')}")

            # 설명 처리 - API 응답에서는 'description'과 'description_text' 모두 존재
            # description_text는 HTML 태그가 제거된 일반 텍스트
            description = t.get("description_text", t.get("description", ""))
            ticket_content.append(f"설명: {description}")

            # 대화 내역 추가
            conversations = t.get("conversations", [])
            if conversations:
                ticket_content.append("\n===== 대화 내역 =====")
                for i, conv in enumerate(conversations):
                    ticket_content.append(
                        f"[대화 {i+1}] - {conv.get('created_at', '')}"
                    )
                    # user_id 대신 실제 API 응답 구조 사용
                    user_info = f"사용자 ID: {conv.get('user_id', '')}"
                    if conv.get("from_email"):
                        user_info += f" ({conv.get('from_email')})"
                    ticket_content.append(user_info)

                    # API 응답에서는 body와 body_text 모두 존재
                    # body_text는 HTML 태그가 제거된 일반 텍스트
                    body = conv.get("body_text", conv.get("body", ""))
                    ticket_content.append(f"내용: {body}")

                    # 대화의 첨부파일 정보
                    attachments = conv.get("attachments", [])
                    if attachments:
                        ticket_content.append("첨부파일:")
                        for att in attachments:
                            ticket_content.append(
                                f"  - {att.get('name', '')} ({att.get('content_type', '')})"
                            )

            # 첨부파일 정보 및 추출된 텍스트 추가
            processed_attachments = t.get("processed_attachments", [])
            image_infos = []  # 이미지 메타데이터만 저장
            source_id = str(ticket_id)

            if processed_attachments:
                ticket_content.append("\n===== 첨부파일 내용 =====")
                for att in processed_attachments:
                    if att.get("processed", False):
                        ticket_content.append(f"파일: {att.get('name', '')}")
                        extracted_text = att.get("extracted_text", "")
                        if (
                            isinstance(extracted_text, dict)
                            and "text" in extracted_text
                        ):
                            ticket_content.append(
                                f"추출된 텍스트: {extracted_text['text']}"
                            )
                        else:
                            ticket_content.append(f"추출된 텍스트: {extracted_text}")

                        # 이미지인 경우 pre-signed URL이 아닌 메타데이터만 저장
                        if att.get("content_type", "").startswith("image/"):
                            image_infos.append({
                                "id": att.get("id"),
                                "name": att.get("name"),
                                "content_type": att.get("content_type"),
                                "size": att.get("size"),
                                "updated_at": att.get("updated_at"),
                                "source_type": "ticket",
                                "source_id": source_id,
                                # URL은 저장하지 않음. 프론트엔드는 표시 시점에 Freshdesk API로 최신 pre-signed URL을 발급받아야 함.
                            })

            # 대화 내역의 첨부파일도 이미지 메타데이터만 수집
            conversations = t.get("conversations", [])
            if conversations:
                for conv in conversations:
                    attachments = conv.get("attachments", [])
                    for att in attachments:
                        if att.get("content_type", "").startswith("image/"):
                            image_infos.append({
                                "id": att.get("id"),
                                "name": att.get("name"),
                                "content_type": att.get("content_type"),
                                "size": att.get("size"),
                                "updated_at": att.get("updated_at"),
                                "source_type": "conversation",
                                "source_id": source_id,
                                "conversation_id": conv.get("id", ""),
                                # URL은 저장하지 않음. 프론트엔드는 표시 시점에 Freshdesk API로 최신 pre-signed URL을 발급받아야 함.
                            })

            doc_text = "\n".join(ticket_content)

            if doc_text.strip():  # 빈 문서 제외
                # 메타데이터 구성 - API 응답 구조에 맞게 수정
                source_id = str(ticket_id)

                # source_url 생성
                source_url = (
                    f"https://{FRESHDESK_DOMAIN}.freshdesk.com/a/tickets/{source_id}"
                )

                # 티켓 태그 처리
                tags = t.get("tags", [])

                # 상태 코드 매핑 (API 응답이 숫자 코드인 경우를 대비)
                # Freshdesk API 상태 코드: 2 = open, 3 = pending, 4 = resolved, 5 = closed, 6 = waiting on customer, 7 = waiting on third party
                status_map = STATUS_MAPPINGS.get("ticket", TICKET_STATUS_MAP)
                status = t.get("status")
                if isinstance(status, int) and status in status_map:
                    status = status_map[status]

                # 사용자 정의 필드 처리
                custom_fields = t.get("custom_fields", {})
                # 사용자 정의 필드 중 category가 있으면 태그에 추가
                if (
                    "category" in custom_fields
                    and custom_fields["category"] not in tags
                ):
                    tags.append(custom_fields["category"])

                # 티켓 메타데이터 구성 (기본 필드 + 커스텀 필드 전체 포함)
                metadata = {
                    "type": "ticket",
                    "source_id": source_id,
                    "id": t.get("id"),
                    "subject": t.get("subject"),
                    "description": t.get("description"),
                    "description_text": t.get("description_text"),
                    "status": t.get("status"),
                    "priority": t.get("priority", 1),
                    "tags": tags,
                    "product": t.get("product_id", ""),
                    "language": t.get("language", "ko"),
                    "source_url": source_url,
                    "created_at": t.get("created_at"),
                    "updated_at": updated_at,
                    "due_by": t.get("due_by"),
                    "fr_due_by": t.get("fr_due_by"),
                    "is_escalated": t.get("is_escalated", False),
                    "fr_escalated": t.get("fr_escalated", False),
                    "company_id": t.get("company_id"),
                    "requester_id": t.get("requester_id"),
                    "responder_id": t.get("responder_id"),
                    "group_id": t.get("group_id"),
                    "source": t.get("source"),
                    "has_attachments": len(all_attachments) > 0,
                    "has_conversations": len(conversations) > 0,
                    "processed_attachments": len(processed_attachments) > 0,
                    "image_attachments": (image_infos if image_infos else []),
                    # 커스텀 필드는 JSON 문자열로 저장 (Qdrant 호환)
                    "custom_fields": json.dumps(t.get("custom_fields", {}), ensure_ascii=False),
                    # description(HTML) 내 인라인 이미지 id 등도 필요시 별도 필드로 저장 가능
                }

                # 메타데이터 값을 벡터 DB 호환 형식으로 변환
                sanitized_metadata = sanitize_metadata(metadata)

                # 메타데이터 크기가 너무 크면 벡터 DB에서 오류가 발생할 수 있으므로
                # 기본 필드만 유지하고 나머지는 제외
                # 사용자 정의 필드가 많은 경우 주의해야 함

                all_documents.append(
                    {"id": doc_id, "text": doc_text, "metadata": sanitized_metadata}
                )

        logger.info("지식베이스 문서 처리 중...")
        for a in articles:
            doc_id = f"kb-{a.get('id')}"
            article_id = a.get("id")

            # 증분 업데이트 모드에서 처리 로직
            # 지식베이스 문서의 updated_at 값이 변경된 경우 또는 기존에 없는 문서인 경우 처리
            updated_at = a.get("updated_at")
            if incremental:
                # 기존 문서가 존재하는지 확인
                if doc_id in existing_ids:
                    # 기존 문서의 메타데이터 조회
                    existing_meta = None
                    try:
                        # Qdrant는 get 메서드가 다르게 동작합니다
                        # 회사 ID 필터링과 함께 검색으로 대체
                        result = vector_db.get_by_id(id=doc_id, company_id=DEFAULT_COMPANY_ID)
                        if result and "metadata" in result:
                            existing_meta = result["metadata"]
                    except Exception as e:
                        logger.warning(f"기존 메타데이터 조회 실패: {e}")

                    # 기존 메타데이터의 updated_at과 비교
                    if existing_meta and "updated_at" in existing_meta:
                        if existing_meta["updated_at"] == updated_at:
                            logger.debug(
                                f"지식베이스 문서 {article_id}는 변경되지 않았습니다. 건너뜁니다."
                            )
                            continue
                        else:
                            logger.info(
                                f"지식베이스 문서 {article_id}의 updated_at이 변경되었습니다. 업데이트합니다."
                            )
                    else:
                        logger.info(
                            f"지식베이스 문서 {article_id}의 메타데이터에 updated_at이 없습니다. 업데이트합니다."
                        )

            # 첨부파일 처리
            attachments = a.get("attachments", [])
            if process_attachments and attachments:
                logger.info(
                    f"지식베이스 문서 {article_id}의 첨부파일 {len(attachments)}개 처리 중..."
                )
                processed_attachments = await process_attachment_files(attachments)
                a["processed_attachments"] = processed_attachments
            else:
                a["processed_attachments"] = []

            # 이미지 첨부파일 메타데이터만 저장 (FAQ도 동일 정책)
            image_infos = []
            for att in a["processed_attachments"]:
                if att.get("content_type", "").startswith("image/"):
                    image_infos.append({
                        "id": att.get("id"),
                        "name": att.get("name"),
                        "content_type": att.get("content_type"),
                        "size": att.get("size"),
                        "updated_at": att.get("updated_at"),
                        "source_type": "kb",
                        "source_id": article_id,
                        # URL은 저장하지 않음. 프론트엔드는 표시 시점에 Freshdesk API로 최신 pre-signed URL을 발급받아야 함.
                    })

            # 문서 내용 준비
            article_content = []
            article_content.append(f"제목: {a.get('title', '')}")
            article_content.append(f"설명: {a.get('description_text', '')}")

            # 추출된 첨부파일 내용 추가
            processed_attachments = a.get("processed_attachments", [])
            if processed_attachments:
                article_content.append("\n===== 첨부파일 내용 =====")
                for att in processed_attachments:
                    if att.get("processed", False) and att.get("extracted_text"):
                        article_content.append(f"파일: {att.get('name', '')}")
                        article_content.append(
                            f"추출된 텍스트: {att.get('extracted_text', '')}"
                        )

            doc_text = "\n".join(article_content)

            if doc_text.strip():  # 빈 문서 제외
                # 메타데이터 구성 - API 응답 구조에 맞게 수정
                source_id = str(article_id)

                # source_url 생성
                source_url = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/solution/articles/{source_id}"

                # 문서 태그 처리
                tags = a.get("tags", [])

                # 계층 정보(hierarchy) 처리
                category_name = None
                folder_name = None
                if "hierarchy" in a and a["hierarchy"]:
                    for item in a["hierarchy"]:
                        if item.get("type") == "category" and "data" in item:
                            category_name = item["data"].get("name")
                        elif item.get("type") == "folder" and "data" in item:
                            # 마지막 폴더 이름 저장
                            folder_name = item["data"].get("name")

                # 폴더와 카테고리 정보를 태그로 추가
                if folder_name and folder_name not in tags:
                    tags.append(folder_name)
                if category_name and category_name not in tags:
                    tags.append(category_name)

                # 조회수(hits) 처리
                hits = a.get("hits", 0)

                # 상태 코드 변환 (2 = published, 1 = draft 등)
                # API 상태 코드: 1 = draft, 2 = published
                status_map = STATUS_MAPPINGS.get("kb", KB_STATUS_MAP)
                status = status_map.get(a.get("status"), "unknown")

                # 언어 처리
                language = a.get("language", "ko")
                if "hierarchy" in a and a["hierarchy"] and len(a["hierarchy"]) > 0:
                    if (
                        "data" in a["hierarchy"][0]
                        and "language" in a["hierarchy"][0]["data"]
                    ):
                        language = a["hierarchy"][0]["data"]["language"]

                # 지식베이스 메타데이터 구성
                metadata = {
                    "type": "kb",
                    "source_id": source_id,
                    "id": a.get("id"),
                    "title": a.get("title"),
                    "description": a.get("description"),
                    "description_text": a.get("description_text"),
                    "status": a.get("status"),
                    "tags": tags,
                    "hits": hits,
                    "thumbs_up": a.get("thumbs_up", 0),
                    "thumbs_down": a.get("thumbs_down", 0),
                    "language": language,
                    "source_url": source_url,
                    "created_at": a.get("created_at"),
                    "updated_at": updated_at,
                    "folder_id": a.get("folder_id"),
                    "category_id": a.get("category_id"),
                    "agent_id": a.get("agent_id"),
                    "has_attachments": len(attachments) > 0,
                    "processed_attachments": len(processed_attachments) > 0,
                    "image_attachments": (image_infos if image_infos else []),
                    # 커스텀 필드는 JSON 문자열로 저장 (Qdrant 호환)
                    "custom_fields": json.dumps(a.get("custom_fields", {}), ensure_ascii=False),
                }

                # 메타데이터 값을 벡터 DB 호환 형식으로 변환
                sanitized_metadata = sanitize_metadata(metadata)

                all_documents.append(
                    {"id": doc_id, "text": doc_text, "metadata": sanitized_metadata}
                )

        if not all_documents and deleted_ids:
            logger.info("새 문서 추가 없이 삭제된 문서만 처리됨")
            elapsed_time = time.time() - start_time
            logger.info(
                f"데이터 수집 완료. {len(deleted_ids)}개 문서 삭제됨 (소요 시간: {elapsed_time:.2f}초)"
            )
            return
        elif not all_documents:
            logger.info("처리할 새 문서가 없습니다.")
            return

        logger.info(f"총 {len(all_documents)}개 신규 문서 처리 중...")

        # 4. 문서 청킹 처리 - 긴 문서를 여러 청크로 나눔
        logger.info(f"총 {len(all_documents)}개 문서 청킹 처리 중...")
        processed_docs = process_documents(all_documents)
        logger.info(f"청킹 처리 후 {len(processed_docs)}개 문서로 분할됨")

        # 5. Qdrant 저장 준비
        docs = [doc["text"] for doc in processed_docs]
        metadatas = [doc["metadata"] for doc in processed_docs]
        ids = [doc["id"] for doc in processed_docs]
        
        # 모든 메타데이터에 company_id 추가 (실제 환경에서는 인증된 사용자의 company_id 사용)
        DEFAULT_COMPANY_ID = "default"
        for metadata in metadatas:
            metadata["company_id"] = DEFAULT_COMPANY_ID

        # 6. 임베딩
        logger.info(f"총 {len(docs)}개 문서 임베딩 시작...")

        # 대량의 문서를 적절한 크기로 나누어 임베딩 - 메모리 효율성 향상
        batch_size = 50
        all_embeddings = []

        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i : i + batch_size]
            logger.info(
                f"문서 배치 임베딩 중... ({i+1}~{i+len(batch_docs)}/{len(docs)})"
            )
            batch_embeddings = embed_documents(batch_docs)
            all_embeddings.extend(batch_embeddings)

        # 7. Qdrant 저장
        logger.info("Qdrant 벡터 DB에 문서 저장 중...")

        # 배치 단위로 upsert 수행 - 메모리 효율성 향상
        for i in range(0, len(docs), batch_size):
            end_idx = min(i + batch_size, len(docs))
            batch_docs = docs[i:end_idx]
            batch_embeddings = all_embeddings[i:end_idx]
            batch_metadatas = metadatas[i:end_idx]
            batch_ids = ids[i:end_idx]

            logger.info(f"문서 배치 저장 중... ({i+1}~{end_idx}/{len(docs)})")
            vector_db.add_documents(
                texts=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                ids=batch_ids,
            )

        elapsed_time = time.time() - start_time
        deleted_count = len(deleted_ids) if "deleted_ids" in locals() else 0
        logger.info(
            f"데이터 수집 완료. 총 {len(docs)}개 문서 임베딩 및 저장, {deleted_count}개 문서 삭제 (소요 시간: {elapsed_time:.2f}초)"
        )

    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}", exc_info=True)
        raise


async def update_status_mappings(collection_name: str = COLLECTION_NAME) -> None:
    """
    상태 매핑 정보를 업데이트하고 기존 문서에 적용합니다.
    
    Qdrant로 전환 후에는 이 함수는 완전히 재구현되어야 합니다.
    현재 버전에서는 통계 정보만 표시하고 실제 업데이트는 수행하지 않습니다.
    
    향후 구현 방향:
    1. Qdrant의 스캐닝 API를 사용하여 모든 문서를 검색
    2. 필요한 문서만 업데이트하는 배치 작업 수행
    """
    logger.warning("Qdrant로 전환 후 상태 매핑 업데이트 기능은 아직 구현되지 않았습니다.")
    logger.info("상태 매핑 정보 업데이트를 위해 데이터 재구축이 필요할 수 있습니다.")
    
    try:
        # 기본적인 Qdrant 컬렉션 접근 확인 및 통계 표시
        DEFAULT_COMPANY_ID = "default"
        
        logger.info(f"전체 문서 수: {vector_db.count()} 개")
        logger.info(f"{DEFAULT_COMPANY_ID} 회사 문서 수: {vector_db.count(company_id=DEFAULT_COMPANY_ID)} 개")
        
        # TODO: Qdrant의 스캐닝 API를 사용하여 구현
        logger.info("이 기능은 현재 버전에서는 지원되지 않습니다.")
        return

    except Exception as e:
        logger.error(f"상태 매핑 정보 확인 중 오류 발생: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        import argparse

        parser = argparse.ArgumentParser(description="Freshdesk 데이터 수집 및 임베딩")
        parser.add_argument(
            "--full",
            action="store_true",
            help="전체 데이터 다시 수집 (기존 데이터 유지)",
        )
        parser.add_argument(
            "--purge", action="store_true", help="기존 데이터 삭제 후 전체 다시 수집"
        )
        parser.add_argument(
            "--no-attachments", action="store_true", help="첨부파일 처리 비활성화"
        )
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="데이터베이스 강제 재구축 (백업 후 처음부터 새로 시작)",
        )
        parser.add_argument(
            "--verify", action="store_true", help="데이터베이스 무결성만 검증하고 종료"
        )
        parser.add_argument(
            "--update-status",
            action="store_true",
            help="상태 매핑 업데이트만 수행 (데이터 수집 없음)",
        )
        parser.add_argument(
            "--edit-status-map", action="store_true", help="상태 매핑 설정 편집"
        )
        args = parser.parse_args()

        # 상태 매핑 편집 모드
        if args.edit_status_map:
            logger.info("상태 매핑 설정 편집 모드")
            try:
                import json

                # 현재 매핑 로드
                current_mappings = load_status_mappings()

                # 매핑 정보 출력
                print("\n현재 상태 매핑 설정:")
                print(json.dumps(current_mappings, indent=2, ensure_ascii=False))

                # 편집 안내
                print("\n상태 매핑을 편집하시겠습니까? (y/n)")
                response = input().strip().lower()

                if response == "y":
                    # 티켓 상태 매핑 편집
                    print(
                        "\n티켓 상태 매핑 편집 (형식: '상태코드:상태명', 예: '2:open')"
                    )
                    print(
                        "여러 항목은 쉼표로 구분하세요. 예: '2:open,3:pending,4:resolved'"
                    )
                    print(
                        "기존 값: "
                        + ", ".join(
                            [
                                f"{k}:{v}"
                                for k, v in current_mappings.get("ticket", {}).items()
                            ]
                        )
                    )
                    ticket_input = input("새 값 (빈 칸이면 기존 값 유지): ").strip()

                    if ticket_input:
                        new_ticket_map = {}
                        try:
                            for item in ticket_input.split(","):
                                if ":" in item:
                                    code, value = item.strip().split(":", 1)
                                    new_ticket_map[int(code)] = value.strip()
                            current_mappings["ticket"] = new_ticket_map
                        except Exception as e:
                            print(f"오류: 잘못된 형식입니다. {e}")

                    # 지식베이스 상태 매핑 편집
                    print(
                        "\n지식베이스 상태 매핑 편집 (형식: '상태코드:상태명', 예: '1:draft')"
                    )
                    print("여러 항목은 쉼표로 구분하세요. 예: '1:draft,2:published'")
                    print(
                        "기존 값: "
                        + ", ".join(
                            [
                                f"{k}:{v}"
                                for k, v in current_mappings.get("kb", {}).items()
                            ]
                        )
                    )
                    kb_input = input("새 값 (빈 칸이면 기존 값 유지): ").strip()

                    if kb_input:
                        new_kb_map = {}
                        try:
                            for item in kb_input.split(","):
                                if ":" in item:
                                    code, value = item.strip().split(":", 1)
                                    new_kb_map[int(code)] = value.strip()
                            current_mappings["kb"] = new_kb_map
                        except Exception as e:
                            print(f"오류: 잘못된 형식입니다. {e}")

                    # 저장
                    save_status_mappings(current_mappings)
                    print("\n상태 매핑이 저장되었습니다.")

                    # 적용 여부
                    print("\n새 상태 매핑을 기존 문서에 적용하시겠습니까? (y/n)")
                    apply_response = input().strip().lower()

                    if apply_response == "y":
                        print("상태 매핑 적용 중...")
                        asyncio.run(update_status_mappings())
                else:
                    print("상태 매핑 편집을 취소했습니다.")

                sys.exit(0)
            except Exception as e:
                logger.error(f"상태 매핑 편집 중 오류 발생: {e}", exc_info=True)
                sys.exit(1)

        # 상태 매핑 업데이트 모드
        if args.update_status:
            logger.info("상태 매핑 업데이트 모드")
            try:
                asyncio.run(update_status_mappings())
                sys.exit(0)
            except Exception as e:
                logger.error(f"상태 매핑 업데이트 중 오류 발생: {e}", exc_info=True)
                sys.exit(1)

        # 무결성 검증 모드
        if args.verify:
            logger.info("데이터베이스 무결성 검증 모드")
            is_valid = verify_database_integrity()
            if is_valid:
                logger.info("데이터베이스 무결성 검증 성공")
                sys.exit(0)
            else:
                logger.error("데이터베이스 무결성 검증 실패")
                sys.exit(1)

        # 명령줄 인자에 따라 실행 모드 결정
        incremental_mode = not (args.full or args.purge or args.rebuild)
        purge_mode = args.purge
        rebuild_mode = args.rebuild
        process_attachments = not args.no_attachments

        if rebuild_mode:
            logger.info("데이터베이스 강제 재구축 모드")
        elif purge_mode:
            logger.info("기존 데이터 삭제 후 전체 다시 수집 모드")
        elif incremental_mode:
            logger.info("증분 업데이트 모드 (신규 문서만 추가)")
        else:
            logger.info("전체 데이터 다시 수집 모드 (기존 데이터 유지)")

        if process_attachments:
            logger.info("첨부파일 처리 활성화됨")
        else:
            logger.info("첨부파일 처리 비활성화됨")

        asyncio.run(
            ingest(
                incremental=incremental_mode,
                purge=purge_mode,
                process_attachments=process_attachments,
                force_rebuild=rebuild_mode,
            )
        )
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로세스가 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        exit(1)
