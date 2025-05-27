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
