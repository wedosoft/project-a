"""
의존성 컨테이너 - IoC (Inversion of Control) 패턴 구현

모든 의존성을 중앙에서 관리하여 유지보수성과 테스트 용이성을 향상시킵니다.
성능 최적화된 캐싱 전략도 포함됩니다.
"""

import logging
from typing import Dict, Any, Optional
import asyncio

from core.database.vectordb import vector_db
from core.platforms.freshdesk import fetcher
from core.llm.manager import get_llm_manager
from core.search.hybrid import HybridSearchManager
from core.config import get_settings
from core.cache import CacheManager

logger = logging.getLogger(__name__)


class DependencyContainer:
    """
    중앙 의존성 컨테이너 - 싱글톤 패턴
    
    모든 서비스 인스턴스를 관리하고 의존성 주입을 담당합니다.
    성능 최적화된 캐싱 전략을 포함합니다.
    """
    
    _instance: Optional['DependencyContainer'] = None
    _services: Dict[str, Any] = {}
    _initialized: bool = False
    
    def __new__(cls) -> 'DependencyContainer':
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self) -> None:
        """컨테이너 초기화 - 모든 서비스 등록"""
        if self._initialized:
            logger.warning("Container가 이미 초기화되어 있습니다.")
            return
            
        logger.info("🏗️ 의존성 컨테이너 초기화 시작...")
        
        try:
            # 설정 관리자
            settings = get_settings()
            self._services['settings'] = settings
            
            # 벡터 데이터베이스
            self._services['vector_db'] = vector_db
            
            # Freshdesk fetcher
            self._services['fetcher'] = fetcher
            
            # LLM Manager (비동기 초기화)
            logger.info("🧠 LLM Manager 초기화 중...")
            llm_manager = get_llm_manager()
            self._services['llm_manager'] = llm_manager
            logger.info("🧠 LLM Manager 초기화 완료")
            
            # 성능 최적화된 캐싱 매니저 초기화
            logger.info("🚀 성능 최적화된 캐싱 시스템 초기화 중...")
            cache_manager = CacheManager()
            
            # 다양한 캐시 생성
            ticket_context_cache = cache_manager.create_cache(
                name="ticket_context",
                maxsize=1000,
                ttl=3600,  # 1시간
                enable_compression=True,
                enable_stats=True
            )
            
            ticket_summary_cache = cache_manager.create_cache(
                name="ticket_summary", 
                maxsize=500,
                ttl=1800,  # 30분
                enable_compression=True,
                enable_stats=True
            )
            
            # LLM 응답 캐시 (새로 추가)
            llm_response_cache = cache_manager.create_cache(
                name="llm_response",
                maxsize=2000,
                ttl=7200,  # 2시간
                enable_compression=True,
                enable_stats=True
            )
            
            # 벡터 검색 결과 캐시 (새로 추가)
            vector_search_cache = cache_manager.create_cache(
                name="vector_search",
                maxsize=1500,
                ttl=1800,  # 30분
                enable_compression=True,
                enable_stats=True
            )
            
            self._services['cache_manager'] = cache_manager
            self._services['ticket_context_cache'] = ticket_context_cache
            self._services['ticket_summary_cache'] = ticket_summary_cache
            self._services['llm_response_cache'] = llm_response_cache
            self._services['vector_search_cache'] = vector_search_cache
            logger.info("🚀 캐싱 시스템 초기화 완료")
            
            # 하이브리드 검색 매니저
            logger.info("🔍 하이브리드 검색 매니저 초기화 중...")
            hybrid_search_manager = HybridSearchManager(
                vector_db=self._services['vector_db'],
                llm_router=self._services['llm_manager'],
                fetcher=self._services['fetcher']
            )
            self._services['hybrid_search_manager'] = hybrid_search_manager
            logger.info("🔍 하이브리드 검색 매니저 초기화 완료")
            
            self._initialized = True
            logger.info("✅ 의존성 컨테이너 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 의존성 컨테이너 초기화 실패: {e}")
            raise
    
    def get(self, service_name: str) -> Any:
        """서비스 인스턴스 반환"""
        if not self._initialized:
            raise RuntimeError("Container가 초기화되지 않았습니다. initialize()를 먼저 호출해주세요.")
        
        if service_name not in self._services:
            raise ValueError(f"서비스 '{service_name}'이 등록되지 않았습니다.")
        
        return self._services[service_name]
    
    def get_vector_db(self):
        """벡터 데이터베이스 반환"""
        return self.get('vector_db')
    
    def get_fetcher(self):
        """Freshdesk fetcher 반환"""
        return self.get('fetcher')
    
    def get_llm_manager(self):
        """LLM Manager 반환"""
        return self.get('llm_manager')
    
    def get_cache_manager(self):
        """캐시 매니저 반환"""
        return self.get('cache_manager')
    
    def get_ticket_context_cache(self):
        """티켓 컨텍스트 캐시 반환"""
        return self.get('ticket_context_cache')
    
    def get_ticket_summary_cache(self):
        """티켓 요약 캐시 반환"""
        return self.get('ticket_summary_cache')
    
    def get_llm_response_cache(self):
        """LLM 응답 캐시 반환"""
        return self.get('llm_response_cache')
    
    def get_vector_search_cache(self):
        """벡터 검색 결과 캐시 반환"""
        return self.get('vector_search_cache')
    
    def get_hybrid_search_manager(self):
        """하이브리드 검색 매니저 반환"""
        return self.get('hybrid_search_manager')
    
    def get_settings(self):
        """설정 반환"""
        return self.get('settings')
    
    def health_check(self) -> Dict[str, Any]:
        """모든 서비스의 건강 상태 확인"""
        status = {
            'initialized': self._initialized,
            'services': {}
        }
        
        for service_name, service in self._services.items():
            try:
                # 각 서비스의 상태 확인
                if hasattr(service, 'health_check'):
                    # 비동기 함수인지 확인
                    if asyncio.iscoroutinefunction(service.health_check):
                        # 비동기 함수는 건너뛰고 기본 정보만 제공
                        status['services'][service_name] = {
                            'status': 'healthy',
                            'type': type(service).__name__,
                            'note': 'async health_check skipped in sync context'
                        }
                    else:
                        # 동기 함수는 실행
                        status['services'][service_name] = service.health_check()
                elif hasattr(service, '__len__'):  # 캐시류
                    status['services'][service_name] = {
                        'status': 'healthy',
                        'size': len(service) if hasattr(service, '__len__') else 'unknown',
                        'type': type(service).__name__
                    }
                else:
                    status['services'][service_name] = {
                        'status': 'healthy',
                        'type': type(service).__name__
                    }
            except Exception as e:
                status['services'][service_name] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
        
        return status
    
    async def shutdown(self) -> None:
        """컨테이너 종료 및 리소스 정리"""
        logger.info("🛑 의존성 컨테이너 종료 시작...")
        
        for service_name, service in self._services.items():
            try:
                if hasattr(service, 'close'):
                    if asyncio.iscoroutinefunction(service.close):
                        await service.close()
                    else:
                        service.close()
                elif hasattr(service, 'clear_all'):  # CacheManager
                    await service.clear_all()
                elif hasattr(service, 'clear'):
                    if asyncio.iscoroutinefunction(service.clear):
                        await service.clear()
                    else:
                        service.clear()
                logger.debug(f"✅ {service_name} 정리 완료")
            except Exception as e:
                logger.warning(f"⚠️ {service_name} 정리 중 오류: {e}")
        
        self._services.clear()
        self._initialized = False
        logger.info("✅ 의존성 컨테이너 종료 완료")


# 전역 컨테이너 인스턴스
container = DependencyContainer()


async def get_container() -> DependencyContainer:
    """FastAPI 의존성으로 사용할 컨테이너 반환"""
    if not container._initialized:
        await container.initialize()
    return container
