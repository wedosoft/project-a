"""
Anthropic 프롬프트 엔지니어링 설정 관리

환경변수 기반의 설정 로드와 실시간 설정 업데이트를 지원합니다.
Constitutional AI, Chain-of-Thought, XML 구조화 등의 기법 설정을 관리합니다.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)


@dataclass
class AnthropicConfig:
    """Anthropic 프롬프트 엔지니어링 설정"""
    
    # 기본 활성화 설정
    enabled: bool = True
    
    # 품질 관리 설정 (실시간 성능 최적화)
    quality_threshold: float = 0.5  # 0.8 → 0.5로 대폭 완화
    max_retries: int = 1  # 2 → 1로 재시도 감소
    retry_threshold: float = 0.3  # 0.6 → 0.3로 완화
    fallback_threshold: float = 0.2  # 0.4 → 0.2로 완화
    
    # LLM 호출 설정
    temperature: float = 0.1
    max_tokens: int = 1500
    timeout: int = 30
    
    # 모델 설정
    model_provider: str = "anthropic"
    model_name: str = "claude-3-sonnet-20240229"
    
    # 지원되는 Anthropic 기법들
    supported_techniques: List[str] = field(default_factory=lambda: [
        "constitutional_ai",
        "chain_of_thought", 
        "xml_structuring",
        "role_prompting",
        "few_shot_learning"
    ])
    
    # 활성화된 기법들 (모든 기법이 기본 활성화)
    enabled_techniques: List[str] = field(default_factory=lambda: [
        "constitutional_ai",
        "chain_of_thought",
        "xml_structuring", 
        "role_prompting",
        "few_shot_learning"
    ])
    
    # Constitutional AI 원칙 가중치
    constitutional_weights: Dict[str, float] = field(default_factory=lambda: {
        'helpful': 0.35,
        'harmless': 0.35,
        'honest': 0.30
    })
    
    # 품질 측정 가중치
    quality_weights: Dict[str, float] = field(default_factory=lambda: {
        'constitutional_compliance': 0.3,
        'xml_structure_validity': 0.2,
        'factual_accuracy': 0.2,
        'actionability': 0.15,
        'completeness': 0.15
    })
    
    # 사용 사례별 모델 설정
    use_case_models: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        'anthropic_ticket_view': {
            'provider': 'anthropic',
            'model': 'claude-3-sonnet-20240229'
        },
        'realtime_summary': {
            'provider': 'anthropic', 
            'model': 'claude-3-haiku-20240307'  # 더 빠른 모델
        },
        'attachment_selection': {
            'provider': 'anthropic',
            'model': 'claude-3-sonnet-20240229'
        },
        'comprehensive_analysis': {
            'provider': 'anthropic',
            'model': 'claude-3-opus-20240229'  # 가장 강력한 모델
        }
    })
    
    # 성능 최적화 설정
    performance_settings: Dict[str, Any] = field(default_factory=lambda: {
        'enable_caching': True,
        'cache_ttl': 3600,  # 1시간
        'enable_parallel_processing': True,
        'max_concurrent_requests': 5,
        'enable_request_batching': False
    })
    
    # 모니터링 설정
    monitoring_settings: Dict[str, Any] = field(default_factory=lambda: {
        'enable_metrics': True,
        'enable_logging': True,
        'log_level': 'INFO',
        'enable_alerts': True,
        'alert_thresholds': {
            'quality_score': 0.7,
            'response_time': 30.0,
            'error_rate': 0.1
        }
    })
    
    # 실험적 기능 설정
    experimental_features: Dict[str, bool] = field(default_factory=lambda: {
        'enable_dynamic_prompts': True,
        'enable_context_optimization': True,
        'enable_adaptive_quality': True,
        'enable_prompt_versioning': True
    })
    
    @classmethod
    def from_env(cls, prefix: str = "ANTHROPIC_") -> 'AnthropicConfig':
        """
        환경변수에서 설정 로드
        
        Args:
            prefix: 환경변수 접두사
            
        Returns:
            AnthropicConfig: 로드된 설정
        """
        try:
            config = cls()
            
            # 기본 설정
            config.enabled = cls._get_bool_env(f"{prefix}ENABLED", config.enabled)
            config.quality_threshold = cls._get_float_env(f"{prefix}QUALITY_THRESHOLD", config.quality_threshold)
            config.max_retries = cls._get_int_env(f"{prefix}MAX_RETRIES", config.max_retries)
            config.temperature = cls._get_float_env(f"{prefix}TEMPERATURE", config.temperature)
            config.max_tokens = cls._get_int_env(f"{prefix}MAX_TOKENS", config.max_tokens)
            config.timeout = cls._get_int_env(f"{prefix}TIMEOUT", config.timeout)
            
            # 모델 설정
            config.model_provider = os.getenv(f"{prefix}MODEL_PROVIDER", config.model_provider)
            config.model_name = os.getenv(f"{prefix}MODEL_NAME", config.model_name)
            
            # 사용 사례별 모델 설정 로드
            config._load_use_case_models_from_env(prefix)
            
            # Constitutional AI 가중치 로드
            config._load_constitutional_weights_from_env(prefix)
            
            # 성능 설정 로드
            config._load_performance_settings_from_env(prefix)
            
            # 모니터링 설정 로드
            config._load_monitoring_settings_from_env(prefix)
            
            # 실험적 기능 설정 로드
            config._load_experimental_features_from_env(prefix)
            
            logger.info(f"Anthropic 설정 로드 완료 (활성화: {config.enabled})")
            return config
            
        except Exception as e:
            logger.error(f"환경변수에서 설정 로드 실패: {e}")
            logger.info("기본 설정 사용")
            return cls()
    
    def _load_use_case_models_from_env(self, prefix: str):
        """사용 사례별 모델 설정 로드"""
        use_case_mapping = {
            'TICKET_VIEW': 'anthropic_ticket_view',
            'REALTIME_SUMMARY': 'realtime_summary', 
            'ATTACHMENT_SELECTION': 'attachment_selection',
            'COMPREHENSIVE_ANALYSIS': 'comprehensive_analysis'
        }
        
        for env_key, use_case in use_case_mapping.items():
            provider_key = f"{prefix}{env_key}_MODEL_PROVIDER"
            model_key = f"{prefix}{env_key}_MODEL_NAME"
            
            provider = os.getenv(provider_key)
            model = os.getenv(model_key)
            
            if provider or model:
                if use_case not in self.use_case_models:
                    self.use_case_models[use_case] = {}
                if provider:
                    self.use_case_models[use_case]['provider'] = provider
                if model:
                    self.use_case_models[use_case]['model'] = model
    
    def _load_constitutional_weights_from_env(self, prefix: str):
        """Constitutional AI 가중치 로드"""
        helpful_weight = self._get_float_env(f"{prefix}CONSTITUTIONAL_HELPFUL_WEIGHT", 
                                           self.constitutional_weights['helpful'])
        harmless_weight = self._get_float_env(f"{prefix}CONSTITUTIONAL_HARMLESS_WEIGHT",
                                            self.constitutional_weights['harmless'])
        honest_weight = self._get_float_env(f"{prefix}CONSTITUTIONAL_HONEST_WEIGHT",
                                          self.constitutional_weights['honest'])
        
        # 가중치 정규화
        total_weight = helpful_weight + harmless_weight + honest_weight
        if total_weight > 0:
            self.constitutional_weights = {
                'helpful': helpful_weight / total_weight,
                'harmless': harmless_weight / total_weight,
                'honest': honest_weight / total_weight
            }
    
    def _load_performance_settings_from_env(self, prefix: str):
        """성능 설정 로드"""
        perf_prefix = f"{prefix}PERFORMANCE_"
        
        self.performance_settings.update({
            'enable_caching': self._get_bool_env(f"{perf_prefix}ENABLE_CACHING", 
                                               self.performance_settings['enable_caching']),
            'cache_ttl': self._get_int_env(f"{perf_prefix}CACHE_TTL",
                                         self.performance_settings['cache_ttl']),
            'enable_parallel_processing': self._get_bool_env(f"{perf_prefix}ENABLE_PARALLEL",
                                                           self.performance_settings['enable_parallel_processing']),
            'max_concurrent_requests': self._get_int_env(f"{perf_prefix}MAX_CONCURRENT",
                                                       self.performance_settings['max_concurrent_requests'])
        })
    
    def _load_monitoring_settings_from_env(self, prefix: str):
        """모니터링 설정 로드"""
        monitor_prefix = f"{prefix}MONITORING_"
        
        self.monitoring_settings.update({
            'enable_metrics': self._get_bool_env(f"{monitor_prefix}ENABLE_METRICS",
                                               self.monitoring_settings['enable_metrics']),
            'enable_logging': self._get_bool_env(f"{monitor_prefix}ENABLE_LOGGING",
                                               self.monitoring_settings['enable_logging']),
            'log_level': os.getenv(f"{monitor_prefix}LOG_LEVEL", 
                                 self.monitoring_settings['log_level']),
            'enable_alerts': self._get_bool_env(f"{monitor_prefix}ENABLE_ALERTS",
                                              self.monitoring_settings['enable_alerts'])
        })
        
        # 알림 임계값 로드
        alert_prefix = f"{monitor_prefix}ALERT_"
        quality_threshold = self._get_float_env(f"{alert_prefix}QUALITY_THRESHOLD",
                                              self.monitoring_settings['alert_thresholds']['quality_score'])
        response_time_threshold = self._get_float_env(f"{alert_prefix}RESPONSE_TIME_THRESHOLD",
                                                    self.monitoring_settings['alert_thresholds']['response_time'])
        error_rate_threshold = self._get_float_env(f"{alert_prefix}ERROR_RATE_THRESHOLD",
                                                 self.monitoring_settings['alert_thresholds']['error_rate'])
        
        self.monitoring_settings['alert_thresholds'].update({
            'quality_score': quality_threshold,
            'response_time': response_time_threshold,
            'error_rate': error_rate_threshold
        })
    
    def _load_experimental_features_from_env(self, prefix: str):
        """실험적 기능 설정 로드"""
        exp_prefix = f"{prefix}EXPERIMENTAL_"
        
        self.experimental_features.update({
            'enable_dynamic_prompts': self._get_bool_env(f"{exp_prefix}DYNAMIC_PROMPTS",
                                                       self.experimental_features['enable_dynamic_prompts']),
            'enable_context_optimization': self._get_bool_env(f"{exp_prefix}CONTEXT_OPTIMIZATION",
                                                            self.experimental_features['enable_context_optimization']),
            'enable_adaptive_quality': self._get_bool_env(f"{exp_prefix}ADAPTIVE_QUALITY",
                                                        self.experimental_features['enable_adaptive_quality']),
            'enable_prompt_versioning': self._get_bool_env(f"{exp_prefix}PROMPT_VERSIONING",
                                                         self.experimental_features['enable_prompt_versioning'])
        })
    
    @staticmethod
    def _get_bool_env(key: str, default: bool) -> bool:
        """환경변수에서 boolean 값 로드"""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    @staticmethod
    def _get_int_env(key: str, default: int) -> int:
        """환경변수에서 정수 값 로드"""
        try:
            value = os.getenv(key)
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            logger.warning(f"환경변수 {key}의 정수 변환 실패, 기본값 사용: {default}")
            return default
    
    @staticmethod
    def _get_float_env(key: str, default: float) -> float:
        """환경변수에서 실수 값 로드"""
        try:
            value = os.getenv(key)
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            logger.warning(f"환경변수 {key}의 실수 변환 실패, 기본값 사용: {default}")
            return default
    
    def get_model_config(self, use_case: str) -> Dict[str, str]:
        """
        사용 사례별 모델 설정 조회
        
        Args:
            use_case: 사용 사례 이름
            
        Returns:
            Dict[str, str]: 모델 설정 {'provider': '', 'model': ''}
        """
        return self.use_case_models.get(use_case, {
            'provider': self.model_provider,
            'model': self.model_name
        })
    
    def is_technique_enabled(self, technique: str) -> bool:
        """
        특정 기법이 활성화되었는지 확인
        
        Args:
            technique: 기법 이름
            
        Returns:
            bool: 활성화 여부
        """
        return technique in self.enabled_techniques
    
    def update_quality_threshold(self, new_threshold: float):
        """
        품질 임계값 업데이트
        
        Args:
            new_threshold: 새로운 임계값 (0.0 ~ 1.0)
        """
        if 0.0 <= new_threshold <= 1.0:
            self.quality_threshold = new_threshold
            logger.info(f"품질 임계값 업데이트: {new_threshold}")
        else:
            logger.error(f"유효하지 않은 품질 임계값: {new_threshold}")
    
    def update_constitutional_weights(self, weights: Dict[str, float]):
        """
        Constitutional AI 가중치 업데이트
        
        Args:
            weights: 새로운 가중치 {'helpful': 0.4, 'harmless': 0.4, 'honest': 0.2}
        """
        total_weight = sum(weights.values())
        if total_weight > 0:
            self.constitutional_weights = {
                key: value / total_weight 
                for key, value in weights.items()
                if key in ['helpful', 'harmless', 'honest']
            }
            logger.info(f"Constitutional AI 가중치 업데이트: {self.constitutional_weights}")
        else:
            logger.error(f"유효하지 않은 가중치: {weights}")
    
    def enable_technique(self, technique: str):
        """
        특정 기법 활성화
        
        Args:
            technique: 활성화할 기법 이름
        """
        if technique in self.supported_techniques and technique not in self.enabled_techniques:
            self.enabled_techniques.append(technique)
            logger.info(f"기법 활성화: {technique}")
    
    def disable_technique(self, technique: str):
        """
        특정 기법 비활성화
        
        Args:
            technique: 비활성화할 기법 이름
        """
        if technique in self.enabled_techniques:
            self.enabled_techniques.remove(technique)
            logger.info(f"기법 비활성화: {technique}")
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'enabled': self.enabled,
            'quality_threshold': self.quality_threshold,
            'max_retries': self.max_retries,
            'temperature': self.temperature,
            'model_provider': self.model_provider,
            'model_name': self.model_name,
            'supported_techniques': self.supported_techniques,
            'enabled_techniques': self.enabled_techniques,
            'constitutional_weights': self.constitutional_weights,
            'quality_weights': self.quality_weights,
            'use_case_models': self.use_case_models,
            'performance_settings': self.performance_settings,
            'monitoring_settings': self.monitoring_settings,
            'experimental_features': self.experimental_features
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnthropicConfig':
        """딕셔너리에서 설정 생성"""
        config = cls()
        
        # 기본 필드 업데이트
        for field_name in ['enabled', 'quality_threshold', 'max_retries', 'temperature', 
                          'model_provider', 'model_name', 'supported_techniques', 
                          'enabled_techniques']:
            if field_name in data:
                setattr(config, field_name, data[field_name])
        
        # 복합 필드 업데이트
        for field_name in ['constitutional_weights', 'quality_weights', 'use_case_models',
                          'performance_settings', 'monitoring_settings', 'experimental_features']:
            if field_name in data:
                getattr(config, field_name).update(data[field_name])
        
        return config
    
    def validate(self) -> List[str]:
        """
        설정 유효성 검증
        
        Returns:
            List[str]: 검증 오류 목록 (빈 리스트면 유효)
        """
        errors = []
        
        # 임계값 범위 확인
        if not 0.0 <= self.quality_threshold <= 1.0:
            errors.append(f"품질 임계값이 범위를 벗어남: {self.quality_threshold}")
        
        if not 0.0 <= self.temperature <= 2.0:
            errors.append(f"온도값이 범위를 벗어남: {self.temperature}")
        
        # 가중치 합계 확인
        constitutional_sum = sum(self.constitutional_weights.values())
        if abs(constitutional_sum - 1.0) > 0.01:
            errors.append(f"Constitutional AI 가중치 합계가 1.0이 아님: {constitutional_sum}")
        
        quality_sum = sum(self.quality_weights.values())
        if abs(quality_sum - 1.0) > 0.01:
            errors.append(f"품질 가중치 합계가 1.0이 아님: {quality_sum}")
        
        # 필수 기법 확인
        required_techniques = ['constitutional_ai', 'xml_structuring']
        for technique in required_techniques:
            if technique not in self.enabled_techniques:
                errors.append(f"필수 기법이 비활성화됨: {technique}")
        
        return errors
    
    def __str__(self) -> str:
        """설정 문자열 표현"""
        return (f"AnthropicConfig(enabled={self.enabled}, "
                f"quality_threshold={self.quality_threshold}, "
                f"model={self.model_provider}/{self.model_name}, "
                f"techniques={len(self.enabled_techniques)}/{len(self.supported_techniques)})")
    
    def __repr__(self) -> str:
        return self.__str__()