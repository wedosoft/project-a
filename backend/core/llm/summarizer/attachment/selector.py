"""
첨부파일 선별기 - LLM이 선별한 1~3개 첨부파일만 상담원에게 노출

이 모듈의 핵심 목적:
- 전체 첨부파일을 무차별적으로 노출하지 않음
- 티켓 내용과 실제 관련성이 높은 첨부파일만 선별
- 상담원에게 의미 있는 첨부파일만 제공하여 효율성 증대
"""

import logging
from typing import List, Dict, Any
from .config import ATTACHMENT_SELECTION_CONFIG

logger = logging.getLogger(__name__)


def select_relevant_attachments(
    attachments: List[Dict[str, Any]], 
    content: str, 
    subject: str = ""
) -> List[Dict[str, Any]]:
    """
    첨부파일 중에서 티켓 내용과 가장 관련성이 높은 첨부파일을 선택
    
    **핵심 정책**: LLM이 선별한 1~3개만 상담원에게 노출
    - 전체 첨부파일 저장/노출 지양
    - 실제 문제 해결에 도움이 되는 파일만 선별
    - 리소스 절약 및 상담원 효율성 향상
    
    Args:
        attachments: 첨부파일 리스트
        content: 티켓 내용
        subject: 티켓 제목
        
    Returns:
        관련성이 높은 첨부파일 리스트 (최대 3개)
    """
    if not attachments:
        logger.debug("첨부파일이 없어 빈 리스트 반환")
        return []
    
    logger.info(f"첨부파일 선별 시작: 총 {len(attachments)}개 파일")
    
    # 콘텐츠 텍스트 전처리
    content_text = (content or "").lower()
    subject_text = (subject or "").lower()
    combined_text = f"{subject_text} {content_text}"
    
    # 각 첨부파일에 대해 관련성 점수 계산
    scored_attachments = []
    config = ATTACHMENT_SELECTION_CONFIG
    
    for att in attachments:
        if not isinstance(att, dict):
            logger.warning(f"잘못된 첨부파일 형식: {type(att)}")
            continue
            
        score = _calculate_attachment_relevance_score(att, combined_text, config)
        scored_attachments.append((score, att))
        
        logger.debug(f"파일 '{att.get('name', 'Unknown')}' 점수: {score}")
    
    # 점수 기준으로 정렬 (높은 점수부터)
    scored_attachments.sort(key=lambda x: x[0], reverse=True)
    
    # 엄격한 기준으로 필터링
    relevant_attachments = _apply_strict_filtering(scored_attachments, combined_text, config)
    
    logger.info(f"첨부파일 선별 완료: {len(relevant_attachments)}개 선택됨 "
                f"(전체 {len(attachments)}개 중 {len(relevant_attachments)/len(attachments)*100:.1f}%)")
    
    return relevant_attachments


def _calculate_attachment_relevance_score(
    attachment: Dict[str, Any], 
    combined_text: str, 
    config: Dict[str, Any]
) -> float:
    """첨부파일 관련성 점수 계산"""
    
    score = 0.0
    att_name = attachment.get('name', '').lower()
    att_type = attachment.get('content_type', '').lower()
    
    # 1. 파일명이 티켓에서 직접 언급되었는지 확인 (최고 점수)
    if att_name in combined_text or any(word in combined_text for word in att_name.split('.')):
        score += config['score_thresholds']['direct_mention']
        logger.debug(f"직접 언급 파일 발견: {att_name}")
    
    # 2. 파일 확장자별 중요도
    if att_name.endswith(tuple(config['extension_scores']['log_files'])):
        score += 4  # 로그 파일은 중요
    elif att_name.endswith(tuple(config['extension_scores']['image_files'])):
        score += 3  # 이미지 파일 (스크린샷 등)
    elif att_name.endswith(tuple(config['extension_scores']['document_files'])):
        score += 2  # 문서 파일
    elif att_name.endswith(tuple(config['extension_scores']['config_files'])):
        score += 3  # 설정 파일
    else:
        score += 1  # 기타 파일
    
    # 3. 콘텐츠 타입별 가중치
    for content_type, weight in config['content_type_weights'].items():
        if content_type in att_type:
            score += weight
            break
    
    # 4. 파일 크기 고려 (적절한 크기의 파일 선호)
    file_size = attachment.get('size', 0) or 0
    size_prefs = config['file_size_preferences']
    
    if size_prefs['optimal_min'] <= file_size <= size_prefs['optimal_max']:
        score += 1  # 적절한 크기
    elif file_size > size_prefs['too_large']:
        score -= 2  # 너무 큰 파일은 감점
    
    # 5. 중요 키워드가 파일명에 포함되어 있는지
    for keyword in config['important_keywords']:
        if keyword in att_name:
            score += 1
    
    return score


def _apply_strict_filtering(
    scored_attachments: List[tuple], 
    combined_text: str, 
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """엄격한 기준으로 첨부파일 필터링 - 실제 관련성이 있는 파일만 선택"""
    
    relevant_attachments = []
    thresholds = config['score_thresholds']
    
    # 전체 점수가 매우 낮으면 관련성 없다고 판단
    if not scored_attachments or scored_attachments[0][0] < thresholds['minimum_score']:
        logger.info("모든 첨부파일이 최소 관련성 기준 미달")
        return []
    
    # 최고 점수 파일이 직접 언급 수준 (10점 이상)인 경우
    if scored_attachments[0][0] >= thresholds['direct_mention']:
        relevant_attachments.append(scored_attachments[0][1])
        logger.info(f"직접 언급 파일 선택: {scored_attachments[0][1].get('name')}")
        
        # 추가 파일들도 매우 높은 기준 적용
        for score, att in scored_attachments[1:3]:
            if score >= thresholds['direct_mention']:
                relevant_attachments.append(att)
                logger.info(f"추가 직접 언급 파일 선택: {att.get('name')}")
    
    # 최고 점수가 높은 관련성 (7-9점)인 경우
    elif scored_attachments[0][0] >= thresholds['high_relevance']:
        first_att = scored_attachments[0][1]
        
        # 특정 타입의 파일이고 내용에 관련 키워드가 있는 경우만
        if (_is_important_file_type(first_att) and 
            _has_content_relevance(combined_text, config)):
            relevant_attachments.append(first_att)
            logger.info(f"높은 관련성 파일 선택: {first_att.get('name')}")
    
    # 중간 관련성 (5-6점)인 경우는 매우 제한적으로만 허용
    elif scored_attachments[0][0] >= thresholds['medium_relevance']:
        first_att = scored_attachments[0][1]
        att_name = first_att.get('name', '').lower()
        
        # 파일명에 중요한 키워드가 포함되어 있고, 로그나 설정 파일인 경우만
        if (any(keyword in att_name for keyword in config['important_keywords']) and
            _is_critical_file_type(first_att) and
            _has_content_relevance(combined_text, config)):
            relevant_attachments.append(first_att)
            logger.info(f"중간 관련성 파일 조건부 선택: {first_att.get('name')}")
    
    # 최대 개수 제한
    max_attachments = config['max_selected_attachments']
    if len(relevant_attachments) > max_attachments:
        relevant_attachments = relevant_attachments[:max_attachments]
        logger.info(f"첨부파일 개수를 {max_attachments}개로 제한")
    
    return relevant_attachments


def _is_important_file_type(attachment: Dict[str, Any]) -> bool:
    """중요한 파일 타입인지 확인 (이미지, 로그, 설정 파일 등)"""
    content_type = attachment.get('content_type', '').lower()
    name = attachment.get('name', '').lower()
    
    # 이미지 파일 (스크린샷 등)
    if content_type.startswith('image/'):
        return True
    
    # 로그, 설정 파일
    if name.endswith(('.log', '.yml', '.yaml', '.json', '.xml', '.txt')):
        return True
    
    return False


def _is_critical_file_type(attachment: Dict[str, Any]) -> bool:
    """매우 중요한 파일 타입인지 확인 (로그, 설정 파일만)"""
    name = attachment.get('name', '').lower()
    return name.endswith(('.log', '.yml', '.yaml', '.json', '.config'))


def _has_content_relevance(combined_text: str, config: Dict[str, Any]) -> bool:
    """티켓 내용과 최소한의 연관성이 있는지 확인"""
    content_keywords = config['content_keywords']
    return any(keyword in combined_text for keyword in content_keywords)


def get_attachment_summary_for_display(relevant_attachments: List[Dict[str, Any]]) -> str:
    """선별된 첨부파일을 요약 표시용 형식으로 변환"""
    if not relevant_attachments:
        return ""
    
    attachment_lines = []
    for att in relevant_attachments[:3]:  # 최대 3개
        filename = att.get('name', 'Unknown')
        attachment_lines.append(f"  - 📎 {filename}")
    
    return "\n".join(attachment_lines)


def log_attachment_selection_stats(
    original_count: int, 
    selected_count: int, 
    selection_reason: str = ""
) -> None:
    """첨부파일 선별 통계 로깅"""
    if original_count > 0:
        selection_rate = selected_count / original_count * 100
        logger.info(f"첨부파일 선별 통계: {selected_count}/{original_count} "
                   f"({selection_rate:.1f}%) 선택됨 {selection_reason}")
    else:
        logger.info("첨부파일 없음")


class AttachmentSelector:
    """
    Attachment selector class that wraps the selection functions
    """
    
    def __init__(self):
        self.config = ATTACHMENT_SELECTION_CONFIG
    
    def select_relevant_attachments(
        self,
        attachments: List[Dict[str, Any]], 
        content: str, 
        subject: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Select relevant attachments using the module function
        """
        return select_relevant_attachments(attachments, content, subject)
    
    def get_attachment_summary_for_display(self, relevant_attachments: List[Dict[str, Any]]) -> str:
        """
        Get attachment summary for display
        """
        return get_attachment_summary_for_display(relevant_attachments)
