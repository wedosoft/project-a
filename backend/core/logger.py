"""
로깅 시스템 공통 모듈 - 모든 백엔드 모듈에서 일관된 로깅을 위한 유틸리티
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 백엔드 루트 디렉토리 (backend/)
BACKEND_ROOT = Path(__file__).parent.parent

# 로그 파일 경로
LOG_FILE_PATH = BACKEND_ROOT / 'freshdesk_collection.log'
LOG_DIR = LOG_FILE_PATH.parent
LOG_DIR.mkdir(exist_ok=True)  # 로그 디렉토리가 없으면 생성

# 로그 설정 상수
MAX_LOG_SIZE = 5 * 1024 * 1024  # 각 로그 파일의 최대 크기 (5MB)
BACKUP_COUNT = 10  # 백업 파일 수 (최대 10개의 순환 로그 파일 보관)
LOG_LEVEL = logging.INFO  # 기본 로그 레벨
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_logging():
    """
    전역 로깅 시스템을 설정합니다. (회전 로그 파일 및 콘솔 출력)
    """
    # 로그 핸들러 설정 - 로그 회전 적용
    file_handler = RotatingFileHandler(
        filename=str(LOG_FILE_PATH), 
        maxBytes=MAX_LOG_SIZE, 
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    
    # 기본 로깅 설정
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[file_handler, console_handler],
        force=True  # 기존 로깅 설정 강제 재설정
    )
    
    return logging.getLogger(__name__)


def get_logger(name):
    """
    모듈별 로거를 반환합니다.
    
    Args:
        name: 일반적으로 __name__을 사용하여 모듈명 전달
        
    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    return logging.getLogger(name)


# 모듈 임포트 시 자동으로 로깅 설정
setup_logging()

if __name__ == "__main__":
    # 테스트 코드
    logger = get_logger("logging_test")
    logger.info("로깅 시스템 테스트")
    logger.warning("경고 메시지 테스트")
    logger.error("오류 메시지 테스트")
    
    print(f"로그 파일 경로: {LOG_FILE_PATH}")
    print(f"최대 로그 파일 크기: {MAX_LOG_SIZE/1024/1024}MB")
    print(f"백업 로그 파일 수: {BACKUP_COUNT}")
