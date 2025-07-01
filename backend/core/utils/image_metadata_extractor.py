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
        추출된 이미지 메타데이터를 포함한 딕셔너리
        {
            "inline_images": [...],
            "all_images": [...],
            "has_inline_images": bool,
            "inline_image_count": int,
            "total_image_count": int,
            "image_count": int
        }
    """
    try:
        inline_images = []
        all_images = []
        
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
                # 첫 번째 img 태그 샘플 로깅
                logger.debug(f"첫 번째 img 태그 샘플: {img_tags_found[0][:200]}...")
            else:
                logger.warning(f"티켓 {ticket_id} 본문에 <img> 태그 없음")
            
            ticket_inline_images = core_utils.extract_inline_images_from_html(description)
            logger.info(f"티켓 {ticket_id} 본문에서 인라인 이미지 {len(ticket_inline_images)}개 발견")
            for img in ticket_inline_images:
                img['source_location'] = 'ticket_description'
                img['conversation_id'] = None
            inline_images.extend(ticket_inline_images)
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
                    img['source_location'] = 'conversation'
                    img['conversation_id'] = conv_id
                    img['conversation_index'] = conv_idx
                inline_images.extend(conv_inline_images)
        
        # 3. 첨부파일에서 이미지 파일 추출
        # Freshdesk fetcher는 'all_attachments' 키를 사용하고, 기본 'attachments'도 지원
        attachments = ticket_data.get('all_attachments', []) or ticket_data.get('attachments', [])
        logger.info(f"티켓 {ticket_id}에 첨부파일 {len(attachments)}개 있음")
        
        image_attachments = 0
        for att in attachments:
            content_type = att.get('content_type', '').lower()
            if content_type.startswith('image/'):
                image_attachments += 1
                image_attachment = {
                    "attachment_id": att.get('id'),
                    "name": att.get('name', ''),
                    "content_type": content_type,
                    "size": att.get('size', 0),
                    "type": "attachment",
                    "source_location": "attachments",
                    "conversation_id": None,
                    "created_at": att.get('created_at', ''),
                    "updated_at": att.get('updated_at', '')
                }
                all_images.append(image_attachment)
        
        logger.info(f"티켓 {ticket_id}에서 이미지 첨부파일 {image_attachments}개 발견")
        
        # 4. 인라인 이미지 정리 (URL 제거 등)
        sanitized_inline_images = core_utils.sanitize_inline_image_metadata(inline_images)
        
        # 5. all_images에 인라인 이미지도 추가
        for img in sanitized_inline_images:
            all_images.append({
                **img,
                "type": "inline"
            })
        
        # 6. 중복 제거 (attachment_id 기준, None인 경우 src_url 기준)
        unique_images = []
        seen_ids = set()
        seen_urls = set()
        
        for img in all_images:
            att_id = img.get('attachment_id')
            src_url = img.get('src_url', '')
            
            if att_id and att_id not in seen_ids:
                unique_images.append(img)
                seen_ids.add(att_id)
            elif not att_id and src_url and src_url not in seen_urls:
                # attachment_id가 없는 경우 src_url로 중복 체크
                unique_images.append(img)
                seen_urls.add(src_url)
            elif not att_id and not src_url:
                # 둘 다 없는 경우도 포함 (rare case)
                unique_images.append(img)
        
        result = {
            "inline_images": sanitized_inline_images,
            "all_images": unique_images,
            "has_inline_images": len(sanitized_inline_images) > 0,
            "inline_image_count": len(sanitized_inline_images),
            "total_image_count": len(unique_images),
            "image_count": len(unique_images)  # 호환성
        }
        
        logger.info(f"티켓 {ticket_id} 이미지 메타데이터 추출 완료: "
                    f"인라인 {len(sanitized_inline_images)}개, "
                    f"전체 {len(unique_images)}개")
        
        return result
        
    except Exception as e:
        logger.error(f"티켓 이미지 메타데이터 추출 중 오류: {e}")
        return {
            "inline_images": [],
            "all_images": [],
            "has_inline_images": False,
            "inline_image_count": 0,
            "total_image_count": 0,
            "image_count": 0
        }


def extract_article_image_metadata(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    KB 문서 데이터에서 이미지 및 첨부파일 메타데이터를 추출합니다.
    
    Args:
        article_data: Freshdesk KB 문서 데이터
        
    Returns:
        추출된 이미지 메타데이터를 포함한 딕셔너리
    """
    try:
        inline_images = []
        all_images = []
        
        # 1. 문서 본문(description)에서 인라인 이미지 추출
        description = article_data.get('description', '') or article_data.get('description_text', '')
        if description:
            article_inline_images = core_utils.extract_inline_images_from_html(description)
            for img in article_inline_images:
                img['source_location'] = 'article_description'
                img['conversation_id'] = None
            inline_images.extend(article_inline_images)
        
        # 2. 첨부파일에서 이미지 파일 추출
        # Freshdesk fetcher는 'all_attachments' 키를 사용하고, 기본 'attachments'도 지원
        attachments = article_data.get('all_attachments', []) or article_data.get('attachments', [])
        for att in attachments:
            content_type = att.get('content_type', '').lower()
            if content_type.startswith('image/'):
                image_attachment = {
                    "attachment_id": att.get('id'),
                    "name": att.get('name', ''),
                    "content_type": content_type,
                    "size": att.get('size', 0),
                    "type": "attachment",
                    "source_location": "attachments",
                    "conversation_id": None,
                    "created_at": att.get('created_at', ''),
                    "updated_at": att.get('updated_at', '')
                }
                all_images.append(image_attachment)
        
        # 3. 인라인 이미지 정리 (URL 제거 등)
        sanitized_inline_images = core_utils.sanitize_inline_image_metadata(inline_images)
        
        # 4. all_images에 인라인 이미지도 추가
        for img in sanitized_inline_images:
            all_images.append({
                **img,
                "type": "inline"
            })
        
        # 5. 중복 제거 (attachment_id 기준, None인 경우 src_url 기준)
        unique_images = []
        seen_ids = set()
        seen_urls = set()
        
        for img in all_images:
            att_id = img.get('attachment_id')
            src_url = img.get('src_url', '')
            
            if att_id and att_id not in seen_ids:
                unique_images.append(img)
                seen_ids.add(att_id)
            elif not att_id and src_url and src_url not in seen_urls:
                # attachment_id가 없는 경우 src_url로 중복 체크
                unique_images.append(img)
                seen_urls.add(src_url)
            elif not att_id and not src_url:
                # 둘 다 없는 경우도 포함 (rare case)
                unique_images.append(img)
        
        return {
            "inline_images": sanitized_inline_images,
            "all_images": unique_images,
            "has_inline_images": len(sanitized_inline_images) > 0,
            "inline_image_count": len(sanitized_inline_images),
            "total_image_count": len(unique_images),
            "image_count": len(unique_images)  # 호환성
        }
        
    except Exception as e:
        logger.error(f"KB 문서 이미지 메타데이터 추출 중 오류: {e}")
        return {
            "inline_images": [],
            "all_images": [],
            "has_inline_images": False,
            "inline_image_count": 0,
            "total_image_count": 0,
            "image_count": 0
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
            f"인라인 {image_metadata['inline_image_count']}개, "
            f"전체 {image_metadata['total_image_count']}개"
        )
        
        return enriched_metadata
        
    except Exception as e:
        logger.error(f"메타데이터 이미지 정보 추가 중 오류: {e}")
        return metadata


def validate_image_metadata(image_metadata: Dict[str, Any]) -> bool:
    """
    이미지 메타데이터의 유효성을 검증합니다.
    
    Args:
        image_metadata: 검증할 이미지 메타데이터
        
    Returns:
        유효성 검증 결과
    """
    try:
        required_fields = [
            "inline_images", "all_images", "has_inline_images",
            "inline_image_count", "total_image_count", "image_count"
        ]
        
        # 필수 필드 존재 확인
        for field in required_fields:
            if field not in image_metadata:
                logger.warning(f"필수 필드 누락: {field}")
                return False
        
        # 데이터 타입 확인
        if not isinstance(image_metadata["inline_images"], list):
            logger.warning("inline_images가 리스트가 아닙니다")
            return False
        
        if not isinstance(image_metadata["all_images"], list):
            logger.warning("all_images가 리스트가 아닙니다")
            return False
        
        if not isinstance(image_metadata["has_inline_images"], bool):
            logger.warning("has_inline_images가 불리언이 아닙니다")
            return False
        
        # 개수 일관성 확인
        inline_count = len(image_metadata["inline_images"])
        if image_metadata["inline_image_count"] != inline_count:
            logger.warning(f"인라인 이미지 개수 불일치: {image_metadata['inline_image_count']} != {inline_count}")
            return False
        
        total_count = len(image_metadata["all_images"])
        if image_metadata["total_image_count"] != total_count:
            logger.warning(f"전체 이미지 개수 불일치: {image_metadata['total_image_count']} != {total_count}")
            return False
        
        # has_inline_images 논리 확인
        has_inline = image_metadata["has_inline_images"]
        should_have_inline = inline_count > 0
        if has_inline != should_have_inline:
            logger.warning(f"has_inline_images 논리 오류: {has_inline} != {should_have_inline}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"이미지 메타데이터 검증 중 오류: {e}")
        return False