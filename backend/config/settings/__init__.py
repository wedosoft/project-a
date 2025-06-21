"""
설정 관리 모듈

환경별 설정을 로드하고 관리합니다.
"""

import os
from .base import DEFAULT_SETTINGS, ENV_SETTINGS_MAP
from .development import DEVELOPMENT_SETTINGS
from .production import PRODUCTION_SETTINGS
from .testing import TESTING_SETTINGS

# 환경별 설정 매핑
SETTINGS_MAP = {
    "development": DEVELOPMENT_SETTINGS,
    "production": PRODUCTION_SETTINGS,
    "testing": TESTING_SETTINGS
}

def get_settings(environment: str = None):
    """
    환경에 맞는 설정을 반환합니다.
    
    Args:
        environment: 환경명 (development, production, testing)
        
    Returns:
        설정 딕셔너리
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")
    
    # 환경명 매핑
    environment = ENV_SETTINGS_MAP.get(environment, environment)
    
    # 설정 반환
    return SETTINGS_MAP.get(environment, DEVELOPMENT_SETTINGS)

def get_config_data_path(filename: str) -> str:
    """
    설정 데이터 파일의 경로를 반환합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        파일 경로
    """
    from .base import CONFIG_DATA_DIR
    return str(CONFIG_DATA_DIR / filename)

__all__ = [
    "get_settings",
    "get_config_data_path",
    "DEFAULT_SETTINGS",
    "DEVELOPMENT_SETTINGS", 
    "PRODUCTION_SETTINGS",
    "TESTING_SETTINGS"
]
