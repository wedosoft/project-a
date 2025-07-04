"""
유연한 LLM 매니저 - 모델 레지스트리와 LangChain 기반 

기존 manager.py의 하드코딩된 모델명을 대체하여 
완전히 유연한 모델 교체가 가능한 시스템입니다.
"""

import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from cachetools import TTLCache
from langchain.llms.base import LLM
from langchain.chat_models.base import BaseChatModel
from langchain.schema import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain.embeddings.base import Embeddings
from langchain.callbacks.manager import CallbackManagerForLLMRun
import asyncio

from .registry import get_model_registry, ModelRegistry, ModelType, CostTier, SpeedTier
from .models.base import LLMProvider, LLMRequest, LLMResponse
from .providers import OpenAIProvider, AnthropicProvider, GeminiProvider
from .utils.config import ConfigManager
from .utils.routing import ProviderRouter
from .utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class FlexibleLLMManager:
    """
    유연한 LLM 매니저 - 모델 레지스트리와 LangChain 완전 통합
    
    특징:
    1. 모델 레지스트리 기반 동적 모델 선택
    2. 환경별 설정 자동 적용
    3. Use case 기반 자동 라우팅
    4. 모델 deprecation 자동 대응
    5. LangChain 추상화 계층 활용
    """
    
    def __init__(self):
        self.registry = get_model_registry()
        self.config_manager = ConfigManager()
        self.router = ProviderRouter()
        self.metrics = MetricsCollector()
        
        # 환경 설정
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.env_config = self.registry.get_environment_config(self.environment)
        
        # 캐시
        self.response_cache = TTLCache(maxsize=1000, ttl=3600)
        self.embedding_cache = TTLCache(maxsize=1000, ttl=3600)
        
        # Provider 인스턴스들
        self.providers: Dict[str, Any] = {}
        self.langchain_models: Dict[str, BaseChatModel] = {}
        
        # 초기화
        self._initialize_providers()
        
        logger.info(f"FlexibleLLMManager 초기화 완료 - 환경: {self.environment}")
    
    def _initialize_providers(self):
        """레지스트리 기반 동적 제공자 초기화"""
        available_models = self.registry.get_available_models()
        
        # 제공자별 그룹화
        providers_by_name = {}
        for model_spec in available_models:
            if model_spec.provider not in providers_by_name:
                providers_by_name[model_spec.provider] = []
            providers_by_name[model_spec.provider].append(model_spec)
        
        # 각 제공자 초기화
        for provider_name, models in providers_by_name.items():
            try:
                self._initialize_provider(provider_name, models)
            except Exception as e:
                logger.error(f"Provider {provider_name} 초기화 실패: {e}")
    
    def _initialize_provider(self, provider_name: str, models: List[Any]):
        """개별 제공자 초기화"""
        # API 키 확인
        api_key = self._get_api_key(provider_name)
        if not api_key:
            logger.warning(f"API key not found for provider: {provider_name}")
            return
        
        # 레거시 provider 초기화
        if provider_name == "openai":
            self.providers[provider_name] = OpenAIProvider(api_key)
        elif provider_name == "anthropic":
            self.providers[provider_name] = AnthropicProvider(api_key)
        elif provider_name == "gemini":
            self.providers[provider_name] = GeminiProvider(api_key)
        
        # LangChain 모델 초기화
        self._initialize_langchain_models(provider_name, models, api_key)
        
        logger.info(f"Provider {provider_name} 초기화 완료 - 모델 수: {len(models)}")
    
    def _initialize_langchain_models(self, provider_name: str, models: List[Any], api_key: str):
        """LangChain 모델 초기화"""
        for model_spec in models:
            if model_spec.deprecated:
                continue
                
            try:
                langchain_model = self._create_langchain_model(
                    provider_name, 
                    model_spec.name, 
                    api_key
                )
                
                if langchain_model:
                    model_key = f"{provider_name}:{model_spec.name}"
                    self.langchain_models[model_key] = langchain_model
                    
            except Exception as e:
                logger.error(f"LangChain 모델 {model_spec.name} 초기화 실패: {e}")
    
    def _create_langchain_model(self, provider_name: str, model_name: str, api_key: str) -> Optional[BaseChatModel]:
        """LangChain 모델 인스턴스 생성"""
        try:
            if provider_name == "openai":
                from langchain.chat_models import ChatOpenAI
                return ChatOpenAI(
                    model=model_name,
                    openai_api_key=api_key,
                    temperature=0.1
                )
            elif provider_name == "anthropic":
                from langchain.chat_models import ChatAnthropic
                return ChatAnthropic(
                    model=model_name,
                    anthropic_api_key=api_key,
                    temperature=0.1
                )
            elif provider_name == "gemini":
                from langchain.chat_models import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(
                    model=model_name,
                    google_api_key=api_key,
                    temperature=0.1
                )
        except ImportError as e:
            logger.error(f"LangChain {provider_name} 모듈 가져오기 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"LangChain {provider_name} 모델 생성 실패: {e}")
            return None
    
    def _get_api_key(self, provider_name: str) -> Optional[str]:
        """제공자별 API 키 조회"""
        # 모델 레지스트리에서 환경변수명 확인
        available_models = self.registry.get_available_models(provider=provider_name)
        if not available_models:
            return None
            
        # 환경변수명 매핑
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY", 
            "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"]
        }
        
        env_vars = env_var_map.get(provider_name, [])
        if isinstance(env_vars, str):
            env_vars = [env_vars]
            
        for env_var in env_vars:
            api_key = os.getenv(env_var)
            if api_key:
                return api_key
        
        return None
    
    def get_model_for_use_case(self, use_case: str, 
                              cost_limit: Optional[CostTier] = None,
                              speed_requirement: Optional[SpeedTier] = None) -> Optional[Tuple[str, str]]:
        """Use case에 최적화된 모델 선택"""
        # 1. 레지스트리에서 우선순위 모델 확인
        best_model = self.registry.get_best_model_for_use_case(
            use_case=use_case,
            cost_limit=cost_limit,
            speed_requirement=speed_requirement
        )
        
        if best_model:
            return best_model
        
        # 2. 환경 설정 기본값 사용
        if self.env_config:
            if use_case == "embedding":
                return ("openai", self.env_config.default_embedding_model)
            else:
                return (self.env_config.default_provider, self.env_config.default_chat_model)
        
        # 3. 폴백: 사용 가능한 첫 번째 모델
        available_models = self.registry.get_available_models()
        for model_spec in available_models:
            if not model_spec.deprecated:
                return (model_spec.provider, model_spec.name)
        
        return None
    
    def get_langchain_model(self, provider: str, model: str) -> Optional[BaseChatModel]:
        """LangChain 모델 인스턴스 조회"""
        model_key = f"{provider}:{model}"
        return self.langchain_models.get(model_key)
    
    async def generate_with_use_case(self, 
                                   use_case: str,
                                   messages: List[Dict[str, str]],
                                   **kwargs) -> LLMResponse:
        """Use case 기반 텍스트 생성"""
        # 1. 최적 모델 선택
        model_selection = self.get_model_for_use_case(use_case)
        if not model_selection:
            raise RuntimeError(f"No available model for use case: {use_case}")
        
        provider, model_name = model_selection
        
        # 2. 모델 deprecation 확인
        model_spec = self.registry.get_model(provider, model_name)
        if model_spec and model_spec.deprecated:
            logger.warning(f"Model {model_name} is deprecated")
            
            # 자동 마이그레이션 시도
            if model_spec.replacement:
                replacement_model = self.registry.get_model(provider, model_spec.replacement)
                if replacement_model and not replacement_model.deprecated:
                    logger.info(f"Auto-migrating from {model_name} to {model_spec.replacement}")
                    model_name = model_spec.replacement
                    model_spec = replacement_model
        
        # 3. Use case 요구사항 검증
        if not self.registry.validate_model_compatibility(provider, model_name, use_case):
            logger.warning(f"Model {model_name} may not be optimal for use case {use_case}")
        
        # 4. LangChain 모델 사용 가능 여부 확인
        langchain_model = self.get_langchain_model(provider, model_name)
        if langchain_model:
            return await self._generate_with_langchain(
                langchain_model, messages, model_spec, **kwargs
            )
        
        # 5. 레거시 provider 사용
        if provider in self.providers:
            request = LLMRequest(
                messages=messages,
                model=model_name,
                **kwargs
            )
            return await self.providers[provider].generate(request)
        
        raise RuntimeError(f"No provider available for {provider}")
    
    async def _generate_with_langchain(self, 
                                     langchain_model: BaseChatModel, 
                                     messages: List[Dict[str, str]], 
                                     model_spec: Any,
                                     **kwargs) -> LLMResponse:
        """LangChain 모델을 사용한 텍스트 생성"""
        try:
            # 메시지 포맷 변환
            langchain_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    langchain_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
                else:
                    langchain_messages.append(HumanMessage(content=content))
            
            # 생성 실행
            response = await langchain_model.agenerate([langchain_messages])
            
            # 응답 변환
            if response.generations and response.generations[0]:
                content = response.generations[0][0].text
                return LLMResponse(
                    provider=LLMProvider.OPENAI,  # 임시값
                    model=model_spec.name,
                    content=content,
                    success=True
                )
            else:
                return LLMResponse(
                    provider=LLMProvider.OPENAI,  # 임시값
                    model=model_spec.name,
                    content="",
                    success=False,
                    error="Empty response"
                )
                
        except Exception as e:
            return LLMResponse(
                provider=LLMProvider.OPENAI,  # 임시값
                model=model_spec.name,
                content="",
                success=False,
                error=str(e)
            )
    
    def get_available_models_for_use_case(self, use_case: str) -> List[Tuple[str, str]]:
        """Use case에 사용 가능한 모든 모델 목록"""
        return self.registry.get_models_for_use_case(use_case)
    
    def check_model_status(self, provider: str, model: str) -> Dict[str, Any]:
        """모델 상태 확인"""
        model_spec = self.registry.get_model(provider, model)
        if not model_spec:
            return {"status": "not_found", "message": "모델을 찾을 수 없습니다"}
        
        if model_spec.deprecated:
            return {
                "status": "deprecated",
                "message": f"모델이 사용 중단되었습니다: {model_spec.deprecation_date}",
                "replacement": model_spec.replacement,
                "migration_guide": model_spec.migration_guide
            }
        
        return {"status": "active", "message": "모델이 활성 상태입니다"}
    
    def get_models_requiring_migration(self) -> List[Dict[str, Any]]:
        """마이그레이션이 필요한 모델들"""
        deprecated_models = self.registry.get_models_requiring_migration()
        
        return [
            {
                "provider": model.provider,
                "model": model.name,
                "deprecation_date": model.deprecation_date,
                "replacement": model.replacement,
                "migration_guide": model.migration_guide
            }
            for model in deprecated_models
        ]
    
    def reload_registry(self):
        """모델 레지스트리 재로드"""
        self.registry.reload_config()
        self._initialize_providers()
        logger.info("모델 레지스트리 재로드 완료")
    
    def get_registry_summary(self) -> Dict[str, Any]:
        """레지스트리 요약 정보"""
        return self.registry.get_registry_summary()
    
    def validate_environment_setup(self) -> Dict[str, Any]:
        """환경 설정 유효성 검사"""
        validation_result = {
            "environment": self.environment,
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # 환경 설정 확인
        if not self.env_config:
            validation_result["valid"] = False
            validation_result["errors"].append(f"환경 설정을 찾을 수 없습니다: {self.environment}")
            return validation_result
        
        # 기본 모델 확인
        default_models = [
            (self.env_config.default_provider, self.env_config.default_chat_model),
            ("openai", self.env_config.default_embedding_model)
        ]
        
        for provider, model in default_models:
            model_spec = self.registry.get_model(provider, model)
            if not model_spec:
                validation_result["errors"].append(f"기본 모델을 찾을 수 없습니다: {provider}:{model}")
                validation_result["valid"] = False
            elif model_spec.deprecated:
                validation_result["warnings"].append(f"기본 모델이 사용 중단되었습니다: {provider}:{model}")
        
        # API 키 확인
        for provider in self.registry.models.keys():
            api_key = self._get_api_key(provider)
            if not api_key:
                validation_result["warnings"].append(f"API 키가 설정되지 않았습니다: {provider}")
        
        return validation_result


# 싱글톤 인스턴스
_flexible_manager_instance = None

def get_flexible_llm_manager() -> FlexibleLLMManager:
    """유연한 LLM 매니저 싱글톤 인스턴스 반환"""
    global _flexible_manager_instance
    
    if _flexible_manager_instance is None:
        _flexible_manager_instance = FlexibleLLMManager()
    
    return _flexible_manager_instance