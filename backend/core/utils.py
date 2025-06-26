"""
유틸리티 함수 모듈

이 모듈은 애플리케이션 전체에서 사용되는 다양한 유틸리티 함수를 제공합니다.
재사용 가능한 헬퍼 함수, 데이터 변환, 로깅 등의 기능을 포함합니다.
"""

import hashlib
import json
import logging
import re
import time
import traceback
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union
from urllib.parse import urlparse

from pydantic import BaseModel

from core.config import settings

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))

# 타입 변수 정의
T = TypeVar('T')
R = TypeVar('R')


def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    지정된 이름과 레벨로 로거를 설정하고 반환합니다.
    
    Args:
        name: 로거 이름
        level: 로깅 레벨 (기본값은 설정에서 가져옴)
        
    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    logger_instance = logging.getLogger(name)
    log_level = getattr(logging, level or settings.LOG_LEVEL)
    logger_instance.setLevel(log_level)
    
    # 이미 핸들러가 설정되어 있지 않은 경우에만 추가
    if not logger_instance.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger_instance.addHandler(handler)
    
    return logger_instance


def timed(func: Callable[..., R]) -> Callable[..., R]:
    """
    함수 실행 시간을 측정하고 로깅하는 데코레이터입니다.
    
    Args:
        func: 측정할 함수
        
    Returns:
        Callable: 측정 로직이 추가된 래퍼 함수
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> R:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.debug(f"{func.__name__} 실행 시간: {elapsed_time:.4f}초")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"{func.__name__} 실행 중 오류 발생 (실행 시간: {elapsed_time:.4f}초): {str(e)}")
            raise
    
    return wrapper


def safe_execute(func: Callable[..., T], default_value: Optional[T] = None, log_error: bool = True) -> Callable[..., Optional[T]]:
    """
    함수를 안전하게 실행하고 오류 시 기본값을 반환하는 데코레이터입니다.
    
    Args:
        func: 실행할 함수
        default_value: 오류 시 반환할 기본값
        log_error: 오류를 로그에 기록할지 여부
        
    Returns:
        Callable: 안전하게 실행되는 래퍼 함수
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if log_error:
                logger.error(f"{func.__name__} 실행 중 오류 발생: {str(e)}")
                logger.debug(traceback.format_exc())
            return default_value
    
    return wrapper


def create_hash(data: Any) -> str:
    """
    데이터의 SHA-256 해시를 생성합니다.
    
    Args:
        data: 해시할 데이터 (문자열로 변환 가능해야 함)
        
    Returns:
        str: 16진수 해시 문자열
    """
    if isinstance(data, (dict, list, tuple, set)):
        data = json.dumps(data, sort_keys=True)
    elif not isinstance(data, str):
        data = str(data)
    
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    텍스트를 지정된 최대 길이로 자릅니다.
    
    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        suffix: 잘린 경우 추가할 접미사
        
    Returns:
        str: 잘린 텍스트
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def sanitize_html(html_content: str) -> str:
    """
    HTML 콘텐츠에서 모든 태그를 제거합니다.
    
    Args:
        html_content: HTML 콘텐츠
        
    Returns:
        str: 태그가 제거된 텍스트
    """
    # HTML 태그 제거
    clean_text = re.sub(r'<[^>]+>', '', html_content)
    # 연속된 공백 정리
    clean_text = re.sub(r'\s+', ' ', clean_text)
    # 앞뒤 공백 제거
    return clean_text.strip()


def utc_now() -> datetime:
    """
    현재 UTC 시간을 반환합니다.
    
    Returns:
        datetime: 현재 UTC 시간
    """
    return datetime.now(timezone.utc)


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    datetime 객체를 지정된 형식의 문자열로 변환합니다.
    
    Args:
        dt: 변환할 datetime 객체
        format_str: 날짜/시간 형식 문자열
        
    Returns:
        str: 형식화된 날짜/시간 문자열
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(format_str)


def parse_datetime(date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    문자열을 datetime 객체로 파싱합니다.
    
    Args:
        date_str: 파싱할 날짜/시간 문자열
        format_str: 날짜/시간 형식 문자열
        
    Returns:
        datetime: 파싱된 datetime 객체 (UTC 시간대)
    """
    dt = datetime.strptime(date_str, format_str)
    return dt.replace(tzinfo=timezone.utc)


def chunked_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """
    리스트를 지정된 크기의 청크로 분할합니다.
    
    Args:
        lst: 분할할 리스트
        chunk_size: 각 청크의 크기
        
    Returns:
        List[List[T]]: 청크 리스트
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def mask_sensitive_data(text: str) -> str:
    """
    민감한 데이터(이메일, 전화번호 등)를 마스킹합니다.
    
    Args:
        text: 원본 텍스트
        
    Returns:
        str: 마스킹된 텍스트
    """
    # 이메일 주소 마스킹
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    masked_text = re.sub(email_pattern, "[이메일 마스킹]", text)
    
    # 전화번호 마스킹 (다양한 형식 지원)
    phone_patterns = [
        r'\b(\d{3})[\s\.-]?(\d{3,4})[\s\.-]?(\d{4})\b',  # 010-1234-5678 형식
        r'\b(\+\d{1,3})[\s\.-]?(\d{2,3})[\s\.-]?(\d{3,4})[\s\.-]?(\d{4})\b',  # +82-10-1234-5678 형식
    ]
    
    for pattern in phone_patterns:
        masked_text = re.sub(pattern, "[전화번호 마스킹]", masked_text)
    
    # 주민등록번호 마스킹
    kr_id_pattern = r'\b\d{6}[\s\.-]?\d{7}\b'
    masked_text = re.sub(kr_id_pattern, "[주민번호 마스킹]", masked_text)
    
    # 카드번호 마스킹
    card_pattern = r'\b(?:\d{4}[\s\.-]?){3}\d{4}\b'
    masked_text = re.sub(card_pattern, "[카드번호 마스킹]", masked_text)
    
    return masked_text


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    """
    Pydantic 모델을 딕셔너리로 변환합니다.
    
    Args:
        model: 변환할 Pydantic 모델
        
    Returns:
        Dict[str, Any]: 변환된 딕셔너리
    """
    return model.dict()


def dict_to_model(data: Dict[str, Any], model_class: type) -> BaseModel:
    """
    딕셔너리를 Pydantic 모델로 변환합니다.
    
    Args:
        data: 변환할 딕셔너리
        model_class: 대상 Pydantic 모델 클래스
        
    Returns:
        BaseModel: 변환된 Pydantic 모델 인스턴스
    """
    return model_class(**data)


def extract_tenant_id(domain: str) -> str:
    """
    도메인에서 tenant_id를 자동으로 추출합니다.
    
    지침서에 따른 멀티테넌트 보안 요구사항:
    - wedosoft.freshdesk.com → "wedosoft"
    - company.zendesk.com → "company"
    
    Args:
        domain: 플랫폼 도메인 (예: wedosoft.freshdesk.com)
        
    Returns:
        str: 추출된 tenant_id
        
    Raises:
        ValueError: 유효하지 않은 도메인 형식인 경우
    """
    if not domain or not isinstance(domain, str):
        raise ValueError("도메인은 필수이며 문자열이어야 합니다")
    
    # URL이 포함된 경우 도메인만 추출
    if domain.startswith(('http://', 'https://')):
        parsed = urlparse(domain)
        domain = parsed.hostname or domain
    
    # 도메인 정규화 (소문자 변환, 공백 제거)
    domain = domain.lower().strip()
    
    # 지원되는 플랫폼 패턴
    platform_patterns = {
        'freshdesk': r'^([a-zA-Z0-9\-_]+)\.freshdesk\.com$',
        'zendesk': r'^([a-zA-Z0-9\-_]+)\.zendesk\.com$',
        # 향후 확장 가능
    }
    
    for platform, pattern in platform_patterns.items():
        match = re.match(pattern, domain)
        if match:
            tenant_id = match.group(1)
            # tenant_id 유효성 검증
            if not tenant_id or len(tenant_id) < 2:
                raise ValueError(f"추출된 tenant_id가 너무 짧습니다: {tenant_id}")
            logger.info(f"도메인 {domain}에서 tenant_id '{tenant_id}' 추출 완료 (플랫폼: {platform})")
            return tenant_id
    
    # 패턴이 맞지 않는 경우
    raise ValueError(f"지원되지 않는 도메인 형식입니다: {domain}")


def validate_company_platform(tenant_id: str, platform: str) -> bool:
    """
    tenant_id와 platform 조합의 유효성을 검증합니다.
    
    Args:
        tenant_id: 회사 식별자
        platform: 플랫폼 이름 (freshdesk, zendesk 등)
        
    Returns:
        bool: 유효한 조합인지 여부
    """
    if not tenant_id or not platform:
        return False
    
    # tenant_id 형식 검증 (영숫자, 하이픈, 언더스코어만 허용)
    if not re.match(r'^[a-zA-Z0-9\-_]{2,50}$', tenant_id):
        logger.error(f"유효하지 않은 tenant_id 형식: {tenant_id}")
        return False
    
    # 지원되는 플랫폼 목록
    supported_platforms = ['freshdesk', 'zendesk']
    if platform not in supported_platforms:
        logger.error(f"지원되지 않는 플랫폼: {platform}")
        return False
    
    return True


def build_domain_from_tenant_id(tenant_id: str, platform: str) -> str:
    """
    tenant_id와 platform으로 도메인을 재구성합니다.
    
    Args:
        tenant_id: 회사 식별자
        platform: 플랫폼 이름
        
    Returns:
        str: 재구성된 도메인
        
    Raises:
        ValueError: 유효하지 않은 입력인 경우
    """
    if not validate_company_platform(tenant_id, platform):
        raise ValueError(f"유효하지 않은 tenant_id 또는 platform: {tenant_id}, {platform}")
    
    domain_templates = {
        'freshdesk': f"{tenant_id}.freshdesk.com",
        'zendesk': f"{tenant_id}.zendesk.com",
    }
    
    if platform not in domain_templates:
        raise ValueError(f"지원되지 않는 플랫폼: {platform}")
    
    return domain_templates[platform]


# ==================== HTML 파싱 및 인라인 이미지 처리 ====================

try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False
    logger.warning("BeautifulSoup4가 설치되지 않았습니다. HTML 파싱 기능이 제한됩니다.")


def extract_attachment_id_from_url(url: str) -> Optional[int]:
    """
    Freshdesk 첨부파일 URL에서 attachment_id를 추출합니다.
    
    Args:
        url: Freshdesk 첨부파일 URL
        
    Returns:
        추출된 attachment_id 또는 None
        
    Example:
        URL: "https://company.freshdesk.com/helpdesk/attachments/12345678901"
        Returns: 12345678901
    """
    try:
        # Freshdesk 첨부파일 URL 패턴들
        patterns = [
            r'/attachments/(\d+)',           # 일반적인 패턴
            r'attachment_id=(\d+)',          # 쿼리 파라미터
            r'/helpdesk/attachments/(\d+)',  # 헬프데스크 패턴
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return int(match.group(1))
        
        # URL 파싱으로 쿼리 파라미터 확인
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        if 'attachment_id' in query_params:
            return int(query_params['attachment_id'][0])
            
    except (ValueError, IndexError) as e:
        logger.warning(f"첨부파일 ID 추출 실패: {url} - {e}")
    
    return None


def extract_inline_images_from_html(html_content: str) -> List[Dict[str, Any]]:
    """
    HTML 콘텐츠에서 인라인 이미지 정보를 추출합니다.
    
    Args:
        html_content: HTML 형태의 티켓 본문 또는 대화 내용
        
    Returns:
        인라인 이미지 정보 리스트
        
    Example:
        [
            {
                "attachment_id": 12345,
                "alt_text": "스크린샷",
                "type": "inline",
                "src_url": "https://...",
                "position": 0
            }
        ]
    """
    if not html_content or not isinstance(html_content, str):
        return []
    
    inline_images = []
    
    if HAS_BEAUTIFULSOUP:
        # BeautifulSoup을 사용한 정확한 파싱
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for position, img in enumerate(soup.find_all('img')):
                src = img.get('src', '').strip()
                alt = img.get('alt', '').strip()
                
                # Freshdesk 첨부파일인지 확인
                if src and ('freshdesk.com' in src or 'attachments' in src):
                    attachment_id = extract_attachment_id_from_url(src)
                    
                    if attachment_id:
                        inline_images.append({
                            "attachment_id": attachment_id,
                            "alt_text": alt,
                            "type": "inline",
                            "src_url": src,  # 임시 저장 (나중에 제거됨)
                            "position": position,
                            "tag_attributes": dict(img.attrs)  # 추가 속성들
                        })
                        
        except Exception as e:
            logger.warning(f"BeautifulSoup 파싱 실패, 정규식 사용: {e}")
            # 실패 시 정규식으로 fallback
            inline_images = _extract_images_with_regex(html_content)
    else:
        # BeautifulSoup이 없는 경우 정규식 사용
        inline_images = _extract_images_with_regex(html_content)
    
    logger.debug(f"HTML에서 {len(inline_images)}개의 인라인 이미지 추출됨")
    return inline_images


def _extract_images_with_regex(html_content: str) -> List[Dict[str, Any]]:
    """
    정규식을 사용하여 HTML에서 이미지 태그를 추출합니다.
    
    Args:
        html_content: HTML 콘텐츠
        
    Returns:
        인라인 이미지 정보 리스트
    """
    inline_images = []
    
    # img 태그 패턴 (src와 alt 속성 추출)
    img_pattern = r'<img[^>]*src=["\']([^"\']*)["\'][^>]*(?:alt=["\']([^"\']*)["\'][^>]*)?>'
    
    for position, match in enumerate(re.finditer(img_pattern, html_content, re.IGNORECASE)):
        src = match.group(1).strip()
        alt = match.group(2).strip() if match.group(2) else ""
        
        # Freshdesk 첨부파일인지 확인
        if src and ('freshdesk.com' in src or 'attachments' in src):
            attachment_id = extract_attachment_id_from_url(src)
            
            if attachment_id:
                inline_images.append({
                    "attachment_id": attachment_id,
                    "alt_text": alt,
                    "type": "inline",
                    "src_url": src,  # 임시 저장 (나중에 제거됨)
                    "position": position
                })
    
    return inline_images


def sanitize_inline_image_metadata(inline_images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    인라인 이미지 메타데이터에서 URL을 제거하고 안전한 정보만 보존합니다.
    
    Args:
        inline_images: 원본 인라인 이미지 정보 리스트
        
    Returns:
        URL이 제거된 안전한 메타데이터 리스트
    """
    sanitized = []
    
    for img in inline_images:
        # URL 제거하고 안전한 메타데이터만 보존
        safe_metadata = {
            "attachment_id": img.get("attachment_id"),
            "alt_text": img.get("alt_text", ""),
            "type": "inline",
            "position": img.get("position", 0),
            # src_url은 저장하지 않음 (보안상 위험)
        }
        
        # 추가 속성이 있으면 필요한 것만 선별적으로 추가
        if "tag_attributes" in img:
            attrs = img["tag_attributes"]
            # 안전한 속성들만 추가
            safe_attrs = {}
            for key in ["width", "height", "title", "class"]:
                if key in attrs:
                    safe_attrs[key] = attrs[key]
            
            if safe_attrs:
                safe_metadata["attributes"] = safe_attrs
        
        sanitized.append(safe_metadata)
    
    return sanitized


def extract_text_content_from_html(html_content: str) -> str:
    """
    HTML에서 순수 텍스트 내용만 추출합니다.
    
    Args:
        html_content: HTML 콘텐츠
        
    Returns:
        HTML 태그가 제거된 순수 텍스트
    """
    if not html_content:
        return ""
    
    if HAS_BEAUTIFULSOUP:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        except Exception as e:
            logger.warning(f"BeautifulSoup 텍스트 추출 실패, 정규식 사용: {e}")
    
    # 정규식으로 HTML 태그 제거 (기존 sanitize_html 함수와 유사하지만 개선됨)
    text = re.sub(r'<[^>]+>', ' ', html_content)
    # 여러 공백을 하나로 통합
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def count_inline_images_in_html(html_content: str) -> int:
    """
    HTML 콘텐츠 내 인라인 이미지 개수를 빠르게 계산합니다.
    
    Args:
        html_content: HTML 콘텐츠
        
    Returns:
        인라인 이미지 개수
    """
    if not html_content:
        return 0
    
    # Freshdesk 첨부파일 이미지만 카운트
    pattern = r'<img[^>]*src=["\'][^"\']*(?:freshdesk\.com|attachments)[^"\']*["\'][^>]*>'
    return len(re.findall(pattern, html_content, re.IGNORECASE))
