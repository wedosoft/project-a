"""
로깅 시스템 공통 모듈 - 모든 백엔드 모듈에서 일관된 로깅을 위한 유틸리티
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


class ExtensionPreservingRotatingFileHandler(RotatingFileHandler):
    """
    확장자를 보존하는 회전 파일 핸들러
    
    기본 RotatingFileHandler는 'logfile.log.1' 형태로 백업 파일을 생성하지만,
    이 클래스는 'logfile.1.log' 형태로 확장자를 보존합니다.
    """
    
    def rotation_filename(self, default_name):
        """
        회전 파일명을 생성합니다.
        
        Args:
            default_name: 기본 파일명 (예: 'freshdesk_collection.log.1')
            
        Returns:
            str: 확장자가 보존되고 3자리 패딩된 파일명 (예: 'freshdesk_collection.001.log')
        """
        # 기본 파일명에서 파일명과 확장자 분리
        path = Path(default_name)
        
        # 파일명에서 '.숫자' 부분 추출
        # 예: 'freshdesk_collection.log.1' -> ['freshdesk_collection', 'log', '1']
        parts = path.name.split('.')
        
        if len(parts) >= 3:
            # 마지막 부분이 숫자라면 백업 파일 번호
            backup_number = parts[-1]
            extension = parts[-2]  # 확장자
            base_name = '.'.join(parts[:-2])  # 기본 파일명
            
            # 숫자를 3자리 패딩으로 포맷 (예: "1" -> "001")
            try:
                padded_number = str(int(backup_number)).zfill(3)
            except ValueError:
                # 숫자가 아닌 경우 원본 그대로 사용
                padded_number = backup_number
            
            # 새로운 형태로 재구성: 'basename.number.extension'
            new_filename = f"{base_name}.{padded_number}.{extension}"
            return str(path.parent / new_filename)
        
        # 기본값 반환 (예외 상황)
        return default_name

# 백엔드 루트 디렉토리 (backend/)
BACKEND_ROOT = Path(__file__).parent.parent

# 로그 파일 경로
LOG_FILE_PATH = BACKEND_ROOT / 'freshdesk_collection.log'
LOG_DIR = LOG_FILE_PATH.parent
LOG_DIR.mkdir(exist_ok=True)  # 로그 디렉토리가 없으면 생성

# 로그 설정 상수
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 10  # 최대 백업 파일 수
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_logger(
    name: str,
    log_file: str = None,
    level: int = logging.INFO,
    max_bytes: int = MAX_LOG_SIZE,
    backup_count: int = BACKUP_COUNT,
    console_output: bool = True
) -> logging.Logger:
    """
    공통 로거 설정 함수
    
    Args:
        name: 로거 이름
        log_file: 로그 파일 경로 (None이면 기본 경로 사용)
        level: 로그 레벨 (기본: INFO)
        max_bytes: 로그 파일 최대 크기 (기본: 5MB)
        backup_count: 백업 파일 최대 개수 (기본: 10개)
        console_output: 콘솔 출력 여부 (기본: True)
        
    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    logger = logging.getLogger(name)
    
    # 기존 핸들러 제거 (중복 방지)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(level)
    
    # 로그 포맷터 설정
    formatter = logging.Formatter(LOG_FORMAT)
    
    # 파일 핸들러 설정 (확장자 보존 회전 핸들러 사용)
    if log_file is None:
        log_file = LOG_FILE_PATH
    else:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = ExtensionPreservingRotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 콘솔 핸들러 설정
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_freshdesk_logger() -> logging.Logger:
    """
    Freshdesk 수집용 전용 로거 반환
    
    Returns:
        logging.Logger: Freshdesk 수집용 로거
    """
    return setup_logger(
        name='freshdesk_collection',
        log_file=BACKEND_ROOT / 'freshdesk_collection.log',
        max_bytes=MAX_LOG_SIZE,
        backup_count=BACKUP_COUNT
    )


def get_api_logger() -> logging.Logger:
    """
    API 서버용 전용 로거 반환
    
    Returns:
        logging.Logger: API 서버용 로거
    """
    return setup_logger(
        name='api_server',
        log_file=BACKEND_ROOT / 'api_server.log',
        max_bytes=MAX_LOG_SIZE,
        backup_count=BACKUP_COUNT
    )


def get_vectordb_logger() -> logging.Logger:
    """
    Vector DB 관련 전용 로거 반환
    
    Returns:
        logging.Logger: Vector DB용 로거
    """
    return setup_logger(
        name='vectordb',
        log_file=BACKEND_ROOT / 'vectordb.log',
        max_bytes=MAX_LOG_SIZE,
        backup_count=BACKUP_COUNT
    )


# 사용 예제:
# from core.logger import get_freshdesk_logger
# logger = get_freshdesk_logger()
# logger.info("Freshdesk 데이터 수집 시작")
