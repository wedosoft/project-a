"""
모델 레지스트리 시스템 - 모든 LLM 모델을 중앙에서 관리하는 시스템
"""

import os
import yaml
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CostTier(Enum):
    """비용 등급"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class SpeedTier(Enum):
    """속도 등급"""
    VERY_SLOW = "very_slow"
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    VERY_FAST = "very_fast"


class QualityTier(Enum):
    """품질 등급"""
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"
    OUTSTANDING = "outstanding"


class ModelType(Enum):
    """모델 타입"""
    CHAT = "chat"
    EMBEDDING = "embedding"
    COMPLETION = "completion"


@dataclass
class ModelSpec:
    """모델 사양"""
    name: str
    provider: str
    type: ModelType
    capabilities: List[str]
    cost_tier: CostTier
    speed_tier: SpeedTier
    quality_tier: QualityTier
    context_window: int
    max_tokens: int
    deprecated: bool = False
    replacement: Optional[str] = None
    dimensions: Optional[int] = None  # 임베딩 모델용
    deprecation_date: Optional[str] = None
    migration_guide: Optional[str] = None


@dataclass
class UseCaseConfig:
    """Use case별 모델 설정"""
    name: str
    priority_models: List[Tuple[str, str]]  # (provider, model) 튜플
    requirements: Dict[str, Any]
    fallback_strategy: str = "next_priority"


@dataclass
class EnvironmentConfig:
    """환경별 기본 설정"""
    name: str
    default_provider: str
    default_chat_model: str
    default_embedding_model: str
    cost_limit: CostTier


class ModelRegistry:
    """모델 레지스트리 - 모든 모델 정보를 중앙에서 관리"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.models: Dict[str, Dict[str, ModelSpec]] = {}
        self.use_cases: Dict[str, UseCaseConfig] = {}
        self.environments: Dict[str, EnvironmentConfig] = {}
        self.deprecation_policy: Dict[str, Any] = {}
        self.monitoring_config: Dict[str, Any] = {}
        
        self._load_config()
    
    def _get_default_config_path(self) -> str:
        """기본 설정 파일 경로 반환"""
        return os.path.join(
            os.path.dirname(__file__),
            "config",
            "model_registry.yaml"
        )
    
    def _load_config(self):
        """설정 파일에서 모델 정보 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self._parse_providers(config.get('providers', {}))
            self._parse_use_cases(config.get('use_cases', {}))
            self._parse_environments(config.get('environments', {}))
            self.deprecation_policy = config.get('deprecation_policy', {})
            self.monitoring_config = config.get('monitoring', {})
            
            logger.info(f"Model registry loaded from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load model registry: {e}")
            raise
    
    def _parse_providers(self, providers_config: Dict[str, Any]):
        """제공자별 모델 정보 파싱"""
        for provider_name, provider_config in providers_config.items():
            self.models[provider_name] = {}
            
            for model_name, model_config in provider_config.get('models', {}).items():
                try:
                    model_spec = ModelSpec(
                        name=model_name,
                        provider=provider_name,
                        type=ModelType(model_config['type']),
                        capabilities=model_config.get('capabilities', []),
                        cost_tier=CostTier(model_config['cost_tier']),
                        speed_tier=SpeedTier(model_config['speed_tier']),
                        quality_tier=QualityTier(model_config['quality_tier']),
                        context_window=model_config.get('context_window', 0),
                        max_tokens=model_config.get('max_tokens', 0),
                        deprecated=model_config.get('deprecated', False),
                        replacement=model_config.get('replacement'),
                        dimensions=model_config.get('dimensions'),
                        deprecation_date=model_config.get('deprecation_date'),
                        migration_guide=model_config.get('migration_guide')
                    )
                    
                    self.models[provider_name][model_name] = model_spec
                    
                except Exception as e:
                    logger.error(f"Failed to parse model {model_name}: {e}")
                    continue
    
    def _parse_use_cases(self, use_cases_config: Dict[str, Any]):
        """Use case별 설정 파싱"""
        for use_case_name, use_case_config in use_cases_config.items():
            try:
                priority_models = [
                    (model['provider'], model['model'])
                    for model in use_case_config.get('priority_models', [])
                ]
                
                self.use_cases[use_case_name] = UseCaseConfig(
                    name=use_case_name,
                    priority_models=priority_models,
                    requirements=use_case_config.get('requirements', {}),
                    fallback_strategy=use_case_config.get('fallback_strategy', 'next_priority')
                )
                
            except Exception as e:
                logger.error(f"Failed to parse use case {use_case_name}: {e}")
                continue
    
    def _parse_environments(self, environments_config: Dict[str, Any]):
        """환경별 설정 파싱"""
        for env_name, env_config in environments_config.items():
            try:
                self.environments[env_name] = EnvironmentConfig(
                    name=env_name,
                    default_provider=env_config['default_provider'],
                    default_chat_model=env_config['default_chat_model'],
                    default_embedding_model=env_config['default_embedding_model'],
                    cost_limit=CostTier(env_config['cost_limit'])
                )
                
            except Exception as e:
                logger.error(f"Failed to parse environment {env_name}: {e}")
                continue
    
    def get_model(self, provider: str, model: str) -> Optional[ModelSpec]:
        """특정 모델 사양 조회"""
        return self.models.get(provider, {}).get(model)
    
    def get_available_models(self, provider: Optional[str] = None, 
                           model_type: Optional[ModelType] = None,
                           include_deprecated: bool = False) -> List[ModelSpec]:
        """사용 가능한 모델 목록 조회"""
        models = []
        
        providers = [provider] if provider else self.models.keys()
        
        for prov in providers:
            for model_spec in self.models.get(prov, {}).values():
                if not include_deprecated and model_spec.deprecated:
                    continue
                    
                if model_type and model_spec.type != model_type:
                    continue
                    
                models.append(model_spec)
        
        return models
    
    def get_models_for_use_case(self, use_case: str) -> List[Tuple[str, str]]:
        """Use case에 따른 우선순위 모델 목록 반환"""
        if use_case not in self.use_cases:
            logger.warning(f"Unknown use case: {use_case}")
            return []
        
        return self.use_cases[use_case].priority_models
    
    def get_best_model_for_use_case(self, use_case: str, 
                                   cost_limit: Optional[CostTier] = None,
                                   speed_requirement: Optional[SpeedTier] = None) -> Optional[Tuple[str, str]]:
        """Use case에 가장 적합한 모델 선택"""
        priority_models = self.get_models_for_use_case(use_case)
        
        for provider, model_name in priority_models:
            model_spec = self.get_model(provider, model_name)
            
            if not model_spec or model_spec.deprecated:
                continue
                
            # 비용 제한 체크
            if cost_limit and self._compare_cost_tier(model_spec.cost_tier, cost_limit) > 0:
                continue
                
            # 속도 요구사항 체크
            if speed_requirement and self._compare_speed_tier(model_spec.speed_tier, speed_requirement) < 0:
                continue
                
            return (provider, model_name)
        
        return None
    
    def _compare_cost_tier(self, tier1: CostTier, tier2: CostTier) -> int:
        """비용 등급 비교 (-1: tier1 < tier2, 0: 같음, 1: tier1 > tier2)"""
        cost_order = {
            CostTier.VERY_LOW: 0,
            CostTier.LOW: 1,
            CostTier.MEDIUM: 2,
            CostTier.HIGH: 3,
            CostTier.VERY_HIGH: 4
        }
        return cost_order[tier1] - cost_order[tier2]
    
    def _compare_speed_tier(self, tier1: SpeedTier, tier2: SpeedTier) -> int:
        """속도 등급 비교 (-1: tier1 < tier2, 0: 같음, 1: tier1 > tier2)"""
        speed_order = {
            SpeedTier.VERY_SLOW: 0,
            SpeedTier.SLOW: 1,
            SpeedTier.MEDIUM: 2,
            SpeedTier.FAST: 3,
            SpeedTier.VERY_FAST: 4
        }
        return speed_order[tier1] - speed_order[tier2]
    
    def get_environment_config(self, env: str) -> Optional[EnvironmentConfig]:
        """환경별 설정 조회"""
        return self.environments.get(env)
    
    def get_deprecated_models(self) -> List[ModelSpec]:
        """사용 중단된 모델 목록 반환"""
        deprecated_models = []
        
        for provider_models in self.models.values():
            for model_spec in provider_models.values():
                if model_spec.deprecated:
                    deprecated_models.append(model_spec)
        
        return deprecated_models
    
    def get_models_requiring_migration(self, days_ahead: int = 30) -> List[ModelSpec]:
        """마이그레이션이 필요한 모델 목록 반환"""
        models_to_migrate = []
        
        for model_spec in self.get_deprecated_models():
            if model_spec.deprecation_date:
                try:
                    deprecation_date = datetime.strptime(
                        model_spec.deprecation_date, 
                        "%Y-%m-%d"
                    )
                    
                    if deprecation_date <= datetime.now() + timedelta(days=days_ahead):
                        models_to_migrate.append(model_spec)
                        
                except ValueError:
                    logger.warning(f"Invalid deprecation date format for {model_spec.name}")
                    continue
        
        return models_to_migrate
    
    def suggest_replacement(self, provider: str, model: str) -> Optional[str]:
        """모델 교체 제안"""
        model_spec = self.get_model(provider, model)
        
        if not model_spec:
            return None
            
        if model_spec.deprecated and model_spec.replacement:
            return model_spec.replacement
            
        return None
    
    def validate_model_compatibility(self, provider: str, model: str, 
                                   use_case: str) -> bool:
        """모델이 특정 use case에 적합한지 검증"""
        model_spec = self.get_model(provider, model)
        
        if not model_spec:
            return False
            
        if model_spec.deprecated:
            return False
            
        if use_case not in self.use_cases:
            return True  # 알려지지 않은 use case는 기본적으로 허용
            
        use_case_config = self.use_cases[use_case]
        requirements = use_case_config.requirements
        
        # 컨텍스트 윈도우 요구사항 체크
        if 'context_window' in requirements:
            if model_spec.context_window < requirements['context_window']:
                return False
                
        # 최대 토큰 요구사항 체크
        if 'max_tokens' in requirements:
            if model_spec.max_tokens < requirements['max_tokens']:
                return False
                
        # 차원 요구사항 체크 (임베딩 모델용)
        if 'dimensions' in requirements and model_spec.dimensions:
            if model_spec.dimensions != requirements['dimensions']:
                return False
                
        return True
    
    def reload_config(self):
        """설정 파일 재로드"""
        self._load_config()
        logger.info("Model registry configuration reloaded")
    
    def get_registry_summary(self) -> Dict[str, Any]:
        """레지스트리 요약 정보 반환"""
        total_models = sum(len(provider_models) for provider_models in self.models.values())
        deprecated_count = len(self.get_deprecated_models())
        
        return {
            'total_models': total_models,
            'deprecated_models': deprecated_count,
            'active_models': total_models - deprecated_count,
            'providers': list(self.models.keys()),
            'use_cases': list(self.use_cases.keys()),
            'environments': list(self.environments.keys()),
            'config_path': self.config_path,
            'last_loaded': datetime.now().isoformat()
        }


# 싱글톤 인스턴스
_registry_instance = None


def get_model_registry() -> ModelRegistry:
    """모델 레지스트리 싱글톤 인스턴스 반환"""
    global _registry_instance
    
    if _registry_instance is None:
        _registry_instance = ModelRegistry()
    
    return _registry_instance


def reload_model_registry():
    """모델 레지스트리 재로드"""
    global _registry_instance
    
    if _registry_instance is not None:
        _registry_instance.reload_config()