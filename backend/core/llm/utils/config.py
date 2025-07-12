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
        """환경변수에서 설정 로드 - 모델 레지스트리 통합"""
        # 새로운 constants에서 모델 설정 가져오기
        from core.constants import ModelConfig, ConversationFilterConfig, APILimits
        
        # 모델 레지스트리에서 환경별 기본값 가져오기
        try:
            from ..registry import get_model_registry
            registry = get_model_registry()
            environment = os.getenv('ENVIRONMENT', 'development')
            env_config = registry.get_environment_config(environment)
        except:
            env_config = None
        
        # 레지스트리 기반 기본값 설정
        if env_config:
            default_provider = env_config.default_provider
            default_chat_model = env_config.default_chat_model
            default_embedding_model = env_config.default_embedding_model
        else:
            # 폴백 기본값
            default_provider = "gemini"
            default_chat_model = "gemini-1.5-flash"
            default_embedding_model = "text-embedding-3-large"
        
        return {
            "timeouts": {
                "global": float(os.getenv("LLM_GLOBAL_TIMEOUT", "15.0")),
                "gemini": float(os.getenv("LLM_GEMINI_TIMEOUT", "20.0")),
                "anthropic": float(os.getenv("LLM_ANTHROPIC_TIMEOUT", "15.0")),
                "openai": float(os.getenv("LLM_OPENAI_TIMEOUT", "15.0")),
            },
            "models": {
                "light": os.getenv("LLM_LIGHT_MODEL", default_chat_model),
                "heavy": os.getenv("LLM_HEAVY_MODEL", "gemini-1.5-pro"),
            },
            "use_cases": {
                # 메인 티켓 요약 (새로운 환경변수 사용)
                "ticket_view": {
                    "provider": self._extract_provider(ModelConfig.MAIN_TICKET_MODEL),
                    "model": self._extract_model_name(ModelConfig.MAIN_TICKET_MODEL),
                    "max_tokens": ModelConfig.MAIN_TICKET_MAX_TOKENS,
                    "temperature": ModelConfig.MAIN_TICKET_TEMPERATURE
                },
                # 유사 티켓 요약
                "ticket_similar": {
                    "provider": self._extract_provider(ModelConfig.SIMILAR_TICKET_MODEL),
                    "model": self._extract_model_name(ModelConfig.SIMILAR_TICKET_MODEL),
                    "max_tokens": ModelConfig.SIMILAR_TICKET_MAX_TOKENS,
                    "temperature": ModelConfig.SIMILAR_TICKET_TEMPERATURE
                },
                # 레거시 호환성을 위한 summarization
                "summarization": {
                    "provider": self._extract_provider(ModelConfig.MAIN_TICKET_MODEL),
                    "model": self._extract_model_name(ModelConfig.MAIN_TICKET_MODEL),
                    "max_tokens": ModelConfig.MAIN_TICKET_MAX_TOKENS,
                    "temperature": ModelConfig.MAIN_TICKET_TEMPERATURE
                },
                # 쿼리 응답
                "question_answering": {
                    "provider": self._extract_provider(ModelConfig.QUERY_RESPONSE_MODEL),
                    "model": self._extract_model_name(ModelConfig.QUERY_RESPONSE_MODEL),
                    "max_tokens": ModelConfig.QUERY_RESPONSE_MAX_TOKENS,
                    "temperature": ModelConfig.QUERY_RESPONSE_TEMPERATURE
                },
                # 대화형 채팅 (쿼리 응답과 동일 설정 사용)
                "chat": {
                    "provider": self._extract_provider(ModelConfig.QUERY_RESPONSE_MODEL),
                    "model": self._extract_model_name(ModelConfig.QUERY_RESPONSE_MODEL),
                    "max_tokens": ModelConfig.QUERY_RESPONSE_MAX_TOKENS,
                    "temperature": ModelConfig.QUERY_RESPONSE_TEMPERATURE
                },
                # 분석 (쿼리 응답과 동일하지만 더 많은 토큰)
                "analysis": {
                    "provider": self._extract_provider(ModelConfig.QUERY_RESPONSE_MODEL),
                    "model": self._extract_model_name(ModelConfig.QUERY_RESPONSE_MODEL),
                    "max_tokens": 4000,  # 분석은 더 긴 응답 필요
                    "temperature": ModelConfig.QUERY_RESPONSE_TEMPERATURE
                },
                "embedding": {
                    "provider": os.getenv("EMBEDDING_MODEL_PROVIDER", "openai"),
                    "model": os.getenv("EMBEDDING_MODEL_NAME", default_embedding_model),
                    "dimensions": int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))
                },
                # 실시간 처리 (메인 티켓과 동일)
                "realtime": {
                    "provider": self._extract_provider(ModelConfig.MAIN_TICKET_MODEL),
                    "model": self._extract_model_name(ModelConfig.MAIN_TICKET_MODEL),
                    "max_tokens": ModelConfig.MAIN_TICKET_MAX_TOKENS,
                    "temperature": ModelConfig.MAIN_TICKET_TEMPERATURE
                },
                # 배치 처리 (유사 티켓과 동일)
                "batch": {
                    "provider": self._extract_provider(ModelConfig.SIMILAR_TICKET_MODEL),
                    "model": self._extract_model_name(ModelConfig.SIMILAR_TICKET_MODEL),
                    "max_tokens": ModelConfig.SIMILAR_TICKET_MAX_TOKENS,
                    "temperature": ModelConfig.SIMILAR_TICKET_TEMPERATURE
                },
                # 대화 필터링
                "conversation_filter": {
                    "provider": self._extract_provider(ModelConfig.CONVERSATION_FILTER_MODEL),
                    "model": self._extract_model_name(ModelConfig.CONVERSATION_FILTER_MODEL),
                    "max_tokens": ModelConfig.CONVERSATION_FILTER_MAX_TOKENS,
                    "temperature": ModelConfig.CONVERSATION_FILTER_TEMPERATURE
                }
            },
            "conversation_filtering": {
                "enabled": ConversationFilterConfig.ENABLED,
                "mode": ConversationFilterConfig.FILTERING_MODE,
                "token_budget": ConversationFilterConfig.TOKEN_BUDGET,
                "importance_threshold": ConversationFilterConfig.IMPORTANCE_THRESHOLD,
            }
        }
    
    def _extract_provider(self, model_string: str) -> str:
        """모델 문자열에서 프로바이더 추출 (예: 'openai/gpt-4' -> 'openai')"""
        if "/" in model_string:
            return model_string.split("/")[0]
        # 기본 프로바이더 추론
        if model_string.startswith("gpt"):
            return "openai"
        elif model_string.startswith("claude"):
            return "anthropic"
        elif model_string.startswith("gemini"):
            return "gemini"
        return "openai"  # 기본값
    
    def _extract_model_name(self, model_string: str) -> str:
        """모델 문자열에서 모델명 추출 (예: 'openai/gpt-4' -> 'gpt-4')"""
        if "/" in model_string:
            return model_string.split("/")[1]
        return model_string
    
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
        """제공자별 기본 모델 반환 - 레지스트리 기반"""
        try:
            from ..registry import get_model_registry
            registry = get_model_registry()
            
            # 환경별 기본 모델 확인
            environment = os.getenv('ENVIRONMENT', 'development')
            env_config = registry.get_environment_config(environment)
            
            if env_config:
                if provider.value == env_config.default_provider:
                    return env_config.default_chat_model
                elif provider == LLMProvider.OPENAI and provider.value != env_config.default_provider:
                    return env_config.default_embedding_model
            
            # 레지스트리에서 활성 모델 찾기
            available_models = registry.get_available_models(provider=provider.value)
            for model_spec in available_models:
                if not model_spec.deprecated:
                    return model_spec.name
                    
        except Exception as e:
            logger.warning(f"레지스트리에서 기본 모델 조회 실패: {e}")
        
        # 폴백 기본값
        defaults = {
            LLMProvider.OPENAI: "gpt-3.5-turbo",
            LLMProvider.ANTHROPIC: "claude-3-haiku-20240307", 
            LLMProvider.GEMINI: "gemini-1.5-flash-latest"
        }
        return defaults.get(provider, "unknown")
    
    def get_use_case_config(self, use_case: str) -> Optional[Dict[str, Any]]:
        """용도별 설정 반환"""
        return self.configs["use_cases"].get(use_case)
    
    def get_model_for_use_case(self, use_case: str) -> tuple[LLMProvider, str]:
        """
        Use Case에 따른 자동 모델 선택 - LangChain 핵심 장점!
        
        Args:
            use_case: "realtime", "summarization", "batch" 등
            
        Returns:
            (provider, model_name) 튜플
        """
        config = self.get_use_case_config(use_case)
        if not config:
            # 기본값 반환
            return LLMProvider.OPENAI, "gpt-3.5-turbo"
        
        provider_name = config.get("provider", "openai")
        model_name = config.get("model", "gpt-3.5-turbo")
        
        # 레지스트리에서 모델 검증 및 deprecation 확인
        try:
            from ..registry import get_model_registry
            registry = get_model_registry()
            
            model_spec = registry.get_model(provider_name, model_name)
            if model_spec:
                if model_spec.deprecated:
                    logger.warning(f"Model {model_name} is deprecated. Replacement: {model_spec.replacement}")
                    # 대체 모델이 있다면 자동으로 사용
                    if model_spec.replacement:
                        replacement_model = registry.get_model(provider_name, model_spec.replacement)
                        if replacement_model and not replacement_model.deprecated:
                            logger.info(f"Auto-migrating from {model_name} to {model_spec.replacement}")
                            model_name = model_spec.replacement
            else:
                logger.warning(f"Model {provider_name}:{model_name} not found in registry")
        except Exception as e:
            logger.debug(f"Registry validation skipped: {e}")
        
        # 문자열을 LLMProvider enum으로 변환
        provider_map = {
            "openai": LLMProvider.OPENAI,
            "anthropic": LLMProvider.ANTHROPIC,
            "gemini": LLMProvider.GEMINI
        }
        
        provider = provider_map.get(provider_name.lower(), LLMProvider.OPENAI)
        return provider, model_name
    
    def get_conversation_filter_config(self) -> Dict[str, Any]:
        """대화 필터링 설정 반환"""
        return self.configs["conversation_filtering"]
