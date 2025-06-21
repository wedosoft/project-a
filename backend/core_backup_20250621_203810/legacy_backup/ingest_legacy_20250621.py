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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.embedder import embed_documents, process_documents
from core.vectordb import vector_db
from core.database import SQLiteDatabase  # SQLite 데이터베이스 추가
from freshdesk.fetcher import (
    extract_company_id_from_domain,
    fetch_kb_articles,
    fetch_tickets,
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"  # Qdrant 컬렉션 이름

# FRESHDESK_DOMAIN에서 company_id 자동 추출
FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
if FRESHDESK_DOMAIN:
    DEFAULT_COMPANY_ID = extract_company_id_from_domain(FRESHDESK_DOMAIN)
    logger.debug(f"FRESHDESK_DOMAIN '{FRESHDESK_DOMAIN}'에서 추출된 company_id: '{DEFAULT_COMPANY_ID}'")
else:
    DEFAULT_COMPANY_ID = "default"
    logger.warning("FRESHDESK_DOMAIN 환경변수가 설정되지 않아 기본값 'default'를 사용합니다.")
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


def create_integrated_ticket_object(ticket: Dict[str, Any], conversations: Optional[List[Dict[str, Any]]] = None, attachments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    티켓, 대화내역, 첨부파일을 하나의 통합 객체로 생성합니다.
    
    Args:
        ticket: 티켓 데이터
        conversations: 대화내역 리스트 (옵션)
        attachments: 첨부파일 리스트 (옵션)
        
    Returns:
        Dict[str, Any]: 통합된 티켓 객체
    """
    # 기본 티켓 정보 복사
    integrated_object = ticket.copy()
    
    # 대화내역이 티켓에 포함되어 있는 경우 사용, 아니면 파라미터 사용
    if conversations is None:
        conversations = ticket.get("conversations", [])
    
    # 첨부파일이 티켓에 포함되어 있는 경우 사용, 아니면 파라미터 사용
    if attachments is None:
        attachments = ticket.get("all_attachments", [])
    
    # 통합 객체 구성
    integrated_object.update({
        "conversations": conversations,
        "all_attachments": attachments,
        "has_conversations": len(conversations) > 0,
        "has_attachments": len(attachments) > 0,
        "conversation_count": len(conversations),
        "attachment_count": len(attachments),
        "integration_timestamp": datetime.utcnow().isoformat(),
        "object_type": "integrated_ticket"
    })
    
    # 요약 생성을 위한 텍스트 통합
    text_parts = []
    
    # 티켓 제목과 설명
    if ticket.get("subject"):
        text_parts.append(f"제목: {ticket['subject']}")
    if ticket.get("description_text"):
        text_parts.append(f"설명: {ticket['description_text']}")
    elif ticket.get("description"):
        text_parts.append(f"설명: {ticket['description']}")
    
    # 대화내역 텍스트 추가
    for conv in conversations:
        if conv.get("body_text"):
            text_parts.append(f"대화: {conv['body_text']}")
        elif conv.get("body"):
            text_parts.append(f"대화: {conv['body']}")
    
    # 첨부파일 정보 추가
    if attachments:
        attachment_names = [att.get("name", "Unknown") for att in attachments]
        text_parts.append(f"첨부파일: {', '.join(attachment_names)}")
    
    integrated_object["integrated_text"] = "\n\n".join(text_parts)
    
    return integrated_object


def create_integrated_article_object(article: Dict[str, Any], attachments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    지식베이스 문서와 첨부파일을 하나의 통합 객체로 생성합니다.
    
    Args:
        article: 지식베이스 문서 데이터
        attachments: 첨부파일 리스트 (옵션)
        
    Returns:
        Dict[str, Any]: 통합된 문서 객체
    """
    # 기본 문서 정보 복사
    integrated_object = article.copy()
    
    # 첨부파일이 문서에 포함되어 있는 경우 사용, 아니면 파라미터 사용
    if attachments is None:
        attachments = article.get("attachments", [])
    
    # 통합 객체 구성
    integrated_object.update({
        "attachments": attachments,
        "has_attachments": len(attachments) > 0,
        "attachment_count": len(attachments),
        "integration_timestamp": datetime.utcnow().isoformat(),
        "object_type": "integrated_article"
    })
    
    # 요약 생성을 위한 텍스트 통합
    text_parts = []
    
    # 문서 제목과 내용
    if article.get("title"):
        text_parts.append(f"제목: {article['title']}")
    if article.get("description"):
        text_parts.append(f"설명: {article['description']}")
    
    # 첨부파일 정보 추가
    if attachments:
        attachment_names = [att.get("name", "Unknown") for att in attachments]
        text_parts.append(f"첨부파일: {', '.join(attachment_names)}")
    
    integrated_object["integrated_text"] = "\n\n".join(text_parts)
    
    return integrated_object


def store_integrated_object_to_sqlite(db: SQLiteDatabase, integrated_object: Dict[str, Any], company_id: str, platform: str = "freshdesk") -> bool:
    """
    통합 객체를 SQLite 데이터베이스에 저장합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        integrated_object: 통합 객체
        company_id: 회사 ID
        platform: 플랫폼명 (기본: freshdesk)
        
    Returns:
        bool: 저장 성공 여부
    """
    try:
        object_type = integrated_object.get("object_type", "unknown")
        
        # 1. integrated_objects 테이블에 저장
        integrated_data = {
            'object_id': integrated_object.get("id"),
            'company_id': company_id,
            'platform': platform,
            'object_type': object_type,
            'original_data': integrated_object,
            'integrated_content': integrated_object.get("full_conversation", ""),
            'summary': integrated_object.get("summary"),
            'metadata': {
                'has_conversations': integrated_object.get("has_conversations", False),
                'has_attachments': integrated_object.get("has_attachments", False),
                'conversation_count': len(integrated_object.get("conversations", [])),
                'attachment_count': len(integrated_object.get("all_attachments", []))
            }
        }
        
        db.insert_integrated_object(integrated_data)
        logger.info(f"통합 객체 저장 완료: ID={integrated_data['object_id']}, Type={object_type}")
        
        # 2. 기존 테이블에도 저장 (호환성 유지)
        if object_type == "integrated_ticket":
            # 티켓으로 저장 - database.py의 insert_ticket 함수 형식에 맞춤
            ticket_id = integrated_object.get("id")
            if not ticket_id:
                logger.error("티켓 ID가 없습니다.")
                return False
                
            # 통합 객체를 ticket_data 형식으로 변환
            ticket_data = integrated_object.copy()
            ticket_data.update({
                'company_id': company_id,
                'platform': platform
            })
                
            # insert_ticket은 딕셔너리를 받아서 raw_data에 저장
            result = db.insert_ticket(ticket_data)
            
            # 대화내역도 개별적으로 저장 (옵션)
            conversations = integrated_object.get("conversations", [])
            for conv in conversations:
                conversation_data = conv.copy()
                conversation_data.update({
                    'ticket_id': ticket_id,
                    'company_id': company_id,
                    'platform': platform
                })
                
                # insert_conversation은 딕셔너리를 받아서 raw_data에 저장
                db.insert_conversation(conversation_data)
            
            logger.info(f"통합 티켓 객체 저장 완료: ID={ticket_id}, 대화={len(conversations)}개")
            return True
            
        elif object_type == "integrated_article":
            # 지식베이스 문서로 저장 - database.py의 insert_article 함수 형식에 맞춤
            article_id = integrated_object.get("id")
            if not article_id:
                logger.error("문서 ID가 없습니다.")
                return False
                
            # 통합 객체를 article_data 형식으로 변환
            article_data = integrated_object.copy()
            article_data.update({
                'company_id': company_id,
                'platform': platform
            })
                
            # insert_article은 딕셔너리를 받아서 raw_data에 저장
            db.insert_article(article_data)
            
            logger.info(f"통합 문서 객체 저장 완료: ID={article_id}")
            return True
            
        else:
            logger.error(f"알 수 없는 객체 타입: {object_type}")
            return False
            
    except Exception as e:
        logger.error(f"통합 객체 저장 실패: {e}")
        return False


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
    로컬에 저장된 Freshdesk 데이터를 로드합니다.
    Enhanced Fetcher로 수집된 상세 데이터를 우선적으로 로드합니다.
    
    Args:
        data_dir: 데이터 디렉토리 경로
    
    Returns:
        tuple: (tickets, articles) - 티켓 리스트와 지식베이스 문서 리스트
    """
    data_path = Path(data_dir)
    tickets = []
    articles = []
    
    if not data_path.exists():
        logger.warning(f"데이터 디렉토리가 존재하지 않습니다: {data_dir}")
        return tickets, articles
    
    logger.info(f"로컬 데이터 로드 시작: {data_dir}")
    
    # 새로운 raw_data 구조 확인
    raw_data_dir = data_path / "raw_data"
    
    if raw_data_dir.exists():
        logger.info("새로운 raw_data 구조 감지됨, 청크 데이터 로드...")
        
        # 1. 티켓 데이터 로드 (raw_data/tickets/tickets_chunk_*.json)
        raw_tickets_dir = raw_data_dir / "tickets"
        if raw_tickets_dir.exists():
            ticket_files = sorted(raw_tickets_dir.glob("tickets_chunk_*.json"))
            if ticket_files:
                logger.info(f"{len(ticket_files)}개 티켓 청크 파일 로드 중...")
                for ticket_file in ticket_files:
                    try:
                        with open(ticket_file, 'r', encoding='utf-8') as f:
                            chunk_tickets = json.load(f)
                            tickets.extend(chunk_tickets)
                            logger.info(f"{ticket_file.name}: {len(chunk_tickets)}개 티켓 로드")
                    except Exception as e:
                        logger.error(f"티켓 파일 로드 실패 {ticket_file.name}: {e}")
                logger.info(f"티켓 데이터 로드 완료: 총 {len(tickets)}개")
            else:
                logger.info("티켓 청크 파일이 없음")
        
        # 2. 지식베이스 데이터 로드 (raw_data/knowledge_base/knowledge_base_chunk_*.json)
        raw_kb_dir = raw_data_dir / "knowledge_base"
        if raw_kb_dir.exists():
            kb_files = sorted(raw_kb_dir.glob("knowledge_base_chunk_*.json"))
            if kb_files:
                logger.info(f"{len(kb_files)}개 지식베이스 청크 파일 로드 중...")
                for kb_file in kb_files:
                    try:
                        with open(kb_file, 'r', encoding='utf-8') as f:
                            chunk_articles = json.load(f)
                            articles.extend(chunk_articles)
                            logger.info(f"{kb_file.name}: {len(chunk_articles)}개 지식베이스 문서 로드")
                    except Exception as e:
                        logger.error(f"지식베이스 파일 로드 실패 {kb_file.name}: {e}")
                logger.info(f"지식베이스 데이터 로드 완료: 총 {len(articles)}개")
            else:
                logger.info("지식베이스 청크 파일이 없음")
    
    else:
        # raw_data 구조가 없는 경우 오류 메시지 출력
        logger.error(f"지원되는 데이터 구조를 찾을 수 없습니다: {data_dir}")
        logger.error("필요한 구조: raw_data/")
        logger.error("  - raw_data/tickets/tickets_chunk_*.json")
        logger.error("  - raw_data/knowledge_base/knowledge_base_chunk_*.json")
        raise ValueError(f"지원되지 않는 데이터 구조: {data_dir}")
    
    logger.info(f"최종 로드 결과: 티켓 {len(tickets):,}개, 지식베이스 {len(articles):,}개")
    return tickets, articles


def save_checkpoint(data_dir: str, stage: str, data: Dict[str, Any]) -> None:
    """
    처리 진행 상황을 체크포인트로 저장합니다.
    임베딩이나 DB 저장 실패 시 재수집을 방지하기 위해 사용됩니다.
    
    Args:
        data_dir: 데이터 디렉토리 경로
        stage: 현재 처리 단계 ('data_loaded', 'embedded', 'stored')
        data: 저장할 데이터 (문서, 임베딩 등)
    """
    try:
        data_path = Path(data_dir)
        checkpoint_dir = data_path / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)  # parents=True 추가로 중첩 폴더 자동 생성
        
        checkpoint_file = checkpoint_dir / f"{stage}_checkpoint.json"
        
        # 체크포인트 메타데이터
        checkpoint_data = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "doc_count": len(data.get("docs", [])),
            "embedding_count": len(data.get("embeddings", [])),
            "metadata_count": len(data.get("metadatas", [])),
            "ids_count": len(data.get("ids", []))
        }
        
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        
        # 실제 데이터는 별도 파일에 저장 (큰 데이터는 피클 사용)
        if stage == "embedded":
            import pickle
            data_file = checkpoint_dir / f"{stage}_data.pkl"
            with open(data_file, 'wb') as f:
                pickle.dump(data, f)
        else:
            data_file = checkpoint_dir / f"{stage}_data.json"
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, default=str)
                
        logger.info(f"체크포인트 저장 완료: {stage} - {checkpoint_file}")
        
    except Exception as e:
        logger.warning(f"체크포인트 저장 실패 (계속 진행): {e}")


def load_checkpoint(data_dir: str, stage: str) -> Optional[Dict[str, Any]]:
    """
    저장된 체크포인트에서 데이터를 로드합니다.
    
    Args:
        data_dir: 데이터 디렉토리 경로
        stage: 로드할 처리 단계
        
    Returns:
        체크포인트 데이터 또는 None (존재하지 않는 경우)
    """
    try:
        data_path = Path(data_dir)
        checkpoint_dir = data_path / "checkpoints"
        
        checkpoint_file = checkpoint_dir / f"{stage}_checkpoint.json"
        if not checkpoint_file.exists():
            return None
            
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            checkpoint_meta = json.load(f)
        
        # 실제 데이터 로드
        if stage == "embedded":
            import pickle
            data_file = checkpoint_dir / f"{stage}_data.pkl"
            if data_file.exists():
                with open(data_file, 'rb') as f:
                    data = pickle.load(f)
        else:
            data_file = checkpoint_dir / f"{stage}_data.json"
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                return None
                
        logger.info(f"체크포인트 로드 완료: {stage} - {checkpoint_meta['doc_count']}개 문서")
        return data
        
    except Exception as e:
        logger.warning(f"체크포인트 로드 실패: {e}")
        return None


def clear_checkpoints(data_dir: str) -> None:
    """
    성공적으로 완료된 후 체크포인트 파일들을 정리합니다.
    """
    try:
        data_path = Path(data_dir)
        checkpoint_dir = data_path / "checkpoints"
        
        if checkpoint_dir.exists():
            import shutil
            shutil.rmtree(checkpoint_dir)
            logger.info("체크포인트 디렉토리 정리 완료")
            
    except Exception as e:
        logger.warning(f"체크포인트 정리 실패 (무시): {e}")


async def ingest(
    incremental: bool = True,
    purge: bool = False,
    process_attachments: bool = PROCESS_ATTACHMENTS,
    force_rebuild: bool = False,
    local_data_dir: Optional[str] = None,
    include_kb: bool = True,
    domain: Optional[str] = None,
    api_key: Optional[str] = None,
    max_tickets: Optional[int] = None,
    max_articles: Optional[int] = None,
) -> None:
    """
    Freshdesk 티켓과 지식베이스 문서를 임베딩 후 Qdrant에 저장합니다.
    Args:
        incremental: 증분 업데이트 모드 여부 (기본값: True)
        purge: 기존 데이터 삭제 여부 (기본값: False)
        process_attachments: 첨부파일 처리 여부 (기본값: True)
        force_rebuild: 데이터베이스 강제 재구축 여부 (기본값: False)
        local_data_dir: 로컬 데이터 디렉토리 경로 (None이면 Freshdesk API에서 직접 수집)
        include_kb: 지식베이스 데이터 포함 여부 (기본값: True)
        domain: Freshdesk 도메인 (None이면 환경변수 사용)
        api_key: Freshdesk API 키 (None이면 환경변수 사용)
        max_tickets: 최대 수집 티켓 수 (None이면 무제한, 기본값: None)
        max_articles: 최대 수집 KB 문서 수 (None이면 무제한, 기본값: None)
    """
    start_time = time.time()
    
    # FRESHDESK_DOMAIN에서 company_id 자동 추출
    FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
    if FRESHDESK_DOMAIN:
        DEFAULT_COMPANY_ID = extract_company_id_from_domain(FRESHDESK_DOMAIN)
        logger.debug(f"ingest: FRESHDESK_DOMAIN '{FRESHDESK_DOMAIN}'에서 추출된 company_id: '{DEFAULT_COMPANY_ID}'")
    else:
        DEFAULT_COMPANY_ID = "default"
        logger.warning("ingest: FRESHDESK_DOMAIN 환경변수가 설정되지 않아 기본값 'default'를 사용합니다.")
    
    logger.info("데이터 수집 프로세스 시작")
    start_time = time.time()

    try:
        # Qdrant 클라우드만 사용하므로, 로컬 DB 백업/무결성 검사 등은 제거됨
        if force_rebuild:
            logger.warning("데이터베이스 강제 재구축 모드 (Qdrant 클라우드 환경)")
            incremental = False
            purge = True
        
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
            
            # 체크포인트 확인 - 이미 임베딩이 완료된 데이터가 있는지 확인
            # 단, force_rebuild가 아닌 경우에만 체크포인트 복구 시도
            embedded_checkpoint = load_checkpoint(local_data_dir, "embedded")
            if embedded_checkpoint and not force_rebuild:
                # 체크포인트 복구 시도 전 사용자 확인 (자동 재수집 방지)
                logger.warning("⚠️  기존 임베딩 작업이 중단된 상태입니다.")
                logger.info("체크포인트에서 작업을 재개하려면 force_rebuild=False 상태에서만 가능합니다.")
                
                # 자동 재수집 방지: 명시적 재개 요청이 있을 때만 실행
                if not incremental:  # 전체 재수집 모드에서는 체크포인트 무시
                    logger.info("전체 재수집 모드: 기존 체크포인트를 무시하고 새로 시작합니다.")
                    clear_checkpoints(local_data_dir)
                else:
                    logger.info("임베딩 완료된 체크포인트 발견됨, 벡터 DB 저장 단계부터 재개...")
                    docs = embedded_checkpoint["docs"]
                    all_embeddings = embedded_checkpoint["embeddings"]
                    metadatas = embedded_checkpoint["metadatas"]
                    ids = embedded_checkpoint["ids"]
                    
                    # 벡터 DB 저장으로 바로 이동
                    logger.info("Qdrant 벡터 DB에 문서 저장 중...")
                    batch_size = 50
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
                    
                    # 성공적으로 완료되면 체크포인트 정리
                    clear_checkpoints(local_data_dir)
                    logger.info("✅ 체크포인트에서 벡터 DB 저장 완료")
                    return
            
            # 체크포인트가 없거나 force_rebuild인 경우 일반 로드
            tickets, articles = load_local_data(local_data_dir)
            
            # 지식베이스 문서 포함 여부에 따라 처리
            if not include_kb:
                logger.info("include_kb=False 설정으로 지식베이스 문서는 제외됩니다.")
                articles = []
            
            # 데이터 로드 체크포인트 저장
            checkpoint_data = {
                "tickets": tickets,
                "articles": articles,
                "docs": [],
                "embeddings": [],
                "metadatas": [],
                "ids": []
            }
            save_checkpoint(local_data_dir, "data_loaded", checkpoint_data)
            
        else:
            # 기존 방식: Freshdesk API에서 직접 수집
            logger.info("Freshdesk 데이터 수집 중...")
            # 동적 Freshdesk 설정을 fetch 함수들에 전달
            tickets_task = asyncio.create_task(fetch_tickets(domain=domain, api_key=api_key, max_tickets=max_tickets or 10000))
            articles_task = asyncio.create_task(fetch_kb_articles(domain=domain, api_key=api_key, max_articles=max_articles))
            tickets, articles = await asyncio.gather(tickets_task, articles_task)

        if not tickets and not articles:
            logger.warning("Freshdesk에서 가져온 데이터가 없습니다.")
            return

        # SQLite에 원본 데이터 저장
        logger.info("SQLite 데이터베이스에 원본 데이터 저장 중...")
        job_id = f"ingest_{int(time.time())}"
        try:
            # 테스트용 데이터베이스 사용 (100건 제한)
            db = SQLiteDatabase("freshdesk_test_data.db")
            db.connect()
            db.create_tables()
            
            # 수집 작업 시작 로그
            job_start_data = {
                'job_id': job_id,
                'company_id': DEFAULT_COMPANY_ID,
                'job_type': 'ingest',
                'status': 'started',
                'start_time': datetime.now().isoformat(),
                'config': {
                    'incremental': incremental,
                    'purge': purge,
                    'include_kb': include_kb,
                    'tickets_count': len(tickets),
                    'articles_count': len(articles)
                }
            }
            db.log_collection_job(job_start_data)
            
            # 티켓 데이터를 통합 객체로 변환하여 저장
            tickets_saved = 0
            for ticket in tickets:
                try:
                    # 통합 객체 생성 (티켓 + 대화 + 첨부파일)
                    integrated_ticket = create_integrated_ticket_object(
                        ticket=ticket,
                        conversations=ticket.get("conversations", []),
                        attachments=ticket.get("all_attachments", [])
                    )
                    
                    # 통합 객체를 SQLite에 저장
                    success = store_integrated_object_to_sqlite(
                        db=db, 
                        integrated_object=integrated_ticket, 
                        company_id=DEFAULT_COMPANY_ID, 
                        platform='freshdesk'
                    )
                    
                    if success:
                        tickets_saved += 1
                        if tickets_saved % 10 == 0:
                            logger.info(f"📊 통합 티켓 객체 저장 진행상황: {tickets_saved}/{len(tickets)}")
                except Exception as e:
                    logger.error(f"통합 티켓 객체 저장 실패 (ID: {ticket.get('id')}): {e}")
            
            # 지식베이스 문서를 통합 객체로 변환하여 저장
            articles_saved = 0
            for article in articles:
                try:
                    # 통합 객체 생성 (문서 + 첨부파일)
                    integrated_article = create_integrated_article_object(
                        article=article,
                        attachments=article.get("attachments", [])
                    )
                    
                    # 통합 객체를 SQLite에 저장
                    success = store_integrated_object_to_sqlite(
                        db=db, 
                        integrated_object=integrated_article, 
                        company_id=DEFAULT_COMPANY_ID, 
                        platform='freshdesk'
                    )
                    
                    if success:
                        articles_saved += 1
                        if articles_saved % 10 == 0:
                            logger.info(f"📊 통합 문서 객체 저장 진행상황: {articles_saved}/{len(articles)}")
                except Exception as e:
                    logger.error(f"통합 문서 객체 저장 실패 (ID: {article.get('id')}): {e}")
            
            # 수집 작업 완료 로그
            job_end_data = {
                'job_id': job_id,
                'company_id': DEFAULT_COMPANY_ID,
                'job_type': 'ingest',
                'status': 'completed',
                'start_time': job_start_data['start_time'],
                'end_time': datetime.now().isoformat(),
                'tickets_collected': tickets_saved,
                'articles_collected': articles_saved,
                'errors_count': 0
            }
            db.log_collection_job(job_end_data)
            
            logger.info(f"✅ SQLite 저장 완료: 티켓 {tickets_saved}개, 지식베이스 문서 {articles_saved}개")
            logger.info(f"📈 수집 통계: {db.get_collection_stats(DEFAULT_COMPANY_ID)}")
            db.disconnect()
            
        except Exception as e:
            logger.error(f"SQLite 저장 중 오류 발생: {e}")
            # 실패 로그 기록
            try:
                job_error_data = {
                    'job_id': job_id,
                    'company_id': DEFAULT_COMPANY_ID,
                    'job_type': 'ingest',
                    'status': 'failed',
                    'start_time': job_start_data.get('start_time', datetime.now().isoformat()),
                    'end_time': datetime.now().isoformat(),
                    'errors_count': 1,
                    'error_message': str(e)
                }
                db.log_collection_job(job_error_data)
                db.disconnect()
            except:
                pass  # 오류 로그 기록 실패는 무시
            # SQLite 저장 실패해도 벡터 DB 저장은 계속 진행

        # 2. 삭제된 문서 감지 및 처리 (증분 업데이트 모드에서만)
        if incremental:
            # 회사 문서 수 확인 (상세 ID 목록은 Qdrant에서는 직접 조회가 어려움)
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
                original_id = str(t.get('id'))
                base_id = f"ticket-{original_id}"
                current_ids.add(base_id)

                # 기존에 청킹된 문서도 고려
                for existing_id in existing_ids:
                    if existing_id.startswith(f"{base_id}_chunk_"):
                        current_ids.add(existing_id)

            for a in articles:
                # 지식베이스 ID와 청크 ID 모두 포함
                original_id = str(a.get('id'))
                base_id = f"kb-{original_id}"
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
            dummy_embedding = embed_documents(["get all documents"])[0]
            result = vector_db.search(
                query_embedding=dummy_embedding,
                top_k=1000,  # 최대 1000개까지만 검색
                company_id=DEFAULT_COMPANY_ID
            )
            existing_ids = set(result.get("ids", []))
            existing_count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
            logger.info(f"현재 문서 {existing_count}개 확인됨 (삭제 처리 후, 최대 1000개 ID 샘플링)")

        logger.info("티켓 데이터를 통합 객체로 처리 중...")
        for t in tickets:
            # ID 체계 개선: ID 생성 방식 수정
            original_id = str(t.get('id'))  # 원본 ID를 문자열로 변환
            doc_id = f"ticket-{original_id}"  # Qdrant 포인트 ID 생성용 (접두어 포함)
            ticket_id = t.get("id")
            updated_at = t.get("updated_at")
            
            # 증분 업데이트 모드에서 기존 문서가 있으면 건너뜀
            if incremental:
                if doc_id in existing_ids:
                    continue
                    
            # description, description_text 등 주요 필드 보완
            if not t.get("description") or not t.get("description_text"):
                from freshdesk.fetcher import fetch_ticket_details
                if ticket_id:  # ticket_id가 None이 아닌 경우에만 호출
                    detail = await fetch_ticket_details(ticket_id, domain=domain, api_key=api_key)
                    if detail:
                        t.update({k: v for k, v in detail.items() if k not in t or not t[k]})
            
            # 통합 객체 생성 (티켓 + 대화 + 첨부파일)
            integrated_ticket = create_integrated_ticket_object(
                ticket=t,
                conversations=t.get("conversations", []),
                attachments=t.get("all_attachments", [])
            )
                    
            # 첨부파일(이미지 등) 메타데이터만 저장
            attachments = integrated_ticket.get("all_attachments", [])
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
                    
            # Qdrant에 저장할 문서 구조 생성 - 통합 텍스트 사용
            doc = {
                "id": doc_id,  # 내부 처리용 ID (접두어 포함)
                "text": integrated_ticket.get("integrated_text", ""),  # 통합 텍스트 사용
                "metadata": {
                    **integrated_ticket,
                    "original_id": original_id,  # 원본 ID를 문자열로 저장 (접두어 없음)
                    "doc_type": "ticket",  # 문서 타입 명시적 저장
                    "attachments": attachment_meta
                }
            }
            all_documents.append(doc)

        logger.info("지식베이스 문서를 통합 객체로 처리 중...")
        for a in articles:
            # ID 체계 개선: ID 생성 방식 수정
            original_id = str(a.get('id'))  # 원본 ID를 문자열로 변환
            doc_id = f"kb-{original_id}"  # Qdrant 포인트 ID 생성용 (접두어 포함)
            
            # 통합 객체 생성 (문서 + 첨부파일)
            integrated_article = create_integrated_article_object(
                article=a,
                attachments=a.get("attachments", [])
            )
            
            doc = {
                "id": doc_id,  # 내부 처리용 ID (접두어 포함)
                "text": integrated_article.get("integrated_text", ""),  # 통합 텍스트 사용
                "metadata": {
                    **integrated_article,
                    "original_id": original_id,  # 원본 ID를 문자열로 저장 (접두어 없음)
                    "doc_type": "kb"  # 문서 타입 명시적 저장
                }
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
        
        # 모든 메타데이터에 company_id와 platform 추가 및 ID 체계 확인 (FRESHDESK_DOMAIN에서 추출된 company_id 사용)
        for metadata, id_val in zip(metadatas, ids):
            metadata["company_id"] = DEFAULT_COMPANY_ID
            metadata["platform"] = "freshdesk"  # 현재는 Freshdesk만 지원
            # ID 체계 표준화: 모든 메타데이터에 original_id와 doc_type이 올바르게 설정되었는지 확인
            if "original_id" not in metadata:
                if "id" in metadata and isinstance(metadata["id"], str):
                    if metadata["id"].startswith("ticket-"):
                        metadata["original_id"] = metadata["id"][7:]
                        metadata["doc_type"] = "ticket"
                    elif metadata["id"].startswith("kb-"):
                        metadata["original_id"] = metadata["id"][3:]
                        metadata["doc_type"] = "kb"
                    else:
                        metadata["original_id"] = str(metadata["id"])
            # doc_type 필드 확인 및 보정
            if "doc_type" not in metadata or not metadata["doc_type"]:
                if isinstance(id_val, str):
                    if id_val.startswith("ticket-"):
                        metadata["doc_type"] = "ticket"
                    elif id_val.startswith("kb-"):
                        metadata["doc_type"] = "kb"
            if "doc_type" not in metadata or not metadata["doc_type"]:
                raise ValueError(f"add_documents 호출 전 metadata에 doc_type이 없습니다. id={id_val}, metadata={metadata}")

        # 6. 임베딩
        logger.info(f"총 {len(docs)}개 문서 임베딩 시작...")

        try:
            # 대량의 문서를 적절한 크기로 나누어 임베딩 - 메모리 효율성 향상
            batch_size = 50
            all_embeddings = []

            for i in range(0, len(docs), batch_size):
                batch_docs = docs[i : i + batch_size]
                logger.info(
                    f"문서 배치 임베딩 중... ({i+1}~{i+len(batch_docs)}/{len(docs)})"
                )
                try:
                    batch_embeddings = embed_documents(batch_docs)
                    all_embeddings.extend(batch_embeddings)
                except Exception as e:
                    logger.error(f"임베딩 배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                    # 실패한 배치에 대해 개별 문서 처리 시도
                    for j, doc in enumerate(batch_docs):
                        try:
                            single_embedding = embed_documents([doc])
                            all_embeddings.extend(single_embedding)
                            logger.info(f"개별 문서 임베딩 성공: {i+j+1}/{len(docs)}")
                        except Exception as doc_e:
                            logger.error(f"개별 문서 임베딩 실패 (문서 {i+j+1}): {doc_e}")
                            # 빈 임베딩으로 대체하여 인덱스 일치 유지
                            dummy_embedding = [0.0] * 1536  # text-embedding-3-small 차원
                            all_embeddings.append(dummy_embedding)
                            
            # 임베딩 완료 체크포인트 저장 (로컬 데이터인 경우만)
            if local_data_dir:
                checkpoint_data = {
                    "docs": docs,
                    "embeddings": all_embeddings,
                    "metadatas": metadatas,
                    "ids": ids
                }
                save_checkpoint(local_data_dir, "embedded", checkpoint_data)
                logger.info("임베딩 완료 체크포인트 저장됨")
                
        except Exception as e:
            logger.error(f"임베딩 처리 중 치명적 오류 발생: {e}")
            # 로컬 데이터인 경우 부분 체크포인트라도 저장 시도
            if local_data_dir and 'all_embeddings' in locals() and all_embeddings:
                try:
                    partial_checkpoint = {
                        "docs": docs[:len(all_embeddings)],
                        "embeddings": all_embeddings,
                        "metadatas": metadatas[:len(all_embeddings)],
                        "ids": ids[:len(all_embeddings)]
                    }
                    save_checkpoint(local_data_dir, "partial_embedded", partial_checkpoint)
                    logger.info(f"부분 임베딩 체크포인트 저장됨: {len(all_embeddings)}개 문서")
                except Exception as cp_e:
                    logger.warning(f"부분 체크포인트 저장 실패: {cp_e}")
            raise

        # 7. Qdrant 저장
        logger.info("Qdrant 벡터 DB에 문서 저장 중...")

        try:
            # 배치 단위로 upsert 수행 - 메모리 효율성 향상
            successful_batches = 0
            failed_batches = []
            
            for i in range(0, len(docs), batch_size):
                end_idx = min(i + batch_size, len(docs))
                batch_docs = docs[i:end_idx]
                batch_embeddings = all_embeddings[i:end_idx]
                batch_metadatas = metadatas[i:end_idx]
                batch_ids = ids[i:end_idx]

                logger.info(f"문서 배치 저장 중... ({i+1}~{end_idx}/{len(docs)})")
                
                # 배치 저장 시도 (재시도 포함)
                max_retries = 3
                retry_count = 0
                batch_success = False
                
                while retry_count < max_retries and not batch_success:
                    try:
                        vector_db.add_documents(
                            texts=batch_docs,
                            embeddings=batch_embeddings,
                            metadatas=batch_metadatas,
                            ids=batch_ids,
                        )
                        successful_batches += 1
                        batch_success = True
                        
                    except Exception as batch_e:
                        retry_count += 1
                        logger.warning(f"배치 저장 실패 (시도 {retry_count}/{max_retries}): {batch_e}")
                        
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)  # 지수 백오프
                        else:
                            # 최종 실패 시 개별 문서 저장 시도
                            logger.error(f"배치 저장 최종 실패, 개별 문서 저장 시도: 배치 {i//batch_size + 1}")
                            failed_batches.append((i, end_idx, batch_docs, batch_embeddings, batch_metadatas, batch_ids))
                            
                            # 개별 문서 저장 시도
                            for j in range(len(batch_docs)):
                                try:
                                    vector_db.add_documents(
                                        texts=[batch_docs[j]],
                                        embeddings=[batch_embeddings[j]],
                                        metadatas=[batch_metadatas[j]],
                                        ids=[batch_ids[j]],
                                    )
                                    logger.info(f"개별 문서 저장 성공: {i+j+1}/{len(docs)}")
                                except Exception as doc_e:
                                    logger.error(f"개별 문서 저장 실패 (문서 {i+j+1}): {doc_e}")
            
            if failed_batches:
                logger.warning(f"실패한 배치: {len(failed_batches)}개")
                # 실패한 배치 정보를 체크포인트로 저장 (수동 복구용)
                if local_data_dir:
                    failed_data = {
                        "failed_batches": failed_batches,
                        "timestamp": datetime.now().isoformat()
                    }
                    save_checkpoint(local_data_dir, "failed_storage", failed_data)
                    
            logger.info(f"벡터 DB 저장 완료: 성공 배치 {successful_batches}개")
            
        except Exception as e:
            logger.error(f"벡터 DB 저장 중 치명적 오류 발생: {e}")
            raise

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
                    
                    # 성공적으로 완료되면 체크포인트 정리
                    if local_data_dir:
                        clear_checkpoints(local_data_dir)
                        logger.info("체크포인트 정리 완료")
                        
                else:
                    logger.warning(f"⚠️  저장 검증 주의: 처리된 문서 수({len(docs)})와 저장된 포인트 수({points_count})에 차이가 있습니다.")
                    # 부분 성공인 경우 체크포인트는 유지 (수동 복구 가능)
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
        
        # include_kb 매개변수 추가
        asyncio.run(
            ingest(
                incremental=incremental_mode,
                purge=purge_mode,
                process_attachments=process_attachments,
                force_rebuild=rebuild_mode,
                local_data_dir=args.local_data,
                include_kb=True,  # 기본적으로 지식베이스 데이터 포함
            )
        )
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로세스가 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        exit(1)

def extract_integrated_text_for_summary(integrated_object: Dict[str, Any], max_length: int = 5000) -> str:
    """
    통합 객체에서 요약에 적합한 텍스트를 추출합니다.
    
    Args:
        integrated_object: 통합 객체 (티켓 또는 문서)
        max_length: 최대 텍스트 길이
        
    Returns:
        str: 요약용 텍스트
    """
    text_parts = []
    
    object_type = integrated_object.get("object_type", "unknown")
    
    if object_type == "integrated_ticket":
        # 티켓 제목과 설명
        if integrated_object.get("subject"):
            text_parts.append(f"티켓 제목: {integrated_object['subject']}")
        
        if integrated_object.get("description_text"):
            text_parts.append(f"티켓 설명: {integrated_object['description_text']}")
        elif integrated_object.get("description"):
            text_parts.append(f"티켓 설명: {integrated_object['description']}")
        
        # 중요한 대화만 선별 (길이 제한)
        conversations = integrated_object.get("conversations", [])
        important_conversations = []
        
        for conv in conversations[:5]:  # 최대 5개의 대화만 포함
            if conv.get("body_text"):
                if len(conv["body_text"]) > 50:  # 의미있는 길이의 대화만
                    important_conversations.append(conv["body_text"][:200])  # 200자로 제한
            elif conv.get("body"):
                if len(conv["body"]) > 50:
                    important_conversations.append(conv["body"][:200])
        
        if important_conversations:
            text_parts.append(f"주요 대화: {' | '.join(important_conversations)}")
            
        # 첨부파일 정보
        attachments = integrated_object.get("all_attachments", [])
        if attachments:
            attachment_names = [att.get("name", "Unknown") for att in attachments[:3]]  # 최대 3개만
            text_parts.append(f"첨부파일: {', '.join(attachment_names)}")
    
    elif object_type == "integrated_article":
        # 문서 제목과 설명
        if integrated_object.get("title"):
            text_parts.append(f"문서 제목: {integrated_object['title']}")
        
        if integrated_object.get("description"):
            text_parts.append(f"문서 내용: {integrated_object['description']}")
        
        # 첨부파일 정보
        attachments = integrated_object.get("attachments", [])
        if attachments:
            attachment_names = [att.get("name", "Unknown") for att in attachments[:3]]
            text_parts.append(f"첨부파일: {', '.join(attachment_names)}")
    
    # 텍스트 결합 및 길이 제한
    full_text = "\n\n".join(text_parts)
    
    if len(full_text) > max_length:
        full_text = full_text[:max_length] + "..."
    
    return full_text


def extract_integrated_text_for_embedding(integrated_object: Dict[str, Any]) -> str:
    """
    통합 객체에서 임베딩에 적합한 텍스트를 추출합니다.
    
    Args:
        integrated_object: 통합 객체
        
    Returns:
        str: 임베딩용 텍스트
    """
    # integrated_text가 이미 생성되어 있으면 그것을 사용
    if integrated_object.get("integrated_text"):
        return integrated_object["integrated_text"]
    
    # 아니면 직접 생성
    text_parts = []
    object_type = integrated_object.get("object_type", "unknown")
    
    if object_type == "integrated_ticket":
        if integrated_object.get("subject"):
            text_parts.append(integrated_object["subject"])
        if integrated_object.get("description_text") or integrated_object.get("description"):
            text_parts.append(integrated_object.get("description_text") or integrated_object.get("description"))
        
        # 모든 대화 포함
        conversations = integrated_object.get("conversations", [])
        for conv in conversations:
            if conv.get("body_text"):
                text_parts.append(conv["body_text"])
            elif conv.get("body"):
                text_parts.append(conv["body"])
    
    elif object_type == "integrated_article":
        if integrated_object.get("title"):
            text_parts.append(integrated_object["title"])
        if integrated_object.get("description"):
            text_parts.append(integrated_object["description"])
    
    return " ".join(text_parts)


def get_integrated_object_from_sqlite(db: SQLiteDatabase, doc_type: str, object_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """
    SQLite에서 통합 객체를 조회합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        doc_type: 문서 타입 ('ticket' 또는 'kb')
        object_id: 객체 ID
        company_id: 회사 ID
        
    Returns:
        Optional[Dict[str, Any]]: 통합 객체 또는 None
    """
    try:
        if doc_type == "ticket":
            # 티켓 조회
            result = db.get_ticket(ticket_id=object_id, company_id=company_id)
            if result and result.get("raw_data"):
                integrated_object = json.loads(result["raw_data"])
                return integrated_object
        elif doc_type == "kb":
            # 지식베이스 문서 조회
            result = db.get_article(article_id=object_id, company_id=company_id)
            if result and result.get("raw_data"):
                integrated_object = json.loads(result["raw_data"])
                return integrated_object
        
        return None
    except Exception as e:
        logger.error(f"통합 객체 조회 실패: {e}")
        return None


def search_integrated_objects_from_sqlite(db: SQLiteDatabase, query: str, company_id: str, doc_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    SQLite에서 통합 객체를 검색합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        query: 검색 쿼리
        company_id: 회사 ID
        doc_type: 문서 타입 필터 ('ticket', 'kb', 또는 None)
        limit: 결과 개수 제한
        
    Returns:
        List[Dict[str, Any]]: 검색된 통합 객체 목록
    """
    try:
        results = []
        
        if doc_type is None or doc_type == "ticket":
            # 티켓 검색
            ticket_results = db.search_tickets(query=query, company_id=company_id, limit=limit)
            for result in ticket_results:
                if result.get("raw_data"):
                    try:
                        integrated_object = json.loads(result["raw_data"])
                        integrated_object["search_score"] = result.get("score", 0)
                        results.append(integrated_object)
                    except json.JSONDecodeError:
                        continue
        
        if doc_type is None or doc_type == "kb":
            # 지식베이스 검색
            article_results = db.search_articles(query=query, company_id=company_id, limit=limit)
            for result in article_results:
                if result.get("raw_data"):
                    try:
                        integrated_object = json.loads(result["raw_data"])
                        integrated_object["search_score"] = result.get("score", 0)
                        results.append(integrated_object)
                    except json.JSONDecodeError:
                        continue
        
        # 점수 기준 정렬
        results.sort(key=lambda x: x.get("search_score", 0), reverse=True)
        return results[:limit]
        
    except Exception as e:
        logger.error(f"통합 객체 검색 실패: {e}")
        return []


# 기존의 sanitize_metadata 함수 유지...
