"""
모델 설정 관리자

용도별 LLM 모델 설정을 관리합니다.
"""

import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ModelConfigManager:
    """용도별 모델 설정을 관리하는 클래스"""
    
    def __init__(self):
        self.summarization_config = {}
        self.realtime_config = {}
        self._load_configurations()
    
    def _load_configurations(self):
        """용도별 모델 설정을 환경변수에서 로드"""
        # 티켓 요약 및 임베딩용 모델 설정
        self.summarization_config = {
            "provider": os.getenv("SUMMARIZATION_MODEL_PROVIDER", "gemini"),
            "model": os.getenv("SUMMARIZATION_MODEL_NAME", "gemini-1.5-flash"),
            "max_tokens": int(os.getenv("SUMMARIZATION_MAX_TOKENS", "1000")),
            "temperature": float(os.getenv("SUMMARIZATION_TEMPERATURE", "0.1"))
        }
        
        # 실시간 상담원 쿼리용 모델 설정
        self.realtime_config = {
            "provider": os.getenv("REALTIME_MODEL_PROVIDER", "openai"),
            "model": os.getenv("REALTIME_MODEL_NAME", "gpt-4o-mini"),
            "max_tokens": int(os.getenv("REALTIME_MAX_TOKENS", "2000")),
            "temperature": float(os.getenv("REALTIME_TEMPERATURE", "0.2"))
        }
        
        logger.info(f"모델 설정 로드 완료 - 요약용: {self.summarization_config}, 실시간: {self.realtime_config}")
    
    def get_config_for_use_case(self, use_case: str) -> Optional[Dict[str, Any]]:
        """용도에 따른 모델 설정 반환"""
        if use_case == "summarization":
            return self.summarization_config
        elif use_case == "realtime":
            return self.realtime_config
        else:
            return None  # 기본 설정 사용
    
    def reload_configs(self):
        """설정을 다시 로드 (환경변수 변경 시)"""
        self._load_configurations()
