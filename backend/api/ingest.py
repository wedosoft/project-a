"""
데이터 수집 및 저장 모듈

이 모듈은 Freshdesk에서 티켓과 지식베이스 문서를 가져와 임베딩한 후,
Qdrant 벡터 데이터베이스에 저장하는 기능을 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참고
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, Union

from core.embedder import embed_documents, process_documents
from core.vectordb import vector_db
from freshdesk.fetcher import fetch_kb_articles, fetch_tickets

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"  # Qdrant 컬렉션 이름
PROCESS_ATTACHMENTS = True  # 첨부파일 처리 여부 설정
STATUS_MAPPINGS_FILE = "status_mappings.json"  # 상태 매핑 정보 파일

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
    """
    상태 매핑 정보를 파일에서 로드합니다. 파일이 없으면 기본값을 사용합니다.
    """
    try:
        if os.path.exists(STATUS_MAPPINGS_FILE):
            with open(STATUS_MAPPINGS_FILE, "r") as f:
                mappings = json.load(f)
                logger.info(f"상태 매핑 파일 로드 완료: {STATUS_MAPPINGS_FILE}")
                return mappings
    except Exception as e:
        logger.warning(f"상태 매핑 파일 로드 실패: {e}. 기본 매핑을 사용합니다.")
    return {"ticket": TICKET_STATUS_MAP, "kb": KB_STATUS_MAP}


def save_status_mappings(mappings):
    """
    상태 매핑 정보를 파일에 저장합니다.
    """
    try:
        with open(STATUS_MAPPINGS_FILE, "w") as f:
            json.dump(mappings, f, indent=2)
            logger.info(f"상태 매핑 파일 저장 완료: {STATUS_MAPPINGS_FILE}")
    except Exception as e:
        logger.error(f"상태 매핑 파일 저장 실패: {e}")


# 상태 매핑 정보 로드
STATUS_MAPPINGS = load_status_mappings()


def sanitize_metadata(
    metadata: Dict[str, Any],
) -> Dict[str, Union[str, int, float, bool]]:
    """
    메타데이터 값을 Qdrant 호환 형식으로 변환합니다.
    Qdrant는 메타데이터 값으로 문자열, 정수, 소수점, 불리언만 허용합니다.
    이 함수는 다양한 타입의 값을 적절하게 변환합니다:
    - 리스트: JSON 문자열로 변환
    - None: 빈 문자열이나 0, False 등 기본값으로 대체
    - 객체: JSON 문자열로 변환
    """
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            if key in ["tags", "processed_attachments"]:
                sanitized[key] = "[]"
            elif key in ["priority", "hits", "thumbs_up", "thumbs_down"]:
                sanitized[key] = 0
            elif key in [
                "has_attachments",
                "has_conversations",
                "is_escalated",
                "fr_escalated",
            ]:
                sanitized[key] = False
            else:
                sanitized[key] = ""
        elif isinstance(value, list):
            try:
                sanitized[key] = json.dumps(value, ensure_ascii=False)
            except TypeError:
                logger.warning(f"리스트 값 JSON 변환 실패: {key}={value}")
                sanitized[key] = "[]"
        elif isinstance(value, dict):
            try:
                sanitized[key] = json.dumps(value, ensure_ascii=False)
            except TypeError:
                logger.warning(f"딕셔너리 값 JSON 변환 실패: {key}={value}")
                sanitized[key] = "{}"
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            try:
                sanitized[key] = str(value)
            except Exception:
                logger.warning(
                    f"알 수 없는 타입 변환 실패: {key}={value}, 타입: {type(value)}"
                )
                sanitized[key] = ""
    return sanitized


def load_local_data(data_dir: str):
    """
    로컬 디렉토리에서 이미 수집된 데이터를 로드합니다.
    
    Args:
        data_dir: 데이터가 저장된 디렉토리 경로
        
    Returns:
        tuple: (tickets, articles) - 티켓 리스트와 문서 리스트
    """
    import json
    from pathlib import Path
    
    data_path = Path(data_dir)
    tickets = []
    articles = []
    
    # all_tickets.json 파일 확인
    all_tickets_file = data_path / "all_tickets.json"
    if all_tickets_file.exists():
        logger.info(f"통합 티켓 파일에서 로드 중: {all_tickets_file}")
        with open(all_tickets_file, 'r', encoding='utf-8') as f:
            tickets = json.load(f)
        logger.info(f"로컬에서 {len(tickets)}개 티켓 로드 완료")
    else:
        # 청크 파일들 확인
        chunk_files = sorted(data_path.glob("tickets_chunk_*.json"))
        if chunk_files:
            logger.info(f"{len(chunk_files)}개 청크 파일에서 로드 중...")
            for chunk_file in chunk_files:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunk_tickets = json.load(f)
                    tickets.extend(chunk_tickets)
                    logger.info(f"{chunk_file.name}: {len(chunk_tickets)}개 티켓 로드")
            logger.info(f"청크 파일에서 총 {len(tickets)}개 티켓 로드 완료")
        else:
            logger.warning(f"로컬 데이터 디렉토리에서 티켓 파일을 찾을 수 없습니다: {data_dir}")
    
    # 지식베이스 문서는 현재 OptimizedFreshdeskFetcher에서 수집하지 않으므로 빈 리스트 반환
    logger.info("지식베이스 문서는 로컬 데이터에 없으므로 빈 리스트 반환")
    
    return tickets, articles


async def ingest(
    incremental: bool = True,
    purge: bool = False,
    process_attachments: bool = PROCESS_ATTACHMENTS,
    force_rebuild: bool = False,
    local_data_dir: str = None,
) -> None:
    """
    Freshdesk 티켓과 지식베이스 문서를 임베딩 후 Qdrant에 저장합니다.
    Args:
        incremental: 증분 업데이트 모드 여부 (기본값: True)
        purge: 기존 데이터 삭제 여부 (기본값: False)
        process_attachments: 첨부파일 처리 여부 (기본값: True)
        force_rebuild: 데이터베이스 강제 재구축 여부 (기본값: False)
        local_data_dir: 로컬 데이터 디렉토리 경로 (None이면 Freshdesk API에서 직접 수집)
    """
    start_time = time.time()
    logger.info("데이터 수집 프로세스 시작")

    try:
        # Qdrant 클라우드만 사용하므로, 로컬 DB 백업/무결성 검사 등은 제거됨
        if force_rebuild:
            logger.warning("데이터베이스 강제 재구축 모드 (Qdrant 클라우드 환경)")
            incremental = False
            purge = True
        
        DEFAULT_COMPANY_ID = "wedosoft"
        existing_count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
        logger.info(f"기존 컬렉션에 {existing_count}개 문서가 있습니다 (company_id={DEFAULT_COMPANY_ID})")

        total_count = vector_db.count()
        logger.info(f"컬렉션 전체 문서 수: {total_count}")
        
        if total_count == 0 and purge is False:
            logger.warning("컬렉션에 문서가 없습니다. 데이터베이스가 비어있거나 접근에 문제가 있을 수 있습니다.")
            incremental = False
            purge = False

        if local_data_dir:
            # 로컬에서 이미 수집된 데이터 읽기
            logger.info(f"로컬 데이터 디렉토리에서 데이터 로드 중: {local_data_dir}")
            tickets, articles = load_local_data(local_data_dir)
        else:
            # 기존 방식: Freshdesk API에서 직접 수집
            logger.info("Freshdesk 데이터 수집 중...")
            tickets_task = asyncio.create_task(fetch_tickets())
            articles_task = asyncio.create_task(fetch_kb_articles())
            tickets, articles = await asyncio.gather(tickets_task, articles_task)

        if not tickets and not articles:
            logger.warning("Freshdesk에서 가져온 데이터가 없습니다.")
            return

        # 2. 삭제된 문서 감지 및 처리 (증분 업데이트 모드에서만)
        if incremental:
            # 회사 문서 수 확인 (상세 ID 목록은 Qdrant에서는 직접 조회가 어려움)
            DEFAULT_COMPANY_ID = "wedosoft"
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
            updated_at = t.get("updated_at")
            # 증분 업데이트 모드에서 기존 문서가 있으면 건너뜀
            if incremental:
                if doc_id in existing_ids:
                    continue
            # description, description_text 등 주요 필드 보완
            if not t.get("description") or not t.get("description_text"):
                from freshdesk.fetcher import fetch_ticket_details
                detail = await fetch_ticket_details(ticket_id)
                if detail:
                    t.update({k: v for k, v in detail.items() if k not in t or not t[k]})
            # 첨부파일(이미지 등) 메타데이터만 저장
            attachments = t.get("attachments") or t.get("all_attachments")
            attachment_meta = []
            if attachments:
                for att in attachments:
                    if not att or not isinstance(att, dict):
                        continue
                    meta = {
                        "id": att.get("id"),
                        "name": att.get("name"),
                        "content_type": att.get("content_type"),
                        "size": att.get("size"),
                        "created_at": att.get("created_at"),
                        "updated_at": att.get("updated_at"),
                        "ticket_id": att.get("ticket_id"),
                        "conversation_id": att.get("conversation_id")
                    }
                    attachment_meta.append(meta)  # 실제로 리스트에 추가
            # Qdrant에 저장할 문서 구조 생성
            doc = {
                "id": doc_id,
                "text": t.get("description_text") or t.get("description") or "",
                "metadata": {
                    **t,
                    "attachments": attachment_meta
                }
            }
            all_documents.append(doc)

        logger.info("지식베이스 문서 처리 중...")
        for a in articles:
            doc_id = f"kb-{a.get('id')}"
            doc = {
                "id": doc_id,
                "text": a.get("description_text") or a.get("description") or "",
                "metadata": {**a}
            }
            all_documents.append(doc)

        # deleted_ids, all_documents 예외 처리 보완
        if not all_documents and deleted_ids:
            logger.info("신규 문서는 없으나 삭제된 문서가 존재합니다. 삭제만 진행합니다.")
            # 삭제 처리 로직이 있다면 여기에 추가
        elif not all_documents:
            logger.info("신규 문서가 없습니다. 작업을 종료합니다.")
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

        # Qdrant 저장 성공 여부 자동 검증
        logger.info("Qdrant 저장 성공 여부 검증 중...")
        try:
            collection_info = vector_db.get_collection_info()
            if "error" not in collection_info:
                points_count = collection_info.get("points_count", 0)
                logger.info(f"✅ Qdrant 컬렉션 '{collection_info['name']}'에 총 {points_count:,}개 포인트 저장 확인")
                logger.info(f"   벡터 크기: {collection_info['vector_size']}, 상태: {collection_info['status']}")
                
                # 저장된 데이터 수와 처리된 문서 수 비교 안내
                if points_count >= len(docs):
                    logger.info("✅ 저장 검증 성공: 모든 문서가 Qdrant에 정상 저장되었습니다.")
                else:
                    logger.warning(f"⚠️  저장 검증 주의: 처리된 문서 수({len(docs)})와 저장된 포인트 수({points_count})에 차이가 있습니다.")
            else:
                logger.error(f"❌ Qdrant 저장 검증 실패: {collection_info['error']}")
        except Exception as e:
            logger.error(f"❌ Qdrant 저장 검증 중 오류 발생: {e}")

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


def verify_database_integrity() -> bool:
    """
    데이터베이스 무결성을 검증합니다.
    이 함수는 Qdrant 벡터 데이터베이스의 상태를 확인하고
    기본적인 무결성 검사를 수행합니다.
    
    Returns:
        bool: 검증 성공 여부 (True: 정상, False: 오류 발견)
    """
    try:
        logger.info("데이터베이스 무결성 검증 시작...")
        
        # 1. 컬렉션 존재 확인
        if not vector_db.collection_exists():
            logger.error("데이터베이스 컬렉션이 존재하지 않습니다.")
            return False
        
        # 2. 문서 수 확인
        total_count = vector_db.count()
        logger.info(f"데이터베이스에 총 {total_count}개 문서가 있습니다.")
        
        if total_count == 0:
            logger.warning("데이터베이스에 문서가 없습니다. 초기 상태이거나 문제가 있을 수 있습니다.")
            # 빈 데이터베이스도 유효한 상태로 간주
            return True
        
        # 3. 검색 테스트 (간단한 쿼리로 응답 확인)
        DEFAULT_COMPANY_ID = "default"
        dummy_embedding = embed_documents(["database verification test"])[0]
        result = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=1,
            company_id=DEFAULT_COMPANY_ID
        )
        
        if not result or "ids" not in result or len(result["ids"]) == 0:
            logger.error("데이터베이스 검색 테스트 실패: 결과를 반환하지 않습니다.")
            return False
        
        logger.info("데이터베이스 무결성 검증 완료: 정상 작동 중")
        return True
        
    except Exception as e:
        logger.error(f"데이터베이스 무결성 검증 중 오류 발생: {e}", exc_info=True)
        return False


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
        parser.add_argument(
            "--local-data", type=str, help="로컬 데이터 디렉토리 경로 (이미 수집된 데이터 사용)"
        )
        parser.add_argument(
            "--drop-only",
            type=str,
            nargs="?",
            const="documents",
            help="Qdrant 컬렉션만 삭제하고 종료 (여러 컬렉션은 콤마로 구분, 예: documents,faqs)"
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

        # --drop-only 옵션 처리
        if args.drop_only:
            collections = [c.strip() for c in args.drop_only.split(",") if c.strip()]
            for col in collections:
                logger.info(f"Qdrant 컬렉션 삭제 시도: {col}")
                success = vector_db.drop_collection(collection_name=col)
                if success:
                    logger.info(f"Qdrant 컬렉션 삭제 완료: {col}")
                else:
                    logger.error(f"Qdrant 컬렉션 삭제 실패: {col}")
            logger.info("컬렉션 삭제만 수행하고 종료합니다.")
            sys.exit(0)

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

        if args.local_data:
            logger.info(f"로컬 데이터 모드: {args.local_data}")
        
        asyncio.run(
            ingest(
                incremental=incremental_mode,
                purge=purge_mode,
                process_attachments=process_attachments,
                force_rebuild=rebuild_mode,
                local_data_dir=args.local_data,
            )
        )
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로세스가 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        exit(1)
