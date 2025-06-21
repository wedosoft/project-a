# -*- coding: utf-8 -*-
"""
프로젝트 설정 관리 모듈

환경별 설정과 doc_id 관련 정책을 중앙에서 관리합니다.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import DocType, SystemConfig


class Environment(Enum):
    """환경 타입"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DocIdPolicy:
    """Doc ID 정책 설정"""
    
    # 필수 접두어 사용 여부
    require_prefix: bool = True
    
    # 접두어 검증 엄격도
    strict_validation: bool = True
    
    # 자동 보정 허용 여부
    auto_correction: bool = True
    
    # 레거시 ID 지원 여부
    support_legacy_ids: bool = False
    
    # 새로운 doc_type 추가 허용 여부
    allow_new_doc_types: bool = False
    
    # 청크 ID 최대 길이
    max_chunk_id_length: int = 255
    
    # 사용자 정의 접두어
    custom_prefixes: Dict[str, str] = field(default_factory=dict)


@dataclass
class ProjectSettings:
    """프로젝트 전체 설정"""
    
    # 환경 설정
    environment: Environment = Environment.DEVELOPMENT
    
    # 기본 company_id
    default_company_id: str = SystemConfig.DEFAULT_COMPANY_ID
    
    # Doc ID 정책
    doc_id_policy: DocIdPolicy = field(default_factory=DocIdPolicy)
    
    # 데이터 검증 설정
    enable_data_validation: bool = True
    validation_on_ingest: bool = True
    validation_on_retrieval: bool = False
    
    # 캐싱 설정
    enable_doc_id_cache: bool = True
    cache_ttl_seconds: int = 3600
    
    # 로깅 설정
    log_doc_id_operations: bool = True
    log_validation_warnings: bool = True
    
    # 마이그레이션 설정
    auto_migrate_legacy_ids: bool = False
    migration_backup_enabled: bool = True
    
    # 확장성 설정
    plugin_directories: List[str] = field(default_factory=list)
    custom_validators: List[str] = field(default_factory=list)


class SettingsManager:
    """설정 관리 클래스"""
    
    _instance: Optional['SettingsManager'] = None
    _settings: Optional[ProjectSettings] = None
    
    def __new__(cls) -> 'SettingsManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._settings is None:
            self._settings = self._load_settings()
    
    def _load_settings(self) -> ProjectSettings:
        """환경변수에서 설정 로드"""
        env_name = os.getenv('ENVIRONMENT', 'development').lower()
        
        try:
            environment = Environment(env_name)
        except ValueError:
            environment = Environment.DEVELOPMENT
        
        # Doc ID 정책 설정
        doc_id_policy = DocIdPolicy(
            require_prefix=os.getenv('DOC_ID_REQUIRE_PREFIX', 'true').lower() == 'true',
            strict_validation=os.getenv('DOC_ID_STRICT_VALIDATION', 'true').lower() == 'true',
            auto_correction=os.getenv('DOC_ID_AUTO_CORRECTION', 'true').lower() == 'true',
            support_legacy_ids=os.getenv('DOC_ID_SUPPORT_LEGACY', 'false').lower() == 'true',
            allow_new_doc_types=os.getenv('DOC_ID_ALLOW_NEW_TYPES', 'false').lower() == 'true',
            max_chunk_id_length=int(os.getenv('DOC_ID_MAX_CHUNK_LENGTH', '255')),
        )
        
        # 사용자 정의 접두어 로드
        custom_prefixes_str = os.getenv('DOC_ID_CUSTOM_PREFIXES', '')
        if custom_prefixes_str:
            try:
                import json
                doc_id_policy.custom_prefixes = json.loads(custom_prefixes_str)
            except json.JSONDecodeError:
                pass
        
        # 전체 설정 구성
        settings = ProjectSettings(
            environment=environment,
            default_company_id=os.getenv('COMPANY_ID', SystemConfig.DEFAULT_COMPANY_ID),
            doc_id_policy=doc_id_policy,
            enable_data_validation=os.getenv('ENABLE_DATA_VALIDATION', 'true').lower() == 'true',
            validation_on_ingest=os.getenv('VALIDATION_ON_INGEST', 'true').lower() == 'true',
            validation_on_retrieval=os.getenv('VALIDATION_ON_RETRIEVAL', 'false').lower() == 'true',
            enable_doc_id_cache=os.getenv('ENABLE_DOC_ID_CACHE', 'true').lower() == 'true',
            cache_ttl_seconds=int(os.getenv('DOC_ID_CACHE_TTL', '3600')),
            log_doc_id_operations=os.getenv('LOG_DOC_ID_OPS', 'true').lower() == 'true',
            log_validation_warnings=os.getenv('LOG_VALIDATION_WARNINGS', 'true').lower() == 'true',
            auto_migrate_legacy_ids=os.getenv('AUTO_MIGRATE_LEGACY_IDS', 'false').lower() == 'true',
            migration_backup_enabled=os.getenv('MIGRATION_BACKUP', 'true').lower() == 'true',
        )
        
        return settings
    
    @property
    def settings(self) -> ProjectSettings:
        """현재 설정 반환"""
        return self._settings
    
    def update_doc_id_policy(self, **kwargs) -> None:
        """Doc ID 정책 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self._settings.doc_id_policy, key):
                setattr(self._settings.doc_id_policy, key, value)
    
    def get_environment_config(self) -> Dict[str, Any]:
        """환경별 설정 반환"""
        env_configs = {
            Environment.DEVELOPMENT: {
                'debug_mode': True,
                'strict_validation': False,
                'auto_correction': True,
                'log_level': 'DEBUG'
            },
            Environment.STAGING: {
                'debug_mode': True,
                'strict_validation': True,
                'auto_correction': True,
                'log_level': 'INFO'
            },
            Environment.PRODUCTION: {
                'debug_mode': False,
                'strict_validation': True,
                'auto_correction': False,
                'log_level': 'WARNING'
            }
        }
        
        return env_configs.get(self._settings.environment, env_configs[Environment.DEVELOPMENT])
    
    def validate_settings(self) -> List[str]:
        """설정 유효성 검사"""
        issues = []
        
        # Doc ID 정책 검증
        policy = self._settings.doc_id_policy
        
        if policy.require_prefix and not policy.strict_validation:
            issues.append("접두어가 필수인 경우 엄격한 검증이 권장됩니다.")
        
        if policy.support_legacy_ids and policy.strict_validation:
            issues.append("레거시 ID 지원과 엄격한 검증은 충돌할 수 있습니다.")
        
        if policy.max_chunk_id_length < 50:
            issues.append("청크 ID 최대 길이가 너무 짧습니다.")
        
        # 환경별 검증
        if self._settings.environment == Environment.PRODUCTION:
            if policy.auto_correction:
                issues.append("프로덕션 환경에서는 자동 보정을 비활성화하는 것이 권장됩니다.")
            
            if self._settings.log_doc_id_operations:
                issues.append("프로덕션 환경에서는 상세한 로깅을 제한하는 것이 권장됩니다.")
        
        return issues
    
    def export_config(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """설정을 딕셔너리로 내보내기"""
        config = {
            'environment': self._settings.environment.value,
            'default_company_id': self._settings.default_company_id,
            'doc_id_policy': {
                'require_prefix': self._settings.doc_id_policy.require_prefix,
                'strict_validation': self._settings.doc_id_policy.strict_validation,
                'auto_correction': self._settings.doc_id_policy.auto_correction,
                'support_legacy_ids': self._settings.doc_id_policy.support_legacy_ids,
                'allow_new_doc_types': self._settings.doc_id_policy.allow_new_doc_types,
                'max_chunk_id_length': self._settings.doc_id_policy.max_chunk_id_length,
                'custom_prefixes': self._settings.doc_id_policy.custom_prefixes,
            },
            'validation': {
                'enable_data_validation': self._settings.enable_data_validation,
                'validation_on_ingest': self._settings.validation_on_ingest,
                'validation_on_retrieval': self._settings.validation_on_retrieval,
            },
            'caching': {
                'enable_doc_id_cache': self._settings.enable_doc_id_cache,
                'cache_ttl_seconds': self._settings.cache_ttl_seconds,
            },
            'logging': {
                'log_doc_id_operations': self._settings.log_doc_id_operations,
                'log_validation_warnings': self._settings.log_validation_warnings,
            },
            'migration': {
                'auto_migrate_legacy_ids': self._settings.auto_migrate_legacy_ids,
                'migration_backup_enabled': self._settings.migration_backup_enabled,
            }
        }
        
        if file_path:
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        
        return config


# 전역 설정 인스턴스
settings_manager = SettingsManager()
settings = settings_manager.settings
