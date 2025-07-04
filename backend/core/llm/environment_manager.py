"""
환경별 설정 관리자 - 개발/스테이징/프로덕션 환경별 모델 설정 분리
"""

import os
import yaml
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Environment(Enum):
    """환경 타입"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


@dataclass
class EnvironmentConfig:
    """환경별 설정"""
    name: str
    default_provider: str
    default_chat_model: str
    default_embedding_model: str
    cost_limit: str
    rate_limits: Dict[str, int]
    model_overrides: Dict[str, Dict[str, str]]
    feature_flags: Dict[str, bool]
    monitoring: Dict[str, Any]


class EnvironmentManager:
    """환경별 설정 중앙 관리자"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = config_dir or self._get_default_config_dir()
        self.current_env = self._detect_environment()
        self.configs: Dict[str, EnvironmentConfig] = {}
        
        self._load_environment_configs()
        
        logger.info(f"EnvironmentManager 초기화 - 현재 환경: {self.current_env}")
    
    def _get_default_config_dir(self) -> str:
        """기본 설정 디렉토리 경로"""
        return os.path.join(
            os.path.dirname(__file__),
            "config",
            "environments"
        )
    
    def _detect_environment(self) -> str:
        """현재 환경 감지"""
        # 1. 환경변수에서 확인
        env = os.getenv('ENVIRONMENT', '').lower()
        if env in [e.value for e in Environment]:
            return env
        
        # 2. 기타 환경변수들로 추론
        if os.getenv('PRODUCTION') or os.getenv('PROD'):
            return Environment.PRODUCTION.value
        elif os.getenv('STAGING') or os.getenv('STAGE'):
            return Environment.STAGING.value
        elif os.getenv('TESTING') or os.getenv('TEST'):
            return Environment.TEST.value
        
        # 3. 기본값
        return Environment.DEVELOPMENT.value
    
    def _load_environment_configs(self):
        """모든 환경 설정 파일 로드"""
        config_dir = Path(self.config_dir)
        if not config_dir.exists():
            logger.warning(f"환경 설정 디렉토리가 없습니다: {config_dir}")
            self._create_default_configs()
            return
        
        for env_file in config_dir.glob("*.yaml"):
            try:
                env_name = env_file.stem
                with open(env_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                self.configs[env_name] = self._parse_environment_config(env_name, config_data)
                logger.info(f"환경 설정 로드 완료: {env_name}")
                
            except Exception as e:
                logger.error(f"환경 설정 로드 실패 {env_file}: {e}")
    
    def _parse_environment_config(self, env_name: str, config_data: Dict[str, Any]) -> EnvironmentConfig:
        """환경 설정 데이터 파싱"""
        return EnvironmentConfig(
            name=env_name,
            default_provider=config_data.get('default_provider', 'gemini'),
            default_chat_model=config_data.get('default_chat_model', 'gemini-1.5-flash'),
            default_embedding_model=config_data.get('default_embedding_model', 'text-embedding-3-small'),
            cost_limit=config_data.get('cost_limit', 'medium'),
            rate_limits=config_data.get('rate_limits', {}),
            model_overrides=config_data.get('model_overrides', {}),
            feature_flags=config_data.get('feature_flags', {}),
            monitoring=config_data.get('monitoring', {})
        )
    
    def _create_default_configs(self):
        """기본 환경 설정 파일들 생성"""
        config_dir = Path(self.config_dir)
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # 개발 환경 설정
        dev_config = {
            'default_provider': 'gemini',
            'default_chat_model': 'gemini-1.5-flash',
            'default_embedding_model': 'text-embedding-3-small',
            'cost_limit': 'low',
            'rate_limits': {
                'requests_per_minute': 60,
                'tokens_per_minute': 100000
            },
            'model_overrides': {
                'summarization': {
                    'provider': 'gemini',
                    'model': 'gemini-1.5-flash'
                }
            },
            'feature_flags': {
                'enable_caching': True,
                'enable_rate_limiting': False,
                'enable_metrics': True,
                'enable_debugging': True
            },
            'monitoring': {
                'log_level': 'DEBUG',
                'metrics_interval': 60,
                'enable_performance_tracking': True
            }
        }
        
        # 스테이징 환경 설정
        staging_config = {
            'default_provider': 'anthropic',
            'default_chat_model': 'claude-3-5-haiku-20241022',
            'default_embedding_model': 'text-embedding-3-small',
            'cost_limit': 'medium',
            'rate_limits': {
                'requests_per_minute': 300,
                'tokens_per_minute': 500000
            },
            'model_overrides': {
                'summarization': {
                    'provider': 'anthropic',
                    'model': 'claude-3-5-haiku-20241022'
                },
                'analysis': {
                    'provider': 'anthropic',
                    'model': 'claude-3-sonnet-20240229'
                }
            },
            'feature_flags': {
                'enable_caching': True,
                'enable_rate_limiting': True,
                'enable_metrics': True,
                'enable_debugging': False
            },
            'monitoring': {
                'log_level': 'INFO',
                'metrics_interval': 30,
                'enable_performance_tracking': True
            }
        }
        
        # 프로덕션 환경 설정
        prod_config = {
            'default_provider': 'anthropic',
            'default_chat_model': 'claude-3-sonnet-20240229',
            'default_embedding_model': 'text-embedding-3-small',
            'cost_limit': 'high',
            'rate_limits': {
                'requests_per_minute': 1000,
                'tokens_per_minute': 2000000
            },
            'model_overrides': {
                'summarization': {
                    'provider': 'anthropic',
                    'model': 'claude-3-5-haiku-20241022'
                },
                'analysis': {
                    'provider': 'anthropic',
                    'model': 'claude-3-opus-20240229'
                },
                'question_answering': {
                    'provider': 'anthropic',
                    'model': 'claude-3-sonnet-20240229'
                }
            },
            'feature_flags': {
                'enable_caching': True,
                'enable_rate_limiting': True,
                'enable_metrics': True,
                'enable_debugging': False
            },
            'monitoring': {
                'log_level': 'WARNING',
                'metrics_interval': 15,
                'enable_performance_tracking': True,
                'alert_thresholds': {
                    'error_rate': 0.05,
                    'response_time': 10.0,
                    'cost_per_hour': 50.0
                }
            }
        }
        
        # 테스트 환경 설정
        test_config = {
            'default_provider': 'openai',
            'default_chat_model': 'gpt-3.5-turbo',
            'default_embedding_model': 'text-embedding-3-small',
            'cost_limit': 'very_low',
            'rate_limits': {
                'requests_per_minute': 10,
                'tokens_per_minute': 10000
            },
            'model_overrides': {},
            'feature_flags': {
                'enable_caching': False,
                'enable_rate_limiting': False,
                'enable_metrics': False,
                'enable_debugging': True
            },
            'monitoring': {
                'log_level': 'DEBUG',
                'metrics_interval': 120,
                'enable_performance_tracking': False
            }
        }
        
        configs = {
            'development': dev_config,
            'staging': staging_config,
            'production': prod_config,
            'test': test_config
        }
        
        for env_name, config in configs.items():
            config_file = config_dir / f"{env_name}.yaml"
            try:
                with open(config_file, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                self.configs[env_name] = self._parse_environment_config(env_name, config)
                logger.info(f"기본 환경 설정 파일 생성: {config_file}")
                
            except Exception as e:
                logger.error(f"환경 설정 파일 생성 실패 {config_file}: {e}")
    
    def get_current_config(self) -> Optional[EnvironmentConfig]:
        """현재 환경의 설정 반환"""
        return self.configs.get(self.current_env)
    
    def get_config(self, env_name: str) -> Optional[EnvironmentConfig]:
        """특정 환경의 설정 반환"""
        return self.configs.get(env_name)
    
    def get_model_for_use_case(self, use_case: str) -> Optional[tuple[str, str]]:
        """Use case에 따른 모델 선택 (환경별 오버라이드 적용)"""
        config = self.get_current_config()
        if not config:
            return None
        
        # 1. 환경별 오버라이드 확인
        if use_case in config.model_overrides:
            override = config.model_overrides[use_case]
            return (override['provider'], override['model'])
        
        # 2. 기본 모델 반환
        if use_case == 'embedding':
            return ('openai', config.default_embedding_model)
        else:
            return (config.default_provider, config.default_chat_model)
    
    def get_feature_flag(self, flag_name: str) -> bool:
        """환경별 기능 플래그 확인"""
        config = self.get_current_config()
        if not config:
            return False
        
        return config.feature_flags.get(flag_name, False)
    
    def get_rate_limit(self, limit_type: str) -> Optional[int]:
        """환경별 속도 제한 값 조회"""
        config = self.get_current_config()
        if not config:
            return None
        
        return config.rate_limits.get(limit_type)
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """환경별 모니터링 설정 조회"""
        config = self.get_current_config()
        if not config:
            return {}
        
        return config.monitoring
    
    def switch_environment(self, env_name: str) -> bool:
        """환경 전환"""
        if env_name not in self.configs:
            logger.error(f"알 수 없는 환경: {env_name}")
            return False
        
        self.current_env = env_name
        os.environ['ENVIRONMENT'] = env_name
        logger.info(f"환경 전환: {env_name}")
        return True
    
    def validate_current_environment(self) -> Dict[str, Any]:
        """현재 환경 설정 유효성 검사"""
        config = self.get_current_config()
        if not config:
            return {
                'valid': False,
                'errors': [f"환경 설정을 찾을 수 없습니다: {self.current_env}"]
            }
        
        validation_result = {
            'environment': self.current_env,
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        # 모델 오버라이드 검증
        for use_case, override in config.model_overrides.items():
            if 'provider' not in override or 'model' not in override:
                validation_result['errors'].append(
                    f"모델 오버라이드 설정 불완전: {use_case}"
                )
                validation_result['valid'] = False
        
        # 비용 제한 확인
        valid_cost_limits = ['very_low', 'low', 'medium', 'high', 'very_high']
        if config.cost_limit not in valid_cost_limits:
            validation_result['warnings'].append(
                f"알 수 없는 비용 제한: {config.cost_limit}"
            )
        
        return validation_result
    
    def get_environment_summary(self) -> Dict[str, Any]:
        """환경 설정 요약 정보"""
        config = self.get_current_config()
        if not config:
            return {}
        
        return {
            'current_environment': self.current_env,
            'available_environments': list(self.configs.keys()),
            'default_provider': config.default_provider,
            'default_chat_model': config.default_chat_model,
            'default_embedding_model': config.default_embedding_model,
            'cost_limit': config.cost_limit,
            'model_overrides_count': len(config.model_overrides),
            'feature_flags_enabled': sum(1 for v in config.feature_flags.values() if v),
            'rate_limits': config.rate_limits,
            'config_dir': self.config_dir
        }
    
    def reload_configs(self):
        """설정 파일 재로드"""
        self.configs.clear()
        self._load_environment_configs()
        logger.info("환경 설정 재로드 완료")


# 싱글톤 인스턴스
_environment_manager_instance = None

def get_environment_manager() -> EnvironmentManager:
    """환경 관리자 싱글톤 인스턴스 반환"""
    global _environment_manager_instance
    
    if _environment_manager_instance is None:
        _environment_manager_instance = EnvironmentManager()
    
    return _environment_manager_instance