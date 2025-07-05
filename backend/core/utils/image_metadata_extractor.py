"""
이미지 및 첨부파일 메타데이터 추출 유틸리티

이 모듈은 티켓, 대화, KB 문서에서 인라인 이미지와 첨부파일 정보를 추출하여
벡터 DB에 저장할 수 있는 형태로 정리하는 기능을 제공합니다.
"""

import logging
from typing import Any, Dict, List, Optional, Union
import re

import importlib.util
import os

# core.utils 모듈을 직접 로드
utils_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils.py')
spec = importlib.util.spec_from_file_location("core_utils", utils_path)
if spec and spec.loader:
    core_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core_utils)
else:
    raise ImportError(f"core.utils 모듈을 로드할 수 없습니다: {utils_path}")

logger = logging.getLogger(__name__)


def extract_ticket_image_metadata(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    티켓 데이터에서 이미지 및 첨부파일 메타데이터를 추출합니다.
    
    Args:
        ticket_data: Freshdesk 티켓 데이터
        
    Returns:
        최적화된 이미지 메타데이터 딕셔너리
        {
            "has_attachments": bool,
            "has_inline_images": bool,
            "attachment_count": int,
            "extended_metadata": {
                "attachments": [...]  # type 필드로 inline/attachment 구분
            }
        }
    """
    try:
        unified_attachments = []
        
        ticket_id = ticket_data.get('id', 'unknown')
        logger.info(f"티켓 {ticket_id} 이미지 메타데이터 추출 시작")
        
        # 1. 티켓 본문(description)에서 인라인 이미지 추출
        description = ticket_data.get('description', '') or ticket_data.get('description_text', '')
        if description:
            logger.info(f"티켓 {ticket_id} 본문 길이: {len(description)} 문자")
            # HTML 샘플 로깅 (img 태그 포함 여부 확인) - 대소문자 구분 없이
            img_tag_regex = re.compile(r'<img[^>]*>', re.IGNORECASE)
            img_tags_found = img_tag_regex.findall(description)
            if img_tags_found:
                logger.info(f"티켓 {ticket_id} 본문에 <img> 태그 {len(img_tags_found)}개 발견됨")
            
            ticket_inline_images = core_utils.extract_inline_images_from_html(description)
            logger.info(f"티켓 {ticket_id} 본문에서 인라인 이미지 {len(ticket_inline_images)}개 발견")
            for img in ticket_inline_images:
                unified_attachments.append({
                    "attachment_id": img.get('attachment_id'),
                    "name": img.get('alt_text') or f"inline_image_{img.get('position', 0)}",
                    "type": "inline",
                    "content_type": "image/unknown",
                    "source_location": "ticket_description",
                    "conversation_id": None,
                    "ticket_id": ticket_id,
                    "position": img.get('position', 0)
                })
        else:
            logger.info(f"티켓 {ticket_id} 본문이 비어있음")
        
        # 2. 대화(conversations)에서 인라인 이미지 추출
        conversations = ticket_data.get('conversations', [])
        for conv_idx, conversation in enumerate(conversations):
            conv_id = conversation.get('id')
            conv_body = conversation.get('body', '') or conversation.get('body_text', '')
            
            if conv_body:
                # 대화 HTML에서 img 태그 확인 - 대소문자 구분 없이
                img_tag_regex = re.compile(r'<img[^>]*>', re.IGNORECASE)
                if img_tag_regex.search(conv_body):
                    logger.info(f"티켓 {ticket_id} 대화 #{conv_idx}에 <img> 태그 발견됨")
                
                conv_inline_images = core_utils.extract_inline_images_from_html(conv_body)
                logger.info(f"티켓 {ticket_id} 대화 #{conv_idx}에서 인라인 이미지 {len(conv_inline_images)}개 발견")
                for img in conv_inline_images:
                    unified_attachments.append({
                        "attachment_id": img.get('attachment_id'),
                        "name": img.get('alt_text') or f"inline_image_{img.get('position', 0)}",
                        "type": "inline",
                        "content_type": "image/unknown",
                        "source_location": "conversation",
                        "conversation_id": conv_id,
                        "ticket_id": ticket_id,
                        "position": img.get('position', 0)
                    })
        
        # 3. 첨부파일에서 모든 파일 추출 (이미지뿐만 아니라 모든 첨부파일)
        attachments = ticket_data.get('all_attachments', []) or ticket_data.get('attachments', [])
        logger.info(f"티켓 {ticket_id}에 첨부파일 {len(attachments)}개 있음")
        
        for att in attachments:
            # 첨부파일 메타데이터 구성 (빈 필드 제거)
            attachment_meta = {
                "attachment_id": att.get('id'),
                "name": att.get('name', ''),
                "type": "attachment",
                "content_type": att.get('content_type', ''),
                "size": att.get('size', 0),
                "url": att.get('attachment_url', ''),
                "source_location": "attachments",
                "conversation_id": att.get('conversation_id'),  # 프론트엔드 필수 필드
                "ticket_id": ticket_id,  # 프론트엔드 필수 필드
            }
            
            # 날짜 필드는 값이 있는 경우만 포함
            if att.get('created_at'):
                attachment_meta["created_at"] = att.get('created_at')
            if att.get('updated_at'):
                attachment_meta["updated_at"] = att.get('updated_at')
            
            unified_attachments.append(attachment_meta)
        
        # 통계 계산
        inline_count = sum(1 for att in unified_attachments if att['type'] == 'inline')
        has_inline_images = inline_count > 0
        has_attachments = len(attachments) > 0
        
        result = {
            "has_attachments": has_attachments,
            "has_inline_images": has_inline_images,
            "attachment_count": len(attachments),
            "attachments": unified_attachments
        }
        
        logger.info(f"티켓 {ticket_id} 이미지 메타데이터 추출 완료: "
                    f"인라인 {inline_count}개, "
                    f"첨부파일 {len(attachments)}개")
        
        return result
        
    except Exception as e:
        logger.error(f"티켓 이미지 메타데이터 추출 중 오류: {e}")
        return {
            "has_attachments": False,
            "has_inline_images": False,
            "attachment_count": 0,
            "attachments": []
        }


def extract_article_image_metadata(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    KB 문서 데이터에서 이미지 및 첨부파일 메타데이터를 추출합니다.
    
    Args:
        article_data: Freshdesk KB 문서 데이터
        
    Returns:
        최적화된 이미지 메타데이터 딕셔너리
        {
            "has_attachments": bool,
            "has_inline_images": bool,
            "attachment_count": int,
            "extended_metadata": {
                "attachments": [...]  # type 필드로 inline/attachment 구분
            }
        }
    """
    try:
        unified_attachments = []
        
        article_id = article_data.get('id', 'unknown')
        logger.info(f"KB 아티클 {article_id} 이미지 메타데이터 추출 시작")
        
        # 1. 문서 본문(description)에서 인라인 이미지 추출
        description = article_data.get('description', '') or article_data.get('description_text', '')
        if description:
            article_inline_images = core_utils.extract_inline_images_from_html(description)
            logger.info(f"KB 아티클 {article_id} 본문에서 인라인 이미지 {len(article_inline_images)}개 발견")
            for img in article_inline_images:
                unified_attachments.append({
                    "attachment_id": img.get('attachment_id'),
                    "name": img.get('alt_text') or f"inline_image_{img.get('position', 0)}",
                    "type": "inline",
                    "content_type": "image/unknown",
                    "source_location": "article_description",
                    "conversation_id": None,
                    "ticket_id": None,  # KB 아티클은 ticket_id가 없음
                    "article_id": article_id,  # KB 아티클 ID 추가
                    "position": img.get('position', 0)
                })
        
        # 2. 첨부파일에서 모든 파일 추출
        attachments = article_data.get('all_attachments', []) or article_data.get('attachments', [])
        logger.info(f"KB 아티클 {article_id}에 첨부파일 {len(attachments)}개 있음")
        
        for att in attachments:
            # KB 아티클 첨부파일 메타데이터 구성 (빈 필드 제거)
            attachment_meta = {
                "attachment_id": att.get('id'),
                "name": att.get('name', ''),
                "type": "attachment",
                "content_type": att.get('content_type', ''),
                "size": att.get('size', 0),
                "url": att.get('attachment_url', ''),
                "source_location": "attachments",
                "conversation_id": None,  # KB 아티클은 conversation_id가 없음
                "ticket_id": None,  # KB 아티클은 ticket_id가 없음
                "article_id": article_id,  # KB 아티클 ID 추가
            }
            
            # 날짜 필드는 값이 있는 경우만 포함
            if att.get('created_at'):
                attachment_meta["created_at"] = att.get('created_at')
            if att.get('updated_at'):
                attachment_meta["updated_at"] = att.get('updated_at')
            
            unified_attachments.append(attachment_meta)
        
        # 통계 계산
        inline_count = sum(1 for att in unified_attachments if att['type'] == 'inline')
        has_inline_images = inline_count > 0
        has_attachments = len(attachments) > 0
        
        result = {
            "has_attachments": has_attachments,
            "has_inline_images": has_inline_images,
            "attachment_count": len(attachments),
            "attachments": unified_attachments
        }
        
        logger.info(f"KB 아티클 {article_id} 이미지 메타데이터 추출 완료: "
                    f"인라인 {inline_count}개, "
                    f"첨부파일 {len(attachments)}개")
        
        return result
        
    except Exception as e:
        logger.error(f"KB 문서 이미지 메타데이터 추출 중 오류: {e}")
        return {
            "has_attachments": False,
            "has_inline_images": False,
            "attachment_count": 0,
            "attachments": []
        }


def enrich_metadata_with_images(
    metadata: Dict[str, Any], 
    source_data: Dict[str, Any], 
    doc_type: str
) -> Dict[str, Any]:
    """
    기존 메타데이터에 이미지 정보를 추가합니다.
    
    Args:
        metadata: 기존 메타데이터
        source_data: 원본 데이터 (티켓 또는 KB 문서)
        doc_type: 문서 타입 ("ticket" 또는 "article")
        
    Returns:
        이미지 메타데이터가 추가된 메타데이터
    """
    try:
        # 문서 타입에 따라 적절한 추출 함수 사용
        if doc_type == "ticket":
            image_metadata = extract_ticket_image_metadata(source_data)
        elif doc_type == "article":
            image_metadata = extract_article_image_metadata(source_data)
        else:
            logger.warning(f"지원하지 않는 문서 타입: {doc_type}")
            return metadata
        
        # 기존 메타데이터에 이미지 정보 병합
        enriched_metadata = metadata.copy()
        enriched_metadata.update(image_metadata)
        
        logger.debug(
            f"{doc_type} 메타데이터에 이미지 정보 추가: "
            f"인라인 {sum(1 for att in image_metadata.get('attachments', []) if att.get('type') == 'inline')}개, "
            f"첨부파일 {image_metadata.get('attachment_count', 0)}개"
        )
        
        return enriched_metadata
        
    except Exception as e:
        logger.error(f"메타데이터 이미지 정보 추가 중 오류: {e}")
        return metadata


def validate_image_metadata(image_metadata: Dict[str, Any]) -> bool:
    """
    최적화된 이미지 메타데이터의 유효성을 검증합니다.
    
    Args:
        image_metadata: 검증할 이미지 메타데이터
        
    Returns:
        유효성 검증 결과
    """
    try:
        required_fields = [
            "has_attachments", "has_inline_images", "attachment_count", "attachments"
        ]
        
        # 필수 필드 존재 확인
        for field in required_fields:
            if field not in image_metadata:
                logger.warning(f"필수 필드 누락: {field}")
                return False
        
        # 데이터 타입 확인
        if not isinstance(image_metadata["has_attachments"], bool):
            logger.warning("has_attachments가 불리언이 아닙니다")
            return False
        
        if not isinstance(image_metadata["has_inline_images"], bool):
            logger.warning("has_inline_images가 불리언이 아닙니다")
            return False
        
        if not isinstance(image_metadata["attachment_count"], int):
            logger.warning("attachment_count가 정수가 아닙니다")
            return False
        
        if not isinstance(image_metadata["attachments"], list):
            logger.warning("attachments가 리스트가 아닙니다")
            return False
        
        # 논리 일관성 확인
        attachments = image_metadata["attachments"]
        attachment_files = [att for att in attachments if att.get("type") == "attachment"]
        inline_images = [att for att in attachments if att.get("type") == "inline"]
        
        if image_metadata["attachment_count"] != len(attachment_files):
            logger.warning(f"첨부파일 개수 불일치: {image_metadata['attachment_count']} != {len(attachment_files)}")
            return False
        
        has_inline = image_metadata["has_inline_images"]
        should_have_inline = len(inline_images) > 0
        if has_inline != should_have_inline:
            logger.warning(f"has_inline_images 논리 오류: {has_inline} != {should_have_inline}")
            return False
        
        has_attachments = image_metadata["has_attachments"]
        should_have_attachments = len(attachment_files) > 0
        if has_attachments != should_have_attachments:
            logger.warning(f"has_attachments 논리 오류: {has_attachments} != {should_have_attachments}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"이미지 메타데이터 검증 중 오류: {e}")
        return False