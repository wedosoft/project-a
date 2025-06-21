"""
데이터 통합 모듈 - 티켓/문서 통합 객체 생성

지침서 준수: 멀티테넌트 및 company_id 자동 태깅
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def create_integrated_ticket_object(
    ticket: Dict[str, Any], 
    conversations: Optional[List[Dict[str, Any]]] = None, 
    attachments: Optional[List[Dict[str, Any]]] = None,
    company_id: str = None
) -> Dict[str, Any]:
    """
    티켓, 대화내역, 첨부파일을 하나의 통합 객체로 생성합니다.
    
    Args:
        ticket: 티켓 데이터
        conversations: 대화내역 리스트 (옵션)
        attachments: 첨부파일 리스트 (옵션)
        company_id: 회사 ID (멀티테넌트 필수)
        
    Returns:
        Dict[str, Any]: 통합된 티켓 객체
    """
    # 지침서 준수: company_id 필수 검증
    if not company_id:
        raise ValueError("company_id는 멀티테넌트 지원을 위해 필수입니다")
    
    # 기본 티켓 정보 복사
    integrated_object = ticket.copy()
    
    # 대화내역이 티켓에 포함되어 있는 경우 사용, 아니면 파라미터 사용
    if conversations is None:
        conversations = ticket.get("conversations", [])
    
    # 첨부파일이 티켓에 포함되어 있는 경우 사용, 아니면 파라미터 사용
    if attachments is None:
        attachments = ticket.get("all_attachments", [])
    
    # 통합 객체 구성 (지침서 기반 멀티테넌트 태깅)
    integrated_object.update({
        "conversations": conversations,
        "all_attachments": attachments,
        "has_conversations": len(conversations) > 0,
        "has_attachments": len(attachments) > 0,
        "conversation_count": len(conversations),
        "attachment_count": len(attachments),
        "integration_timestamp": datetime.utcnow().isoformat(),
        "object_type": "integrated_ticket",
        "company_id": company_id,  # 지침서 필수: company_id 자동 태깅
        "platform": "freshdesk"   # 플랫폼 구분
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
    
    logger.debug(f"통합 티켓 객체 생성 완료: ID={ticket.get('id')}, company_id={company_id}")
    return integrated_object


def create_integrated_article_object(
    article: Dict[str, Any], 
    attachments: Optional[List[Dict[str, Any]]] = None,
    company_id: str = None
) -> Dict[str, Any]:
    """
    지식베이스 문서와 첨부파일을 하나의 통합 객체로 생성합니다.
    
    Args:
        article: 지식베이스 문서 데이터
        attachments: 첨부파일 리스트 (옵션)
        company_id: 회사 ID (멀티테넌트 필수)
        
    Returns:
        Dict[str, Any]: 통합된 문서 객체
    """
    # 지침서 준수: company_id 필수 검증
    if not company_id:
        raise ValueError("company_id는 멀티테넌트 지원을 위해 필수입니다")
    
    # 기본 문서 정보 복사
    integrated_object = article.copy()
    
    # 첨부파일이 문서에 포함되어 있는 경우 사용, 아니면 파라미터 사용
    if attachments is None:
        attachments = article.get("attachments", [])
    
    # 통합 객체 구성 (지침서 기반 멀티테넌트 태깅)
    integrated_object.update({
        "attachments": attachments,
        "has_attachments": len(attachments) > 0,
        "attachment_count": len(attachments),
        "integration_timestamp": datetime.utcnow().isoformat(),
        "object_type": "integrated_article",
        "company_id": company_id,  # 지침서 필수: company_id 자동 태깅
        "platform": "freshdesk"   # 플랫폼 구분
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
    
    logger.debug(f"통합 문서 객체 생성 완료: ID={article.get('id')}, company_id={company_id}")
    return integrated_object
