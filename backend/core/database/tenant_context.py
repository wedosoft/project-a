"""
멀티테넌트 컨텍스트 관리자
요청별로 테넌트 컨텍스트를 설정하고 해당 테넌트의 설정을 제공
"""

import logging
from typing import Dict, Any, Optional
from functools import wraps
from contextlib import contextmanager
import threading

from .tenant_config import TenantConfigManager, get_tenant_config_manager

logger = logging.getLogger(__name__)

# 스레드 로컬 스토리지 (요청별 테넌트 컨텍스트)
_thread_local = threading.local()

class TenantContext:
    """테넌트 컨텍스트 관리 클래스"""
    
    def __init__(self, tenant_id: int, platform: str = "freshdesk"):
        self.tenant_id = tenant_id
        self.platform = platform
        self._config_manager = None
        self._config_cache = {}
    
    @property
    def config_manager(self) -> TenantConfigManager:
        """지연 로딩으로 설정 관리자 인스턴스 반환"""
        if self._config_manager is None:
            self._config_manager = get_tenant_config_manager(str(self.tenant_id), self.platform)
        return self._config_manager
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """테넌트 설정 조회 (캐시 지원)"""
        if key not in self._config_cache:
            self._config_cache[key] = self.config_manager.get_tenant_setting(
                self.tenant_id, key, default
            )
        return self._config_cache[key]
    
    def get_platform_config(self, platform: str = None) -> Dict[str, Any]:
        """플랫폼 설정 조회 (캐시 지원)"""
        platform = platform or self.platform
        cache_key = f"platform_config_{platform}"
        
        if cache_key not in self._config_cache:
            self._config_cache[cache_key] = self.config_manager.get_platform_config(
                self.tenant_id, platform
            )
        return self._config_cache[cache_key]
    
    def get_freshdesk_config(self) -> Dict[str, Any]:
        """Freshdesk 설정 조회 (편의 메서드)"""
        cache_key = "freshdesk_config"
        
        if cache_key not in self._config_cache:
            self._config_cache[cache_key] = self.config_manager.get_freshdesk_config(
                self.tenant_id
            )
        return self._config_cache[cache_key]
    
    def clear_cache(self):
        """설정 캐시 클리어"""
        self._config_cache.clear()
    
    def __repr__(self):
        return f"TenantContext(tenant_id={self.tenant_id}, platform='{self.platform}')"


# =====================================================
# 테넌트 컨텍스트 관리 함수들
# =====================================================

def set_current_tenant(tenant_id: int, platform: str = "freshdesk") -> TenantContext:
    """현재 요청의 테넌트 컨텍스트 설정"""
    context = TenantContext(tenant_id, platform)
    _thread_local.tenant_context = context
    logger.debug(f"테넌트 컨텍스트 설정: {context}")
    return context

def get_current_tenant() -> Optional[TenantContext]:
    """현재 요청의 테넌트 컨텍스트 반환"""
    return getattr(_thread_local, 'tenant_context', None)

def clear_current_tenant():
    """현재 요청의 테넌트 컨텍스트 클리어"""
    if hasattr(_thread_local, 'tenant_context'):
        delattr(_thread_local, 'tenant_context')

@contextmanager
def tenant_context(tenant_id: int, platform: str = "freshdesk"):
    """테넌트 컨텍스트 관리 컨텍스트 매니저
    
    Usage:
        with tenant_context(tenant_id=1, platform="freshdesk"):
            config = get_current_tenant().get_freshdesk_config()
    """
    old_context = get_current_tenant()
    try:
        set_current_tenant(tenant_id, platform)
        yield get_current_tenant()
    finally:
        if old_context:
            _thread_local.tenant_context = old_context
        else:
            clear_current_tenant()

# =====================================================
# 데코레이터들
# =====================================================

def require_tenant_context(func):
    """테넌트 컨텍스트가 필요한 함수에 사용하는 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        current_tenant = get_current_tenant()
        if current_tenant is None:
            raise ValueError(
                f"함수 '{func.__name__}'는 테넌트 컨텍스트가 필요합니다. "
                "set_current_tenant() 또는 tenant_context()를 사용하세요."
            )
        return func(*args, **kwargs)
    return wrapper

def with_tenant_context(tenant_id_param: str = 'tenant_id', 
                       platform_param: str = 'platform'):
    """함수 매개변수에서 테넌트 정보를 추출하여 컨텍스트를 설정하는 데코레이터
    
    Args:
        tenant_id_param: tenant_id가 들어있는 매개변수명
        platform_param: platform이 들어있는 매개변수명
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 매개변수에서 테넌트 정보 추출
            tenant_id = kwargs.get(tenant_id_param)
            platform = kwargs.get(platform_param, "freshdesk")
            
            if tenant_id is None:
                # 위치 인수에서 찾기 (함수 시그니처 분석 필요)
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                if tenant_id_param in param_names:
                    param_index = param_names.index(tenant_id_param)
                    if param_index < len(args):
                        tenant_id = args[param_index]
            
            if tenant_id is None:
                raise ValueError(f"매개변수 '{tenant_id_param}'에서 tenant_id를 찾을 수 없습니다.")
            
            # 테넌트 컨텍스트 설정하고 함수 실행
            with tenant_context(int(tenant_id), platform):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

# =====================================================
# 편의 함수들
# =====================================================

@require_tenant_context
def get_current_setting(key: str, default: Any = None) -> Any:
    """현재 테넌트의 설정 값 반환"""
    return get_current_tenant().get_setting(key, default)

@require_tenant_context
def get_current_platform_config(platform: str = None) -> Dict[str, Any]:
    """현재 테넌트의 플랫폼 설정 반환"""
    return get_current_tenant().get_platform_config(platform)

@require_tenant_context
def get_current_freshdesk_config() -> Dict[str, Any]:
    """현재 테넌트의 Freshdesk 설정 반환"""
    return get_current_tenant().get_freshdesk_config()

def create_freshdesk_client():
    """현재 테넌트 설정으로 Freshdesk 클라이언트 생성"""
    config = get_current_freshdesk_config()
    
    if not config.get('domain') or not config.get('api_key'):
        raise ValueError("Freshdesk 설정이 완전하지 않습니다. domain과 api_key가 필요합니다.")
    
    # 실제 Freshdesk 클라이언트 생성 (여기서는 설정만 반환)
    return {
        'base_url': f"https://{config['domain']}/api/v2",
        'api_key': config['api_key'],
        'headers': {
            'Authorization': f"Basic {config['api_key']}",
            'Content-Type': 'application/json'
        },
        'timeout': config.get('timeout', 30),
        'rate_limit': config.get('rate_limit', 100)
    }

# =====================================================
# FastAPI 미들웨어 지원
# =====================================================

def extract_tenant_from_request(request) -> tuple[int, str]:
    """HTTP 요청에서 테넌트 정보 추출
    
    다양한 방법으로 테넌트 정보를 추출할 수 있습니다:
    1. 헤더: X-Tenant-ID, X-Platform
    2. 쿼리 파라미터: tenant_id, platform
    3. 서브도메인: {tenant}.yourdomain.com
    4. JWT 토큰에서 추출
    """
    
    # 1. 헤더에서 추출
    tenant_id = request.headers.get('X-Tenant-ID') or request.headers.get('X-Tenant-ID')
    platform = request.headers.get('X-Platform', 'freshdesk')
    
    if tenant_id:
        return int(tenant_id), platform
    
    # 2. 쿼리 파라미터에서 추출
    tenant_id = request.query_params.get('tenant_id') or request.query_params.get('tenant_id')
    platform = request.query_params.get('platform', 'freshdesk')
    
    if tenant_id:
        return int(tenant_id), platform
    
    # 3. 서브도메인에서 추출 (예: acme.yourdomain.com -> tenant_id는 DB에서 조회)
    host = request.headers.get('host', '')
    if '.' in host:
        subdomain = host.split('.')[0]
        # 실제로는 DB에서 subdomain -> tenant_id 매핑을 조회해야 함
        # 여기서는 예시로 하드코딩
        subdomain_mapping = {
            'wedosoft': 1,
            'acme': 2,
            'startup': 3
        }
        if subdomain in subdomain_mapping:
            return subdomain_mapping[subdomain], platform
    
    raise ValueError("요청에서 테넌트 정보를 찾을 수 없습니다.")

async def tenant_middleware(request, call_next):
    """FastAPI 미들웨어: 요청별로 테넌트 컨텍스트 자동 설정"""
    try:
        tenant_id, platform = extract_tenant_from_request(request)
        
        with tenant_context(tenant_id, platform):
            response = await call_next(request)
            return response
            
    except ValueError as e:
        # 테넌트 정보가 없는 경우 (공개 엔드포인트 등)
        logger.debug(f"테넌트 컨텍스트 없이 요청 처리: {e}")
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"테넌트 미들웨어 오류: {e}")
        # 오류가 있어도 요청은 계속 처리
        response = await call_next(request)
        return response
