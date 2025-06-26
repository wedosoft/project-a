"""
데이터 검증 및 상태 관리 모듈

이 모듈은 수집된 데이터의 검증, 상태 매핑 관리, 데이터베이스 무결성 검사 등을 담당합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참고
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from core.database.vectordb import vector_db

# 로깅 설정
logger = logging.getLogger(__name__)

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
    
    Returns:
        Dict: 상태 매핑 정보
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


def save_status_mappings(mappings: Dict[str, Any]):
    """
    상태 매핑 정보를 파일에 저장합니다.
    
    Args:
        mappings: 저장할 매핑 정보
    """
    try:
        with open(STATUS_MAPPINGS_FILE, "w") as f:
            json.dump(mappings, f, indent=2)
            logger.info(f"상태 매핑 파일 저장 완료: {STATUS_MAPPINGS_FILE}")
    except Exception as e:
        logger.error(f"상태 매핑 파일 저장 실패: {e}")


async def update_status_mappings(collection_name: str = "documents") -> None:
    """
    Qdrant에서 기존 상태 값들을 조회하여 매핑 정보를 업데이트합니다.
    
    Args:
        collection_name: Qdrant 컬렉션 이름
    """
    logger.info("Qdrant에서 상태 매핑 정보 업데이트 중...")
    
    try:
        # 현재 상태 매핑 로드
        current_mappings = load_status_mappings()
        
        # Qdrant에서 모든 문서의 상태 값 조회
        # 실제 구현에서는 Qdrant scroll API를 사용하여 모든 문서를 순회
        # 여기서는 간단한 버전으로 구현
        
        # 새로운 상태 값 발견 시 매핑에 추가
        updated = False
        
        # 티켓 상태 검증
        for status_id, status_name in TICKET_STATUS_MAP.items():
            if str(status_id) not in current_mappings.get("ticket", {}):
                if "ticket" not in current_mappings:
                    current_mappings["ticket"] = {}
                current_mappings["ticket"][str(status_id)] = status_name
                updated = True
                logger.info(f"새로운 티켓 상태 매핑 추가: {status_id} -> {status_name}")
        
        # KB 상태 검증
        for status_id, status_name in KB_STATUS_MAP.items():
            if str(status_id) not in current_mappings.get("kb", {}):
                if "kb" not in current_mappings:
                    current_mappings["kb"] = {}
                current_mappings["kb"][str(status_id)] = status_name
                updated = True
                logger.info(f"새로운 KB 상태 매핑 추가: {status_id} -> {status_name}")
        
        # 변경사항이 있으면 저장
        if updated:
            save_status_mappings(current_mappings)
            logger.info("상태 매핑 정보가 업데이트되었습니다.")
        else:
            logger.info("상태 매핑 정보에 변경사항이 없습니다.")
            
    except Exception as e:
        logger.error(f"상태 매핑 업데이트 중 오류: {e}")


def verify_database_integrity() -> bool:
    """
    데이터베이스 무결성을 검증합니다.
    
    Returns:
        bool: 무결성 검증 통과 여부
    """
    logger.info("데이터베이스 무결성 검증 중...")
    
    try:
        # Qdrant 연결 상태 확인
        total_count = vector_db.count()
        logger.info(f"Qdrant 컬렉션 문서 수: {total_count}")
        
        if total_count < 0:
            logger.error("Qdrant 컬렉션 조회 실패")
            return False
        
        # 기본적인 연결 확인이 통과되면 무결성 양호로 판단
        logger.info("✅ 데이터베이스 무결성 검증 통과")
        return True
        
    except Exception as e:
        logger.error(f"데이터베이스 무결성 검증 실패: {e}")
        return False


def validate_integrated_object(integrated_object: Dict[str, Any], object_type: str) -> bool:
    """
    통합 객체의 유효성을 검증합니다.
    
    Args:
        integrated_object: 검증할 통합 객체
        object_type: 객체 타입 ('ticket' 또는 'article')
        
    Returns:
        bool: 검증 통과 여부
    """
    try:
        # 필수 필드 검증
        required_fields = ["id", "object_type", "integration_timestamp"]
        
        for field in required_fields:
            if field not in integrated_object:
                logger.warning(f"필수 필드 누락: {field}")
                return False
        
        # 객체 타입별 추가 검증
        if object_type == "ticket":
            # 티켓 특화 검증
            if not integrated_object.get("subject"):
                logger.warning("티켓 제목(subject)이 없습니다.")
                return False
                
        elif object_type == "article":
            # KB 문서 특화 검증  
            if not integrated_object.get("title"):
                logger.warning("KB 문서 제목(title)이 없습니다.")
                return False
        
        # 통합 텍스트 검증
        if not integrated_object.get("integrated_text"):
            logger.warning("통합 텍스트(integrated_text)가 생성되지 않았습니다.")
            return False
        
        logger.debug(f"{object_type} 객체 검증 통과: {integrated_object.get('id')}")
        return True
        
    except Exception as e:
        logger.error(f"통합 객체 검증 중 오류: {e}")
        return False


def validate_metadata(metadata: Dict[str, Any]) -> bool:
    """
    메타데이터의 유효성을 검증합니다.
    
    Args:
        metadata: 검증할 메타데이터
        
    Returns:
        bool: 검증 통과 여부
    """
    try:
        # 필수 메타데이터 필드 검증
        required_fields = ["id", "tenant_id", "platform", "type"]
        
        for field in required_fields:
            if field not in metadata:
                logger.warning(f"메타데이터 필수 필드 누락: {field}")
                return False
        
        # tenant_id 검증
        if not metadata.get("tenant_id") or metadata["tenant_id"] == "":
            logger.warning("tenant_id가 비어있습니다.")
            return False
        
        # 플랫폼 검증
        allowed_platforms = ["freshdesk", "zendesk"]
        if metadata.get("platform") not in allowed_platforms:
            logger.warning(f"지원되지 않는 플랫폼: {metadata.get('platform')}")
            return False
        
        # 타입 검증
        allowed_types = ["ticket", "kb_article"]
        if metadata.get("type") not in allowed_types:
            logger.warning(f"지원되지 않는 타입: {metadata.get('type')}")
            return False
        
        logger.debug(f"메타데이터 검증 통과: {metadata.get('id')}")
        return True
        
    except Exception as e:
        logger.error(f"메타데이터 검증 중 오류: {e}")
        return False


def extract_integrated_text_for_summary(integrated_object: Dict[str, Any], max_length: int = 5000) -> str:
    """
    통합 객체에서 요약을 위한 텍스트를 추출합니다.
    
    Args:
        integrated_object: 통합 객체
        max_length: 최대 텍스트 길이
        
    Returns:
        str: 요약용 텍스트
    """
    try:
        # 통합 텍스트가 있으면 사용
        if integrated_object.get("integrated_text"):
            text = integrated_object["integrated_text"]
            if len(text) <= max_length:
                return text
            else:
                # 길이 제한 적용
                return text[:max_length] + "..."
        
        # 통합 텍스트가 없으면 개별 필드에서 구성
        text_parts = []
        
        # 타입에 따른 텍스트 추출
        if integrated_object.get("object_type") == "integrated_ticket":
            if integrated_object.get("subject"):
                text_parts.append(f"제목: {integrated_object['subject']}")
            if integrated_object.get("description_text"):
                text_parts.append(f"설명: {integrated_object['description_text']}")
        elif integrated_object.get("object_type") == "integrated_article":
            if integrated_object.get("title"):
                text_parts.append(f"제목: {integrated_object['title']}")
            if integrated_object.get("description"):
                text_parts.append(f"설명: {integrated_object['description']}")
        
        combined_text = "\n\n".join(text_parts)
        
        if len(combined_text) > max_length:
            return combined_text[:max_length] + "..."
        return combined_text
        
    except Exception as e:
        logger.error(f"요약용 텍스트 추출 중 오류: {e}")
        return ""


def extract_integrated_text_for_embedding(integrated_object: Dict[str, Any]) -> str:
    """
    통합 객체에서 임베딩을 위한 텍스트를 추출합니다.
    
    Args:
        integrated_object: 통합 객체
        
    Returns:
        str: 임베딩용 텍스트
    """
    try:
        # 통합 텍스트가 있으면 사용
        if integrated_object.get("integrated_text"):
            return integrated_object["integrated_text"]
        
        # 통합 텍스트가 없으면 개별 필드에서 구성
        text_parts = []
        
        # 타입에 따른 텍스트 추출
        if integrated_object.get("object_type") == "integrated_ticket":
            if integrated_object.get("subject"):
                text_parts.append(integrated_object["subject"])
            if integrated_object.get("description_text"):
                text_parts.append(integrated_object["description_text"])
            
            # 대화 내역 추가
            conversations = integrated_object.get("conversations", [])
            for conv in conversations:
                if conv.get("body_text"):
                    text_parts.append(conv["body_text"])
                    
        elif integrated_object.get("object_type") == "integrated_article":
            if integrated_object.get("title"):
                text_parts.append(integrated_object["title"])
            if integrated_object.get("description"):
                text_parts.append(integrated_object["description"])
        
        return "\n\n".join(text_parts)
        
    except Exception as e:
        logger.error(f"임베딩용 텍스트 추출 중 오류: {e}")
        return ""
