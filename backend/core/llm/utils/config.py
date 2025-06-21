"""
설정 관리 모듈
"""

import os
import logging
from typing import Dict, Any, Optional
from ..models.providers import ProviderConfig
from ..models.base import LLMProvider

logger = logging.getLogger(__name__)


class ConfigManager:
    """LLM 설정 관리자"""
    
    def __init__(self):
        self.configs = self._load_configs()
    
    def _load_configs(self) -> Dict[str, Any]:
        """환경변수에서 설정 로드"""
        return {
            "timeouts": {
                "global": float(os.getenv("LLM_GLOBAL_TIMEOUT", "15.0")),
                "gemini": float(os.getenv("LLM_GEMINI_TIMEOUT", "20.0")),
                "anthropic": float(os.getenv("LLM_ANTHROPIC_TIMEOUT", "15.0")),
                "openai": float(os.getenv("LLM_OPENAI_TIMEOUT", "15.0")),
            },
            "models": {
                "light": os.getenv("LLM_LIGHT_MODEL", "gemini-1.5-flash"),
                "heavy": os.getenv("LLM_HEAVY_MODEL", "gemini-1.5-pro"),
            },
            "use_cases": {
                "summarization": {
                    "provider": os.getenv("SUMMARIZATION_MODEL_PROVIDER", "gemini"),
                    "model": os.getenv("SUMMARIZATION_MODEL_NAME", "gemini-1.5-flash"),
                    "max_tokens": int(os.getenv("SUMMARIZATION_MAX_TOKENS", "1000")),
                    "temperature": float(os.getenv("SUMMARIZATION_TEMPERATURE", "0.1"))
                },
                "realtime": {
                    "provider": os.getenv("REALTIME_MODEL_PROVIDER", "openai"),
                    "model": os.getenv("REALTIME_MODEL_NAME", "gpt-4o-mini"),
                    "max_tokens": int(os.getenv("REALTIME_MAX_TOKENS", "2000")),
                    "temperature": float(os.getenv("REALTIME_TEMPERATURE", "0.2"))
                }
            },
            "conversation_filtering": {
                "enabled": os.getenv("ENABLE_CONVERSATION_FILTERING", "true").lower() == "true",
                "mode": os.getenv("CONVERSATION_FILTERING_MODE", "conservative"),
                "token_budget": int(os.getenv("CONVERSATION_TOKEN_BUDGET", "12000")),
                "importance_threshold": float(os.getenv("CONVERSATION_IMPORTANCE_THRESHOLD", "0.4")),
            }
        }
    
    def get_provider_config(self, provider: LLMProvider) -> Optional[ProviderConfig]:
        """제공자 설정 반환"""
        provider_name = provider.value
        api_key = os.getenv(f"{provider_name.upper()}_API_KEY")
        
        if not api_key:
            return None
        
        return ProviderConfig(
            provider=provider,
            api_key=api_key,
            default_model=self._get_default_model(provider),
            timeout=int(self.configs["timeouts"].get(provider_name, self.configs["timeouts"]["global"])),
            enabled=True
        )
    
    def _get_default_model(self, provider: LLMProvider) -> str:
        """제공자별 기본 모델 반환"""
        defaults = {
            LLMProvider.OPENAI: "gpt-3.5-turbo",
            LLMProvider.ANTHROPIC: "claude-3-haiku-20240307", 
            LLMProvider.GEMINI: "gemini-1.5-flash-latest"
        }
        return defaults.get(provider, "unknown")
    
    def get_use_case_config(self, use_case: str) -> Optional[Dict[str, Any]]:
        """용도별 설정 반환"""
        return self.configs["use_cases"].get(use_case)
    
    def get_conversation_filter_config(self) -> Dict[str, Any]:
        """대화 필터링 설정 반환"""
        return self.configs["conversation_filtering"]
