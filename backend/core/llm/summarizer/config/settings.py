"""
Anthropic 프롬프트 엔지니어링 통합 설정 관리

환경변수 기반 설정을 통합 관리하고, 런타임 설정 업데이트를 지원합니다.
개발/운영 환경에 따른 설정 자동 조정과 검증 기능을 포함합니다.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from datetime import datetime

from .anthropic_config import AnthropicConfig

logger = logging.getLogger(__name__)


class AnthropicSettings:
    """Anthropic 프롬프트 엔지니어링 통합 설정 관리"""
    
    def __init__(self):
        """설정 관리자 초기화"""
        self._config = None
        self._last_reload = None
        self._validation_errors = []
        
        # 설정 파일 경로
        self.templates_dir = Path(__file__).parent.parent / "prompt" / "templates"
        self.config_dir = Path(__file__).parent
        
        # 캐시 설정
        self._enable_config_cache = True
        self._config_cache_ttl = 300  # 5분
        
        self.load_config()
    
    def load_config(self, force_reload: bool = False) -> AnthropicConfig:
        """
        설정 로드 (캐시 지원)
        
        Args:
            force_reload: 강제 다시 로드 여부
            
        Returns:
            AnthropicConfig: 로드된 설정
        """
        try:
            # 캐시 확인
            if not force_reload and self._config and self._enable_config_cache:
                if self._last_reload:
                    elapsed = (datetime.now() - self._last_reload).seconds
                    if elapsed < self._config_cache_ttl:
                        logger.debug("캐시된 Anthropic 설정 사용")
                        return self._config
            
            # 환경변수에서 설정 로드
            logger.info("Anthropic 설정 로드 중...")
            self._config = AnthropicConfig.from_env()
            self._last_reload = datetime.now()
            
            # 설정 검증
            self._validation_errors = self._config.validate()
            if self._validation_errors:
                logger.warning(f"설정 검증 경고: {self._validation_errors}")
            
            # 개발 환경 자동 조정
            self._adjust_for_environment()
            
            logger.info(f"✅ Anthropic 설정 로드 완료: {self._config}")
            return self._config
            
        except Exception as e:
            logger.error(f"❌ Anthropic 설정 로드 실패: {e}")
            # 기본 설정 사용
            self._config = AnthropicConfig()
            return self._config
    
    def get_config(self) -> AnthropicConfig:
        """현재 설정 조회"""
        if not self._config:
            return self.load_config()
        return self._config
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """
        설정 동적 업데이트
        
        Args:
            updates: 업데이트할 설정값들
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            if not self._config:
                self.load_config()
            
            # 설정 백업
            backup_config = AnthropicConfig.from_dict(self._config.to_dict())
            
            # 업데이트 적용
            for key, value in updates.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
                    logger.info(f"설정 업데이트: {key} = {value}")
                else:
                    logger.warning(f"알 수 없는 설정 키: {key}")
            
            # 업데이트된 설정 검증
            validation_errors = self._config.validate()
            if validation_errors:
                logger.error(f"설정 검증 실패: {validation_errors}")
                # 백업 복원
                self._config = backup_config
                return False
            
            self._last_reload = datetime.now()
            logger.info("✅ 설정 업데이트 성공")
            return True
            
        except Exception as e:
            logger.error(f"❌ 설정 업데이트 실패: {e}")
            return False
    
    def get_model_config(self, use_case: str) -> Dict[str, str]:
        """사용 사례별 모델 설정 조회"""
        config = self.get_config()
        return config.get_model_config(use_case)
    
    def is_technique_enabled(self, technique: str) -> bool:
        """특정 기법 활성화 여부 확인"""
        config = self.get_config()
        return config.is_technique_enabled(technique)
    
    def get_quality_threshold(self) -> float:
        """품질 임계값 조회"""
        config = self.get_config()
        return config.quality_threshold
    
    def get_constitutional_weights(self) -> Dict[str, float]:
        """Constitutional AI 가중치 조회"""
        config = self.get_config()
        return config.constitutional_weights.copy()
    
    def update_quality_threshold(self, threshold: float) -> bool:
        """품질 임계값 업데이트"""
        return self.update_config({"quality_threshold": threshold})
    
    def update_constitutional_weights(self, weights: Dict[str, float]) -> bool:
        """Constitutional AI 가중치 업데이트"""
        config = self.get_config()
        config.update_constitutional_weights(weights)
        return True
    
    def enable_technique(self, technique: str) -> bool:
        """특정 기법 활성화"""
        config = self.get_config()
        config.enable_technique(technique)
        return True
    
    def disable_technique(self, technique: str) -> bool:
        """특정 기법 비활성화"""
        config = self.get_config()
        config.disable_technique(technique)
        return True
    
    def get_admin_settings(self) -> Dict[str, Any]:
        """관리자 친화적 설정 조회"""
        return {
            "web_interface_enabled": self._get_bool_env("ANTHROPIC_ADMIN_ENABLE_WEB_INTERFACE", True),
            "api_access_enabled": self._get_bool_env("ANTHROPIC_ADMIN_ENABLE_API_ACCESS", True),
            "hot_reload_enabled": self._get_bool_env("ANTHROPIC_ADMIN_ENABLE_HOT_RELOAD", True),
            "backup_on_change": self._get_bool_env("ANTHROPIC_ADMIN_BACKUP_ON_CHANGE", True),
            "version_control_enabled": self._get_bool_env("ANTHROPIC_ADMIN_ENABLE_VERSION_CONTROL", True),
            "audit_log_enabled": self._get_bool_env("ANTHROPIC_ADMIN_ENABLE_AUDIT_LOG", True),
            "max_history_entries": self._get_int_env("ANTHROPIC_ADMIN_MAX_HISTORY_ENTRIES", 100),
            "backup_frequency": os.getenv("ANTHROPIC_ADMIN_BACKUP_FREQUENCY", "daily"),
            "retention_period": self._get_int_env("ANTHROPIC_ADMIN_RETENTION_PERIOD", 90),
            "auto_validate": self._get_bool_env("ANTHROPIC_ADMIN_AUTO_VALIDATE_CHANGES", True),
            "test_before_apply": self._get_bool_env("ANTHROPIC_ADMIN_TEST_BEFORE_APPLY", True),
            "rollback_on_failure": self._get_bool_env("ANTHROPIC_ADMIN_ROLLBACK_ON_FAILURE", True)
        }
    
    def get_notification_settings(self) -> Dict[str, Any]:
        """알림 설정 조회"""
        channels = os.getenv("ANTHROPIC_NOTIFICATIONS_CHANNELS", "email").split(",")
        return {
            "enabled": self._get_bool_env("ANTHROPIC_NOTIFICATIONS_ENABLE_CHANGE_NOTIFICATIONS", True),
            "channels": [ch.strip() for ch in channels],
            "email": {
                "enabled": self._get_bool_env("ANTHROPIC_NOTIFICATIONS_EMAIL_ENABLED", True),
                "recipients": os.getenv("ANTHROPIC_NOTIFICATIONS_EMAIL_RECIPIENTS", "").split(",")
            },
            "slack": {
                "webhook_url": os.getenv("ANTHROPIC_NOTIFICATIONS_SLACK_WEBHOOK_URL"),
                "channel": os.getenv("ANTHROPIC_NOTIFICATIONS_SLACK_CHANNEL", "#ai-alerts")
            },
            "webhook": {
                "url": os.getenv("ANTHROPIC_NOTIFICATIONS_WEBHOOK_URL"),
                "secret": os.getenv("ANTHROPIC_NOTIFICATIONS_WEBHOOK_SECRET")
            },
            "notify_on": {
                "prompt_changes": self._get_bool_env("ANTHROPIC_NOTIFICATIONS_NOTIFY_ON_PROMPT_CHANGES", True),
                "quality_updates": self._get_bool_env("ANTHROPIC_NOTIFICATIONS_NOTIFY_ON_QUALITY_THRESHOLD_UPDATES", True),
                "system_errors": self._get_bool_env("ANTHROPIC_NOTIFICATIONS_NOTIFY_ON_SYSTEM_ERRORS", True),
                "backup_completion": self._get_bool_env("ANTHROPIC_NOTIFICATIONS_NOTIFY_ON_BACKUP_COMPLETION", True)
            }
        }
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """성능 설정 조회"""
        config = self.get_config()
        return config.performance_settings.copy()
    
    def get_monitoring_settings(self) -> Dict[str, Any]:
        """모니터링 설정 조회"""
        config = self.get_config()
        return config.monitoring_settings.copy()
    
    def get_experimental_features(self) -> Dict[str, bool]:
        """실험적 기능 설정 조회"""
        config = self.get_config()
        return config.experimental_features.copy()
    
    def export_config(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """설정 내보내기"""
        config = self.get_config()
        exported = config.to_dict()
        
        if not include_sensitive:
            # 민감한 정보 제거
            sensitive_keys = ['api_key', 'secret', 'password', 'token']
            self._remove_sensitive_keys(exported, sensitive_keys)
        
        exported['export_metadata'] = {
            "exported_at": datetime.now().isoformat(),
            "version": "1.0.0",
            "validation_errors": self._validation_errors
        }
        
        return exported
    
    def import_config(self, config_data: Dict[str, Any]) -> bool:
        """설정 가져오기"""
        try:
            # 메타데이터 제거
            config_data.pop('export_metadata', None)
            
            # 새 설정 생성 및 검증
            new_config = AnthropicConfig.from_dict(config_data)
            validation_errors = new_config.validate()
            
            if validation_errors:
                logger.error(f"가져온 설정 검증 실패: {validation_errors}")
                return False
            
            # 설정 적용
            self._config = new_config
            self._last_reload = datetime.now()
            
            logger.info("✅ 설정 가져오기 성공")
            return True
            
        except Exception as e:
            logger.error(f"❌ 설정 가져오기 실패: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """기본 설정으로 재설정"""
        try:
            self._config = AnthropicConfig()
            self._last_reload = datetime.now()
            self._validation_errors = []
            
            logger.info("✅ 기본 설정으로 재설정 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 기본 설정 재설정 실패: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """설정 관리자 상태 조회"""
        config = self.get_config()
        
        return {
            "config_loaded": self._config is not None,
            "last_reload": self._last_reload.isoformat() if self._last_reload else None,
            "validation_errors": self._validation_errors,
            "cache_enabled": self._enable_config_cache,
            "cache_ttl": self._config_cache_ttl,
            "templates_dir": str(self.templates_dir),
            "config_summary": {
                "enabled": config.enabled,
                "quality_threshold": config.quality_threshold,
                "enabled_techniques": len(config.enabled_techniques),
                "total_techniques": len(config.supported_techniques),
                "model_provider": config.model_provider,
                "model_name": config.model_name
            }
        }
    
    def _adjust_for_environment(self):
        """개발/운영 환경에 따른 설정 자동 조정"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        
        if env == "development":
            # 개발 환경: 더 관대한 품질 임계값, 상세한 로깅
            if self._config.quality_threshold > 0.9:
                self._config.quality_threshold = 0.7
                logger.info("개발 환경: 품질 임계값을 0.7로 조정")
            
            self._config.monitoring_settings['log_level'] = 'DEBUG'
            self._config.performance_settings['enable_caching'] = False  # 개발 중 캐시 비활성화
            
        elif env == "production":
            # 운영 환경: 엄격한 품질 관리, 성능 최적화
            if self._config.quality_threshold < 0.8:
                self._config.quality_threshold = 0.8
                logger.info("운영 환경: 품질 임계값을 0.8로 조정")
            
            self._config.monitoring_settings['log_level'] = 'INFO'
            self._config.performance_settings['enable_caching'] = True
            self._config.max_retries = 3  # 운영에서는 더 많은 재시도
    
    def _remove_sensitive_keys(self, data: Dict[str, Any], sensitive_keys: List[str]):
        """민감한 키 제거 (재귀적)"""
        for key in list(data.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                data[key] = "***REDACTED***"
            elif isinstance(data[key], dict):
                self._remove_sensitive_keys(data[key], sensitive_keys)
    
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
            return default


# 전역 설정 인스턴스
anthropic_settings = AnthropicSettings()


# 편의 함수들
def get_anthropic_config() -> AnthropicConfig:
    """Anthropic 설정 조회"""
    return anthropic_settings.get_config()


def reload_anthropic_config() -> AnthropicConfig:
    """Anthropic 설정 다시 로드"""
    return anthropic_settings.load_config(force_reload=True)


def update_anthropic_config(updates: Dict[str, Any]) -> bool:
    """Anthropic 설정 업데이트"""
    return anthropic_settings.update_config(updates)


def get_model_config(use_case: str) -> Dict[str, str]:
    """사용 사례별 모델 설정 조회"""
    return anthropic_settings.get_model_config(use_case)


def is_anthropic_enabled() -> bool:
    """Anthropic 기능 활성화 여부 확인"""
    config = get_anthropic_config()
    return config.enabled


def is_technique_enabled(technique: str) -> bool:
    """특정 기법 활성화 여부 확인"""
    return anthropic_settings.is_technique_enabled(technique)


def get_quality_threshold() -> float:
    """품질 임계값 조회"""
    return anthropic_settings.get_quality_threshold()


def get_constitutional_weights() -> Dict[str, float]:
    """Constitutional AI 가중치 조회"""
    return anthropic_settings.get_constitutional_weights()