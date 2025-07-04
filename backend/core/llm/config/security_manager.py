"""
보안 강화된 설정 관리 시스템

이 모듈은 다음 보안 기능을 제공합니다:
1. 민감한 정보 암호화/복호화
2. 접근 권한 제어
3. 감사 로깅
4. 시크릿 로테이션
5. 보안 정책 적용
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import hmac
import secrets
from pathlib import Path

# 암호화 라이브러리
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    import base64
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    
logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """보안 수준"""
    PUBLIC = "public"           # 공개 정보
    INTERNAL = "internal"       # 내부 정보
    CONFIDENTIAL = "confidential"  # 기밀 정보
    SECRET = "secret"          # 비밀 정보
    TOP_SECRET = "top_secret"  # 최고 기밀


class AccessRole(Enum):
    """접근 역할"""
    READONLY = "readonly"
    DEVELOPER = "developer"
    ADMIN = "admin"
    SECURITY_ADMIN = "security_admin"


@dataclass
class SecurityPolicy:
    """보안 정책"""
    encryption_required: bool
    access_roles: List[AccessRole]
    audit_logging: bool
    rotation_days: int
    backup_required: bool
    ip_whitelist: List[str] = field(default_factory=list)
    time_restrictions: Dict[str, str] = field(default_factory=dict)


@dataclass
class AuditLogEntry:
    """감사 로그 항목"""
    timestamp: str
    user_id: str
    action: str
    resource: str
    result: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


class SecureConfigManager:
    """보안 강화된 설정 관리자"""
    
    def __init__(self, master_key: Optional[str] = None):
        if not HAS_CRYPTO:
            logger.warning("cryptography 패키지가 설치되지 않았습니다. 암호화 기능이 비활성화됩니다.")
            
        self.master_key = master_key or self._get_master_key()
        self.cipher_suite = self._initialize_encryption() if HAS_CRYPTO else None
        
        # 보안 정책들
        self.security_policies = self._load_security_policies()
        
        # 감사 로그
        self.audit_log: List[AuditLogEntry] = []
        self.log_file_path = os.getenv('SECURITY_AUDIT_LOG', 'security_audit.log')
        
        # 접근 제어
        self.current_user = os.getenv('USER', 'unknown')
        self.current_role = self._determine_user_role()
        
        logger.info(f"보안 설정 관리자 초기화 - 사용자: {self.current_user}, 역할: {self.current_role.value}")
    
    def _get_master_key(self) -> str:
        """마스터 키 조회"""
        # 1. 환경변수에서 조회
        master_key = os.getenv('CONFIG_MASTER_KEY')
        if master_key:
            return master_key
        
        # 2. 키 파일에서 조회
        key_file = Path.home() / '.llm' / 'master.key'
        if key_file.exists():
            try:
                with open(key_file, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"키 파일 읽기 실패: {e}")
        
        # 3. 새 키 생성
        new_key = self._generate_master_key()
        
        # 키 파일에 저장 (안전한 권한으로)
        try:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, 'w') as f:
                f.write(new_key)
            os.chmod(key_file, 0o600)  # 소유자만 읽기/쓰기
            logger.info(f"새 마스터 키 생성 및 저장: {key_file}")
        except Exception as e:
            logger.warning(f"키 파일 저장 실패: {e}")
        
        return new_key
    
    def _generate_master_key(self) -> str:
        """새 마스터 키 생성"""
        if HAS_CRYPTO:
            return Fernet.generate_key().decode()
        else:
            # 폴백: 간단한 랜덤 키
            return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    
    def _initialize_encryption(self) -> Optional[Fernet]:
        """암호화 시스템 초기화"""
        if not HAS_CRYPTO:
            return None
            
        try:
            # 마스터 키를 Fernet 키로 변환
            if len(self.master_key) == 44 and self.master_key.endswith('='):
                # 이미 Fernet 키 형태
                return Fernet(self.master_key.encode())
            else:
                # 패스워드에서 키 유도
                password = self.master_key.encode()
                salt = b'llm_config_salt'  # 실제로는 랜덤 salt 사용 권장
                
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password))
                return Fernet(key)
                
        except Exception as e:
            logger.error(f"암호화 초기화 실패: {e}")
            return None
    
    def _load_security_policies(self) -> Dict[str, SecurityPolicy]:
        """보안 정책 로드"""
        return {
            "api_keys": SecurityPolicy(
                encryption_required=True,
                access_roles=[AccessRole.ADMIN, AccessRole.SECURITY_ADMIN],
                audit_logging=True,
                rotation_days=90,
                backup_required=True,
                ip_whitelist=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
            ),
            "database_credentials": SecurityPolicy(
                encryption_required=True,
                access_roles=[AccessRole.ADMIN, AccessRole.SECURITY_ADMIN],
                audit_logging=True,
                rotation_days=60,
                backup_required=True
            ),
            "model_registry": SecurityPolicy(
                encryption_required=False,
                access_roles=[AccessRole.READONLY, AccessRole.DEVELOPER, AccessRole.ADMIN],
                audit_logging=True,
                rotation_days=365,
                backup_required=True
            ),
            "environment_configs": SecurityPolicy(
                encryption_required=False,
                access_roles=[AccessRole.DEVELOPER, AccessRole.ADMIN],
                audit_logging=True,
                rotation_days=30,
                backup_required=True
            )
        }
    
    def _determine_user_role(self) -> AccessRole:
        """현재 사용자의 역할 결정"""
        # 환경변수에서 역할 확인
        role_env = os.getenv('LLM_USER_ROLE', '').lower()
        if role_env:
            try:
                return AccessRole(role_env)
            except ValueError:
                pass
        
        # 사용자명 기반 역할 결정 (예시)
        if self.current_user in ['root', 'admin']:
            return AccessRole.ADMIN
        elif self.current_user.startswith('dev'):
            return AccessRole.DEVELOPER
        else:
            return AccessRole.READONLY
    
    def encrypt_sensitive_data(self, data: Dict[str, Any], security_level: SecurityLevel) -> Dict[str, Any]:
        """민감한 데이터 암호화"""
        if not self.cipher_suite:
            logger.warning("암호화 시스템이 초기화되지 않음 - 데이터를 그대로 반환")
            return data
        
        encrypted_data = data.copy()
        
        # 보안 수준에 따른 암호화 대상 결정
        fields_to_encrypt = self._get_encryption_fields(security_level)
        
        for field_path in fields_to_encrypt:
            try:
                value = self._get_nested_value(encrypted_data, field_path)
                if value and isinstance(value, str):
                    encrypted_value = self.cipher_suite.encrypt(value.encode()).decode()
                    self._set_nested_value(encrypted_data, field_path, f"ENC[{encrypted_value}]")
                    
            except Exception as e:
                logger.error(f"암호화 실패 {field_path}: {e}")
        
        # 암호화 메타데이터 추가
        encrypted_data['_encryption_metadata'] = {
            'encrypted_at': datetime.now().isoformat(),
            'security_level': security_level.value,
            'encrypted_fields': fields_to_encrypt,
            'encryption_version': '1.0'
        }
        
        return encrypted_data
    
    def decrypt_sensitive_data(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """암호화된 데이터 복호화"""
        if not self.cipher_suite:
            logger.warning("암호화 시스템이 초기화되지 않음 - 데이터를 그대로 반환")
            return encrypted_data
        
        decrypted_data = encrypted_data.copy()
        
        # 암호화 메타데이터 확인
        metadata = decrypted_data.get('_encryption_metadata', {})
        encrypted_fields = metadata.get('encrypted_fields', [])
        
        for field_path in encrypted_fields:
            try:
                value = self._get_nested_value(decrypted_data, field_path)
                if value and isinstance(value, str) and value.startswith('ENC[') and value.endswith(']'):
                    encrypted_value = value[4:-1]  # ENC[ ... ] 제거
                    decrypted_value = self.cipher_suite.decrypt(encrypted_value.encode()).decode()
                    self._set_nested_value(decrypted_data, field_path, decrypted_value)
                    
            except Exception as e:
                logger.error(f"복호화 실패 {field_path}: {e}")
        
        # 메타데이터 제거
        decrypted_data.pop('_encryption_metadata', None)
        
        return decrypted_data
    
    def _get_encryption_fields(self, security_level: SecurityLevel) -> List[str]:
        """보안 수준에 따른 암호화 대상 필드들"""
        if security_level == SecurityLevel.SECRET or security_level == SecurityLevel.TOP_SECRET:
            return [
                'api_keys.openai.dev_key',
                'api_keys.openai.prod_key',
                'api_keys.anthropic.dev_key',
                'api_keys.anthropic.prod_key',
                'api_keys.gemini.dev_key',
                'api_keys.gemini.prod_key',
                'database.qdrant.api_key',
                'database.redis.password',
                'monitoring.datadog.api_key',
                'external_services.freshdesk.api_key',
                'encryption.config_encryption_key',
                'encryption.jwt_secret',
                'encryption.session_secret'
            ]
        elif security_level == SecurityLevel.CONFIDENTIAL:
            return [
                'api_keys.*.prod_key',
                'database.*.password',
                'encryption.*'
            ]
        else:
            return []
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """중첩된 딕셔너리에서 값 조회"""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if key == '*':
                # 와일드카드 - 모든 하위 키들을 반환
                if isinstance(current, dict):
                    return list(current.keys())
                else:
                    return None
            elif isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any):
        """중첩된 딕셔너리에 값 설정"""
        keys = path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def check_access_permission(self, resource: str, action: str) -> bool:
        """접근 권한 확인"""
        policy = self.security_policies.get(resource)
        if not policy:
            # 정책이 없으면 기본적으로 거부
            self._log_access_attempt(resource, action, "DENIED", "No policy found")
            return False
        
        # 역할 기반 접근 제어
        if self.current_role not in policy.access_roles:
            self._log_access_attempt(resource, action, "DENIED", f"Insufficient role: {self.current_role.value}")
            return False
        
        # IP 화이트리스트 확인 (구현 예시)
        if policy.ip_whitelist:
            client_ip = os.getenv('CLIENT_IP', '127.0.0.1')
            if not self._is_ip_allowed(client_ip, policy.ip_whitelist):
                self._log_access_attempt(resource, action, "DENIED", f"IP not whitelisted: {client_ip}")
                return False
        
        # 시간 제한 확인
        if policy.time_restrictions:
            if not self._is_time_allowed(policy.time_restrictions):
                self._log_access_attempt(resource, action, "DENIED", "Outside allowed time window")
                return False
        
        self._log_access_attempt(resource, action, "ALLOWED", "Access granted")
        return True
    
    def _is_ip_allowed(self, client_ip: str, whitelist: List[str]) -> bool:
        """IP 주소가 화이트리스트에 있는지 확인"""
        try:
            import ipaddress
            client_addr = ipaddress.ip_address(client_ip)
            
            for allowed_range in whitelist:
                if '/' in allowed_range:
                    # CIDR 표기법
                    network = ipaddress.ip_network(allowed_range, strict=False)
                    if client_addr in network:
                        return True
                else:
                    # 단일 IP
                    if client_addr == ipaddress.ip_address(allowed_range):
                        return True
                        
            return False
        except Exception as e:
            logger.error(f"IP 확인 오류: {e}")
            return False
    
    def _is_time_allowed(self, time_restrictions: Dict[str, str]) -> bool:
        """현재 시간이 허용 시간대인지 확인"""
        now = datetime.now()
        
        # 요일 제한
        if 'allowed_days' in time_restrictions:
            allowed_days = time_restrictions['allowed_days'].split(',')
            current_day = now.strftime('%A').lower()
            if current_day not in [day.strip().lower() for day in allowed_days]:
                return False
        
        # 시간 제한
        if 'allowed_hours' in time_restrictions:
            try:
                start_hour, end_hour = map(int, time_restrictions['allowed_hours'].split('-'))
                current_hour = now.hour
                if not (start_hour <= current_hour <= end_hour):
                    return False
            except ValueError:
                logger.error("시간 제한 형식 오류")
                return False
        
        return True
    
    def _log_access_attempt(self, resource: str, action: str, result: str, reason: str):
        """접근 시도 로깅"""
        log_entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            user_id=self.current_user,
            action=action,
            resource=resource,
            result=result,
            ip_address=os.getenv('CLIENT_IP'),
            user_agent=os.getenv('HTTP_USER_AGENT'),
            additional_info={'reason': reason, 'role': self.current_role.value}
        )
        
        self.audit_log.append(log_entry)
        self._write_audit_log(log_entry)
    
    def _write_audit_log(self, log_entry: AuditLogEntry):
        """감사 로그를 파일에 기록"""
        try:
            log_data = {
                'timestamp': log_entry.timestamp,
                'user_id': log_entry.user_id,
                'action': log_entry.action,
                'resource': log_entry.resource,
                'result': log_entry.result,
                'ip_address': log_entry.ip_address,
                'user_agent': log_entry.user_agent,
                'additional_info': log_entry.additional_info
            }
            
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_data, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"감사 로그 기록 실패: {e}")
    
    def rotate_secrets(self, resource: str) -> Dict[str, Any]:
        """시크릿 로테이션"""
        if not self.check_access_permission(resource, "rotate"):
            return {"success": False, "error": "Access denied"}
        
        policy = self.security_policies.get(resource)
        if not policy:
            return {"success": False, "error": "No policy found"}
        
        try:
            # 실제 로테이션 로직은 리소스 타입에 따라 구현
            if resource == "api_keys":
                return self._rotate_api_keys()
            elif resource == "database_credentials":
                return self._rotate_database_credentials()
            else:
                return {"success": False, "error": "Unsupported resource type"}
                
        except Exception as e:
            logger.error(f"시크릿 로테이션 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def _rotate_api_keys(self) -> Dict[str, Any]:
        """API 키 로테이션 (시뮬레이션)"""
        # 실제로는 각 제공자의 API를 호출하여 새 키 생성
        logger.info("API 키 로테이션 시뮬레이션")
        
        new_keys = {
            "openai": {
                "old_key": "sk-old...",
                "new_key": f"sk-new{secrets.token_hex(16)}",
                "rotated_at": datetime.now().isoformat()
            },
            "anthropic": {
                "old_key": "ant-old...",
                "new_key": f"ant-new{secrets.token_hex(16)}",
                "rotated_at": datetime.now().isoformat()
            }
        }
        
        self._log_access_attempt("api_keys", "rotate", "SUCCESS", "API keys rotated")
        return {"success": True, "rotated_keys": list(new_keys.keys())}
    
    def _rotate_database_credentials(self) -> Dict[str, Any]:
        """데이터베이스 인증 정보 로테이션 (시뮬레이션)"""
        logger.info("데이터베이스 인증 정보 로테이션 시뮬레이션")
        
        new_credentials = {
            "qdrant": {
                "old_password": "old_pass",
                "new_password": secrets.token_urlsafe(32),
                "rotated_at": datetime.now().isoformat()
            },
            "redis": {
                "old_password": "old_redis_pass",
                "new_password": secrets.token_urlsafe(24),
                "rotated_at": datetime.now().isoformat()
            }
        }
        
        self._log_access_attempt("database_credentials", "rotate", "SUCCESS", "Database credentials rotated")
        return {"success": True, "rotated_services": list(new_credentials.keys())}
    
    def get_security_status(self) -> Dict[str, Any]:
        """보안 상태 요약"""
        if not self.check_access_permission("security_status", "read"):
            return {"error": "Access denied"}
        
        # 최근 감사 로그 분석
        recent_logs = [log for log in self.audit_log if 
                      datetime.fromisoformat(log.timestamp) > datetime.now() - timedelta(hours=24)]
        
        failed_attempts = [log for log in recent_logs if log.result == "DENIED"]
        
        # 시크릿 만료 확인
        expiring_secrets = self._check_expiring_secrets()
        
        return {
            "security_level": "HIGH" if len(failed_attempts) == 0 else "MEDIUM",
            "total_policies": len(self.security_policies),
            "recent_access_attempts": len(recent_logs),
            "failed_attempts_24h": len(failed_attempts),
            "encryption_enabled": self.cipher_suite is not None,
            "expiring_secrets": expiring_secrets,
            "current_user": self.current_user,
            "current_role": self.current_role.value,
            "audit_log_size": len(self.audit_log)
        }
    
    def _check_expiring_secrets(self) -> List[Dict[str, Any]]:
        """만료 예정 시크릿 확인"""
        expiring = []
        
        for resource, policy in self.security_policies.items():
            # 실제로는 각 시크릿의 생성/갱신 일자를 확인해야 함
            # 여기서는 시뮬레이션
            days_until_expiry = policy.rotation_days - 10  # 임의의 값
            
            if days_until_expiry <= 30:  # 30일 이내 만료 예정
                expiring.append({
                    "resource": resource,
                    "days_until_expiry": days_until_expiry,
                    "policy_rotation_days": policy.rotation_days
                })
        
        return expiring
    
    def create_secure_backup(self, data: Dict[str, Any], backup_path: str) -> bool:
        """보안 백업 생성"""
        if not self.check_access_permission("backup", "create"):
            return False
        
        try:
            # 데이터 암호화
            encrypted_data = self.encrypt_sensitive_data(data, SecurityLevel.SECRET)
            
            # 백업 파일 생성
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(encrypted_data, f, indent=2, ensure_ascii=False)
            
            # 파일 권한 설정 (소유자만 읽기/쓰기)
            os.chmod(backup_file, 0o600)
            
            # 체크섬 파일 생성
            checksum = self._calculate_file_checksum(backup_file)
            checksum_file = backup_file.with_suffix('.sha256')
            
            with open(checksum_file, 'w') as f:
                f.write(f"{checksum}  {backup_file.name}\n")
            
            self._log_access_attempt("backup", "create", "SUCCESS", f"Backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"보안 백업 생성 실패: {e}")
            self._log_access_attempt("backup", "create", "FAILED", str(e))
            return False
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """파일 체크섬 계산"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def verify_backup_integrity(self, backup_path: str) -> bool:
        """백업 파일 무결성 검증"""
        try:
            backup_file = Path(backup_path)
            checksum_file = backup_file.with_suffix('.sha256')
            
            if not checksum_file.exists():
                logger.error("체크섬 파일이 없습니다")
                return False
            
            # 저장된 체크섬 읽기
            with open(checksum_file, 'r') as f:
                stored_checksum = f.read().split()[0]
            
            # 현재 파일 체크섬 계산
            current_checksum = self._calculate_file_checksum(backup_file)
            
            if stored_checksum == current_checksum:
                logger.info("백업 파일 무결성 검증 성공")
                return True
            else:
                logger.error("백업 파일 무결성 검증 실패 - 파일이 변조되었을 가능성")
                return False
                
        except Exception as e:
            logger.error(f"백업 무결성 검증 오류: {e}")
            return False


# 싱글톤 인스턴스
_secure_config_manager = None

def get_secure_config_manager() -> SecureConfigManager:
    """보안 설정 관리자 싱글톤 인스턴스"""
    global _secure_config_manager
    
    if _secure_config_manager is None:
        _secure_config_manager = SecureConfigManager()
    
    return _secure_config_manager