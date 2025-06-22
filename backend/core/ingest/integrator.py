"""
데이터 통합 모듈 - 티켓/문서 통합 객체 생성

지침서 준수: 멀티테넌트 및 company_id 자동 태깅
인라인 이미지 처리 및 첨부파일 통합 관리
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.utils import (
    extract_inline_images_from_html,
    sanitize_inline_image_metadata,
    extract_text_content_from_html,
    count_inline_images_in_html
)

logger = logging.getLogger(__name__)

def create_integrated_ticket_object(
    ticket: Dict[str, Any], 
    conversations: Optional[List[Dict[str, Any]]] = None, 
    attachments: Optional[List[Dict[str, Any]]] = None,
    company_id: str = None
) -> Dict[str, Any]:
    """
    티켓, 대화내역, 첨부파일을 하나의 통합 객체로 생성합니다.
    인라인 이미지 처리 및 첨부파일 통합 관리 포함.
    
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
    
    # 인라인 이미지 처리
    inline_images = []
    
    # 1. 티켓 본문(description)에서 인라인 이미지 추출
    description_html = ticket.get("description", "")
    if description_html:
        ticket_inline_images = extract_inline_images_from_html(description_html)
        inline_images.extend(ticket_inline_images)
    
    # 2. 대화내역에서 인라인 이미지 추출
    for conv in conversations:
        conv_body = conv.get("body", "")
        if conv_body:
            conv_inline_images = extract_inline_images_from_html(conv_body)
            # 대화 ID와 위치 정보 추가
            for img in conv_inline_images:
                img["conversation_id"] = conv.get("id")
                img["conversation_position"] = img.get("position", 0)
            inline_images.extend(conv_inline_images)
    
    # 3. 인라인 이미지 메타데이터 정리 (URL 제거)
    sanitized_inline_images = sanitize_inline_image_metadata(inline_images)
    
    # 4. 첨부파일과 인라인 이미지 통합 (선택적)
    all_images = []
    
    # 첨부파일 중 이미지 타입만 추출
    for att in attachments:
        content_type = att.get("content_type", "")
        if content_type and content_type.startswith("image/"):
            # 첨부파일 이미지 메타데이터 (URL 제거)
            image_meta = {
                "attachment_id": att.get("id"),
                "name": att.get("name", ""),
                "content_type": content_type,
                "size": att.get("size", 0),
                "type": "attachment",  # 첨부파일 구분
                "created_at": att.get("created_at"),
                "updated_at": att.get("updated_at"),
                # attachment_url은 저장하지 않음 (보안)
            }
            all_images.append(image_meta)
    
    # 인라인 이미지도 통합 리스트에 추가
    all_images.extend(sanitized_inline_images)
    
    # 통합 객체 구성 (지침서 기반 멀티테넌트 태깅)
    integrated_object.update({
        "conversations": conversations,
        "all_attachments": attachments,
        "inline_images": sanitized_inline_images,  # 인라인 이미지 별도 저장
        "all_images": all_images,  # 첨부파일 + 인라인 이미지 통합
        "has_conversations": len(conversations) > 0,
        "has_attachments": len(attachments) > 0,
        "has_inline_images": len(sanitized_inline_images) > 0,
        "has_images": len(all_images) > 0,  # 모든 이미지 포함 여부
        "conversation_count": len(conversations),
        "attachment_count": len(attachments),
        "inline_image_count": len(sanitized_inline_images),
        "total_image_count": len(all_images),
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
    
    # HTML에서 순수 텍스트만 추출
    if description_html:
        description_text = extract_text_content_from_html(description_html)
        if description_text:
            text_parts.append(f"설명: {description_text}")
    elif ticket.get("description_text"):
        text_parts.append(f"설명: {ticket['description_text']}")
    
    # 대화내역 텍스트 추가 (HTML에서 텍스트 추출)
    for conv in conversations:
        conv_body = conv.get("body", "")
        if conv_body:
            conv_text = extract_text_content_from_html(conv_body)
            if conv_text:
                text_parts.append(f"대화: {conv_text}")
        elif conv.get("body_text"):
            text_parts.append(f"대화: {conv['body_text']}")
    
    # 첨부파일 정보 추가
    if attachments:
        attachment_names = [att.get("name", "Unknown") for att in attachments]
        text_parts.append(f"첨부파일: {', '.join(attachment_names)}")
    
    # 인라인 이미지 정보 추가
    if sanitized_inline_images:
        inline_image_info = []
        for img in sanitized_inline_images:
            alt_text = img.get("alt_text", "")
            if alt_text:
                inline_image_info.append(f"이미지({alt_text})")
            else:
                inline_image_info.append("이미지")
        text_parts.append(f"인라인 이미지: {', '.join(inline_image_info)}")
    
    integrated_object["integrated_text"] = "\n\n".join(text_parts)
    
    logger.debug(
        f"통합 티켓 객체 생성 완료: ID={ticket.get('id')}, company_id={company_id}, "
        f"첨부파일={len(attachments)}, 인라인이미지={len(sanitized_inline_images)}"
    )
    return integrated_object


def create_integrated_article_object(
    article: Dict[str, Any], 
    attachments: Optional[List[Dict[str, Any]]] = None,
    company_id: str = None
) -> Dict[str, Any]:
    """
    지식베이스 문서와 첨부파일을 하나의 통합 객체로 생성합니다.
    인라인 이미지 처리 및 첨부파일 통합 관리 포함.
    
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
    
    # 인라인 이미지 처리
    inline_images = []
    
    # KB 문서 본문(description)에서 인라인 이미지 추출
    description_html = article.get("description", "")
    if description_html:
        article_inline_images = extract_inline_images_from_html(description_html)
        inline_images.extend(article_inline_images)
    
    # 인라인 이미지 메타데이터 정리 (URL 제거)
    sanitized_inline_images = sanitize_inline_image_metadata(inline_images)
    
    # 첨부파일과 인라인 이미지 통합
    all_images = []
    
    # 첨부파일 중 이미지 타입만 추출
    for att in attachments:
        content_type = att.get("content_type", "")
        if content_type and content_type.startswith("image/"):
            # 첨부파일 이미지 메타데이터 (URL 제거)
            image_meta = {
                "attachment_id": att.get("id"),
                "name": att.get("name", ""),
                "content_type": content_type,
                "size": att.get("size", 0),
                "type": "attachment",  # 첨부파일 구분
                "created_at": att.get("created_at"),
                "updated_at": att.get("updated_at"),
                # attachment_url은 저장하지 않음 (보안)
            }
            all_images.append(image_meta)
    
    # 인라인 이미지도 통합 리스트에 추가
    all_images.extend(sanitized_inline_images)
    
    # 통합 객체 구성 (지침서 기반 멀티테넌트 태깅)
    integrated_object.update({
        "attachments": attachments,
        "inline_images": sanitized_inline_images,  # 인라인 이미지 별도 저장
        "all_images": all_images,  # 첨부파일 + 인라인 이미지 통합
        "has_attachments": len(attachments) > 0,
        "has_inline_images": len(sanitized_inline_images) > 0,
        "has_images": len(all_images) > 0,  # 모든 이미지 포함 여부
        "attachment_count": len(attachments),
        "inline_image_count": len(sanitized_inline_images),
        "total_image_count": len(all_images),
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
    
    # HTML에서 순수 텍스트만 추출
    if description_html:
        description_text = extract_text_content_from_html(description_html)
        if description_text:
            text_parts.append(f"설명: {description_text}")
    elif article.get("description_text"):
        text_parts.append(f"설명: {article['description_text']}")
    
    # 첨부파일 정보 추가
    if attachments:
        attachment_names = [att.get("name", "Unknown") for att in attachments]
        text_parts.append(f"첨부파일: {', '.join(attachment_names)}")
    
    # 인라인 이미지 정보 추가
    if sanitized_inline_images:
        inline_image_info = []
        for img in sanitized_inline_images:
            alt_text = img.get("alt_text", "")
            if alt_text:
                inline_image_info.append(f"이미지({alt_text})")
            else:
                inline_image_info.append("이미지")
        text_parts.append(f"인라인 이미지: {', '.join(inline_image_info)}")
    
    integrated_object["integrated_text"] = "\n\n".join(text_parts)
    
    logger.debug(
        f"통합 문서 객체 생성 완료: ID={article.get('id')}, company_id={company_id}, "
        f"첨부파일={len(attachments)}, 인라인이미지={len(sanitized_inline_images)}"
    )
    return integrated_object
