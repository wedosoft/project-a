"""
데이터 통합 모듈 - 티켓/문서 통합 객체 생성 (간소화 버전)

지침서 준수: 멀티테넌트 및 tenant_id 자동 태깅
순수 텍스트 기반 처리로 성능 최적화
HTML 처리 제거, 첨부파일 엔드포인트 활용
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def create_integrated_ticket_object(
    ticket: Dict[str, Any], 
    conversations: Optional[List[Dict[str, Any]]] = None, 
    attachments: Optional[List[Dict[str, Any]]] = None,
    tenant_id: str = None
) -> Dict[str, Any]:
    """
    티켓, 대화내역, 첨부파일을 하나의 통합 객체로 생성합니다.
    간소화 버전: HTML 처리 제거, 순수 텍스트만 사용
    
    Args:
        ticket: 티켓 데이터 (description_text 필드 사용)
        conversations: 대화내역 리스트 (body_text 필드 사용)
        attachments: 첨부파일 리스트 (엔드포인트 참조)
        tenant_id: 테넌트 ID (멀티테넌트 필수)
        
    Returns:
        Dict[str, Any]: 간소화된 통합 티켓 객체
    """
    # 지침서 준수: tenant_id 필수 검증
    if not tenant_id:
        raise ValueError("tenant_id는 멀티테넌트 지원을 위해 필수입니다")
    
    # 대화내역과 첨부파일 처리
    if conversations is None:
        conversations = ticket.get("conversations", [])
    if attachments is None:
        attachments = ticket.get("all_attachments", [])
    
    logger.debug(f"간소화된 통합 객체 생성 - 티켓 ID: {ticket.get('id')}, 대화: {len(conversations)}개, 첨부파일: {len(attachments)}개")
    
    # HTML 필드 제외한 기본 티켓 정보만 복사
    base_ticket_data = {k: v for k, v in ticket.items() 
                       if k not in ['description', 'conversations', 'all_attachments']}
    
    # 순수 텍스트 통합 (HTML 파싱 없이)
    text_parts = []
    
    # 티켓 제목과 설명 (텍스트 필드만 사용)
    if ticket.get("subject"):
        text_parts.append(f"제목: {ticket['subject']}")
    
    if ticket.get("description_text"):
        text_parts.append(f"설명: {ticket['description_text']}")
    
    # 대화내역 텍스트 추가 (HTML 파싱 없이)
    for conv in conversations:
        if conv.get("body_text"):
            text_parts.append(f"대화: {conv['body_text']}")
    
    # 첨부파일 참조 정보 (엔드포인트 활용, 최소 정보만)
    attachment_refs = []
    if attachments:
        text_parts.append("\n=== 첨부파일 목록 ===")
        for att in attachments:
            # 부모 관계 판단 (첨부파일 다운로드를 위해 필수)
            if att.get("conversation_id"):
                parent_type = "conversation"
                parent_id = att.get("conversation_id")
            else:
                parent_type = "ticket"
                parent_id = att.get("ticket_id") or ticket.get("id")
            
            # 최소 첨부파일 정보만 저장 (용량 최적화)
            attachment_ref = {
                "id": att.get("id"),
                "name": att.get("name", ""),
                "content_type": att.get("content_type", ""),
                "size": att.get("size", 0),
                "parent_type": parent_type,
                "parent_id": parent_id
                # download_endpoint: /attachments/download/{id}?ticket_id={parent_id} 또는 ?conversation_id={parent_id}
            }
            attachment_refs.append(attachment_ref)
            
            # LLM이 첨부파일을 고려할 수 있도록 상세 정보 포함
            file_info = f"- {att.get('name', 'Unknown')} ({att.get('content_type', '')}, {att.get('size', 0):,} bytes)"
            text_parts.append(file_info)
    
    # 기본 메타데이터만 최소 보존 (용량 최적화)
    essential_metadata = {
        "original_id": ticket.get("id"),
        "subject": ticket.get("subject"),
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "requester_id": ticket.get("requester_id"),
        "conversation_count": len(conversations),
        "attachment_count": len(attachments)
    }
    
    # 간소화된 통합 객체 구성 (용량 최적화)
    integrated_object = {
        "id": ticket.get("id"),  # 마이그레이션 레이어 호환성을 위해 추가
        "integrated_text": "\n\n".join(text_parts),  # LLM 처리용 텍스트
        "attachments": attachment_refs,  # 최소 첨부파일 정보
        "essential_metadata": essential_metadata,  # 핵심 메타데이터만
        "object_id": ticket.get("id"),  # storage.py에서 필요한 필드 추가
        "original_id": ticket.get("id"),  # 호환성을 위해 유지
        "tenant_id": tenant_id,
        "platform": "freshdesk",
        "object_type": "integrated_ticket",
        "integration_timestamp": datetime.utcnow().isoformat()
        # 원본 데이터는 제외 (중복 제거로 용량 절약)
    }
    
    logger.debug(f"간소화된 통합 티켓 객체 생성 완료: ID={ticket.get('id')}, tenant_id={tenant_id}")
    return integrated_object


def create_integrated_article_object(
    article: Dict[str, Any], 
    attachments: Optional[List[Dict[str, Any]]] = None,
    tenant_id: str = None
) -> Dict[str, Any]:
    """
    지식베이스 문서와 첨부파일을 하나의 통합 객체로 생성합니다.
    간소화 버전: HTML 처리 제거, 순수 텍스트만 사용
    
    Args:
        article: 지식베이스 문서 데이터 (description_text 필드 사용)
        attachments: 첨부파일 리스트 (엔드포인트 참조)
        tenant_id: 테넌트 ID (멀티테넌트 필수)
        
    Returns:
        Dict[str, Any]: 간소화된 통합 문서 객체
    """
    # 지침서 준수: tenant_id 필수 검증
    if not tenant_id:
        raise ValueError("tenant_id는 멀티테넌트 지원을 위해 필수입니다")
    
    # 첨부파일 처리
    if attachments is None:
        attachments = article.get("attachments", [])
    
    logger.debug(f"간소화된 통합 문서 객체 생성 - 문서 ID: {article.get('id')}, 첨부파일: {len(attachments)}개")
    
    # HTML 필드 제외한 기본 문서 정보만 복사
    base_article_data = {k: v for k, v in article.items() 
                        if k not in ['description', 'attachments']}
    
    # 순수 텍스트 통합 (HTML 파싱 없이)
    text_parts = []
    
    # 문서 제목과 내용 (텍스트 필드만 사용)
    if article.get("title"):
        text_parts.append(f"제목: {article['title']}")
    
    if article.get("description_text"):
        text_parts.append(f"설명: {article['description_text']}")
    
    # 첨부파일 참조 정보 (엔드포인트 활용, 최소 정보만)
    attachment_refs = []
    if attachments:
        text_parts.append("\n=== 첨부파일 목록 ===")
        for att in attachments:
            # 지식베이스 문서 첨부파일은 항상 article 타입
            parent_type = "article"
            parent_id = att.get("article_id") or article.get("id")
            
            # 최소 첨부파일 정보만 저장 (용량 최적화)
            attachment_ref = {
                "id": att.get("id"),
                "name": att.get("name", ""),
                "content_type": att.get("content_type", ""),
                "size": att.get("size", 0),
                "parent_type": parent_type,
                "parent_id": parent_id
                # TODO: 지식베이스 첨부파일 다운로드 엔드포인트 구현 필요
                # download_endpoint: /attachments/download/{id}?article_id={parent_id}
            }
            attachment_refs.append(attachment_ref)
            
            # LLM이 첨부파일을 고려할 수 있도록 상세 정보 포함
            file_info = f"- {att.get('name', 'Unknown')} ({att.get('content_type', '')}, {att.get('size', 0):,} bytes)"
            text_parts.append(file_info)
    
    # 기본 메타데이터만 최소 보존 (용량 최적화)
    essential_metadata = {
        "original_id": article.get("id"),
        "title": article.get("title"),
        "status": article.get("status"),
        "category_id": article.get("category_id"),
        "folder_id": article.get("folder_id"),
        "created_at": article.get("created_at"),
        "updated_at": article.get("updated_at"),
        "attachment_count": len(attachments)
    }
    
    # 간소화된 통합 객체 구성 (용량 최적화)
    integrated_object = {
        "id": article.get("id"),  # 마이그레이션 레이어 호환성을 위해 추가
        "integrated_text": "\n\n".join(text_parts),  # LLM 처리용 텍스트
        "attachments": attachment_refs,  # 최소 첨부파일 정보
        "essential_metadata": essential_metadata,  # 핵심 메타데이터만
        "object_id": article.get("id"),  # storage.py에서 필요한 필드 추가
        "original_id": article.get("id"),  # 호환성을 위해 유지
        "tenant_id": tenant_id,
        "platform": "freshdesk",
        "object_type": "integrated_article",
        "integration_timestamp": datetime.utcnow().isoformat()
        # 원본 데이터는 제외 (중복 제거로 용량 절약)
    }
    
    logger.debug(f"간소화된 통합 문서 객체 생성 완료: ID={article.get('id')}, tenant_id={tenant_id}")
    return integrated_object
