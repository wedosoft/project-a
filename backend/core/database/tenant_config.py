"""
멀티테넌트 설정 관리자
테넌트별 설정을 데이터베이스에서 관리하며, 환경변수는 시스템 레벨에서만 사용
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import base64

logger = logging.getLogger(__name__)

# 암호화 라이브러리 선택적 임포트
try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    logger.warning("cryptography 라이브러리 없음. 암호화 기능 비활성화")
    ENCRYPTION_AVAILABLE = False
    Fernet = None

class TenantConfigManager:
    """테넌트별 설정 관리 클래스"""
    
    def __init__(self, tenant_id: str = None, platform: str = "freshdesk", db_instance=None):
        """
        Args:
            tenant_id: 테넌트 ID (db_instance가 없을 때 사용)
            platform: 플랫폼명 (db_instance가 없을 때 사용)
            db_instance: 데이터베이스 인스턴스 (SQLite 또는 PostgreSQL)
        """
        if db_instance:
            self.db = db_instance
        else:
            from .database import get_database
            self.db = get_database(tenant_id, platform)
        
        self.tenant_id = tenant_id
        self.platform = platform
        self._encryption_key = self._get_or_create_encryption_key()
    
    def _get_or_create_encryption_key(self) -> Optional[bytes]:
        """암호화 키 생성 또는 가져오기"""
        if not ENCRYPTION_AVAILABLE:
            logger.info("암호화 라이브러리 없음. 암호화 비활성화")
            return None
            
        # 시스템 설정에서 암호화 키 조회
        key_setting = self.get_system_setting('tenant_config_encryption_key')
        
        if key_setting:
            return base64.b64decode(key_setting.encode())
        else:
            # 새 키 생성 및 저장
            key = Fernet.generate_key()
            self.set_system_setting(
                'tenant_config_encryption_key', 
                base64.b64encode(key).decode(),
                encrypted=False,  # 키 자체는 암호화하지 않음
                description='테넌트 설정 암호화용 마스터 키'
            )
            return key
    
    def _encrypt_value(self, value: str) -> str:
        """값 암호화"""
        if not ENCRYPTION_AVAILABLE or not self._encryption_key:
            logger.warning("암호화 불가능. 원본 값 반환")
            return value
            
        f = Fernet(self._encryption_key)
        return f.encrypt(value.encode()).decode()
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """값 복호화"""
        if not ENCRYPTION_AVAILABLE or not self._encryption_key:
            logger.warning("복호화 불가능. 원본 값 반환")
            return encrypted_value
            
        try:
            f = Fernet(self._encryption_key)
            return f.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            logger.error(f"복호화 실패: {e}")
            return encrypted_value
        """값 복호화"""
        f = Fernet(self._encryption_key)
        return f.decrypt(encrypted_value.encode()).decode()
    
    # =====================================================
    # 테넌트별 설정 관리
    # =====================================================
    
    def set_tenant_setting(self, tenant_id: int, key: str, value: Any, 
                          encrypted: bool = False, description: str = None) -> bool:
        """테넌트 설정 저장
        
        Args:
            tenant_id: 테넌트 ID
            key: 설정 키
            value: 설정 값
            encrypted: 암호화 여부
            description: 설명
        """
        if not self.db.connection:
            self.db.connect()
        
        cursor = self.db.connection.cursor()
        
        # 값 처리
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        # 암호화 처리
        if encrypted:
            value_str = self._encrypt_value(value_str)
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO company_settings (
                    tenant_id, setting_key, setting_value, is_encrypted,
                    description, updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (tenant_id, key, value_str, encrypted, description))
            
            self.db.connection.commit()
            logger.info(f"테넌트 설정 저장: tenant_id={tenant_id}, key={key}")
            return True
            
        except Exception as e:
            logger.error(f"테넌트 설정 저장 실패: {e}")
            return False
    
    def get_tenant_setting(self, tenant_id: int, key: str, default: Any = None) -> Any:
        """테넌트 설정 조회
        
        Args:
            tenant_id: 테넌트 ID
            key: 설정 키
            default: 기본값
        """
        if not self.db.connection:
            self.db.connect()
        
        cursor = self.db.connection.cursor()
        
        try:
            cursor.execute("""
                SELECT setting_value, is_encrypted FROM company_settings 
                WHERE tenant_id = ? AND setting_key = ?
            """, (tenant_id, key))
            
            row = cursor.fetchone()
            if not row:
                return default
            
            value_str, is_encrypted = row
            
            # 복호화 처리
            if is_encrypted:
                value_str = self._decrypt_value(value_str)
            
            # JSON 파싱 시도
            try:
                return json.loads(value_str)
            except (json.JSONDecodeError, TypeError):
                return value_str
                
        except Exception as e:
            logger.error(f"테넌트 설정 조회 실패: {e}")
            return default
    
    def get_all_tenant_settings(self, tenant_id: int) -> Dict[str, Any]:
        """테넌트의 모든 설정 조회"""
        if not self.db.connection:
            self.db.connect()
        
        cursor = self.db.connection.cursor()
        
        try:
            cursor.execute("""
                SELECT setting_key, setting_value, is_encrypted, description 
                FROM company_settings WHERE tenant_id = ?
            """, (tenant_id,))
            
            settings = {}
            for row in cursor.fetchall():
                key, value_str, is_encrypted, description = row
                
                # 복호화 처리
                if is_encrypted:
                    try:
                        value_str = self._decrypt_value(value_str)
                    except Exception as e:
                        logger.error(f"설정 복호화 실패: {key}, {e}")
                        continue
                
                # JSON 파싱 시도
                try:
                    value = json.loads(value_str)
                except (json.JSONDecodeError, TypeError):
                    value = value_str
                
                settings[key] = {
                    'value': value,
                    'encrypted': is_encrypted,
                    'description': description
                }
            
            return settings
            
        except Exception as e:
            logger.error(f"테넌트 설정 전체 조회 실패: {e}")
            return {}
    
    def delete_tenant_setting(self, tenant_id: int, key: str) -> bool:
        """테넌트 설정 삭제"""
        if not self.db.connection:
            self.db.connect()
        
        cursor = self.db.connection.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM company_settings 
                WHERE tenant_id = ? AND setting_key = ?
            """, (tenant_id, key))
            
            self.db.connection.commit()
            deleted = cursor.rowcount > 0
            
            if deleted:
                logger.info(f"테넌트 설정 삭제: tenant_id={tenant_id}, key={key}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"테넌트 설정 삭제 실패: {e}")
            return False
    
    # =====================================================
    # 시스템 설정 관리 (전체 플랫폼 공통)
    # =====================================================
    
    def set_system_setting(self, key: str, value: Any, encrypted: bool = False, 
                          description: str = None) -> bool:
        """시스템 설정 저장"""
        if not self.db.connection:
            self.db.connect()
        
        cursor = self.db.connection.cursor()
        
        # 값 처리
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        # 암호화 처리
        if encrypted:
            value_str = self._encrypt_value(value_str)
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO system_settings (
                    setting_key, setting_value, is_encrypted, description, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value_str, encrypted, description))
            
            self.db.connection.commit()
            logger.info(f"시스템 설정 저장: key={key}")
            return True
            
        except Exception as e:
            logger.error(f"시스템 설정 저장 실패: {e}")
            return False
    
    def get_system_setting(self, key: str, default: Any = None) -> Any:
        """시스템 설정 조회"""
        if not self.db.connection:
            self.db.connect()
        
        cursor = self.db.connection.cursor()
        
        try:
            cursor.execute("""
                SELECT setting_value, is_encrypted FROM system_settings 
                WHERE setting_key = ?
            """, (key,))
            
            row = cursor.fetchone()
            if not row:
                return default
            
            value_str, is_encrypted = row
            
            # 복호화 처리
            if is_encrypted:
                value_str = self._decrypt_value(value_str)
            
            # JSON 파싱 시도
            try:
                return json.loads(value_str)
            except (json.JSONDecodeError, TypeError):
                return value_str
                
        except Exception as e:
            logger.error(f"시스템 설정 조회 실패: {e}")
            return default
    
    # =====================================================
    # 플랫폼별 설정 관리 (고급 기능)
    # =====================================================
    
    def set_platform_config(self, tenant_id: int, platform: str, config: Dict[str, Any]) -> bool:
        """플랫폼별 설정 저장
        
        Args:
            tenant_id: 테넌트 ID
            platform: 플랫폼명 (freshdesk, zendesk 등)
            config: 플랫폼 설정 딕셔너리
        """
        key = f"platform_config_{platform}"
        return self.set_tenant_setting(
            tenant_id, 
            key, 
            config, 
            encrypted=True,  # 플랫폼 설정은 보안상 암호화
            description=f"{platform} 플랫폼 연동 설정"
        )
    
    def get_platform_config(self, tenant_id: int, platform: str) -> Dict[str, Any]:
        """플랫폼별 설정 조회"""
        key = f"platform_config_{platform}"
        return self.get_tenant_setting(tenant_id, key, {})
    
    def get_freshdesk_config(self, tenant_id: int) -> Dict[str, Any]:
        """Freshdesk 설정 조회 (편의 메서드)"""
        config = self.get_platform_config(tenant_id, 'freshdesk')
        
        # 기본값 설정
        defaults = {
            'domain': None,
            'api_key': None,
            'rate_limit': 100,  # API 호출 제한
            'timeout': 30,
            'retry_count': 3,
            'collect_attachments': True,
            'collect_private_notes': True
        }
        
        return {**defaults, **config}
    
    def set_freshdesk_config(self, tenant_id: int, domain: str, api_key: str, 
                           **kwargs) -> bool:
        """Freshdesk 설정 저장 (편의 메서드)"""
        config = {
            'domain': domain,
            'api_key': api_key,
            **kwargs
        }
        return self.set_platform_config(tenant_id, 'freshdesk', config)
    
    # =====================================================
    # 설정 템플릿 및 유틸리티
    # =====================================================
    
    def create_tenant_from_template(self, template_tenant_id: int, 
                                   new_tenant_id: int) -> bool:
        """템플릿을 사용하여 새 테넌트 설정 생성"""
        try:
            template_settings = self.get_all_tenant_settings(template_tenant_id)
            
            for key, setting_info in template_settings.items():
                # 민감한 정보는 복사하지 않음
                if 'api_key' in key.lower() or 'password' in key.lower():
                    continue
                
                self.set_tenant_setting(
                    new_tenant_id,
                    key,
                    setting_info['value'],
                    setting_info['encrypted'],
                    setting_info['description']
                )
            
            logger.info(f"템플릿 기반 테넌트 생성: {template_tenant_id} -> {new_tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"템플릿 기반 테넌트 생성 실패: {e}")
            return False
    
    def validate_tenant_config(self, tenant_id: int, platform: str) -> Dict[str, Any]:
        """테넌트 설정 유효성 검증"""
        validation = {
            'tenant_id': tenant_id,
            'platform': platform,
            'is_valid': True,
            'missing_settings': [],
            'invalid_settings': [],
            'warnings': []
        }
        
        # 플랫폼별 필수 설정 확인
        if platform == 'freshdesk':
            config = self.get_freshdesk_config(tenant_id)
            
            if not config.get('domain'):
                validation['missing_settings'].append('freshdesk.domain')
                validation['is_valid'] = False
            
            if not config.get('api_key'):
                validation['missing_settings'].append('freshdesk.api_key')
                validation['is_valid'] = False
            
            # API 키 형식 검증 (기본적인 체크)
            if config.get('api_key') and len(config['api_key']) < 20:
                validation['invalid_settings'].append('freshdesk.api_key')
                validation['warnings'].append('API 키 형식이 올바르지 않을 수 있습니다')
        
        return validation

# =====================================================
# 편의 함수들
# =====================================================

def get_tenant_config_manager(tenant_id: str, platform: str = "freshdesk"):
    """테넌트 설정 관리자 인스턴스 반환"""
    from .database import get_database
    
    db = get_database(tenant_id, platform)
    return TenantConfigManager(db)

def setup_new_tenant(tenant_id: int, company_name: str, platform: str,
                    platform_config: Dict[str, Any]) -> bool:
    """새 테넌트 설정 초기화"""
    try:
        # 임시로 시스템 DB 사용 (실제로는 마스터 DB 사용해야 함)
        from .database import get_database
        
        db = get_database("system", "master")
        config_manager = TenantConfigManager(db)
        
        # 기본 설정 저장
        config_manager.set_tenant_setting(tenant_id, 'company_name', company_name)
        config_manager.set_tenant_setting(tenant_id, 'primary_platform', platform)
        config_manager.set_tenant_setting(tenant_id, 'created_at', datetime.now().isoformat())
        
        # 플랫폼 설정 저장
        config_manager.set_platform_config(tenant_id, platform, platform_config)
        
        logger.info(f"새 테넌트 설정 완료: tenant_id={tenant_id}, platform={platform}")
        return True
        
    except Exception as e:
        logger.error(f"새 테넌트 설정 실패: {e}")
        return False
