"""
성능 최적화된 캐싱 매니저

다층 캐싱 전략과 성능 최적화 기능을 제공합니다:
- 메모리 캐시 (TTLCache)
- Redis 캐시 (향후 확장)
- 압축 및 직렬화 최적화
- 캐시 히트율 모니터링
"""

import time
import json
import logging
import asyncio
from typing import Any, Optional, Dict, Union, Tuple
from cachetools import TTLCache, LRUCache
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """캐시 통계 정보"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    avg_response_time: float = 0.0
    last_reset: datetime = None


class PerformanceCache:
    """
    성능 최적화된 캐싱 시스템
    
    특징:
    - 다층 캐싱 (L1: 메모리, L2: 향후 Redis)
    - 자동 압축 및 직렬화
    - 성능 모니터링
    - 캐시 워밍업 지원
    """
    
    def __init__(
        self,
        maxsize: int = 1000,
        ttl: int = 3600,
        enable_compression: bool = True,
        enable_stats: bool = True
    ):
        self.maxsize = maxsize
        self.ttl = ttl
        self.enable_compression = enable_compression
        self.enable_stats = enable_stats
        
        # 메모리 캐시 (L1)
        self._l1_cache = TTLCache(maxsize=maxsize, ttl=ttl)
        
        # 통계 추적
        self._stats = CacheStats(last_reset=datetime.now())
        self._response_times: list = []
        
        # 성능 최적화를 위한 설정
        self._serialization_cache = LRUCache(maxsize=100)  # 직렬화 결과 캐시
        
        logger.info(f"🚀 PerformanceCache 초기화: maxsize={maxsize}, ttl={ttl}s")
    
    def _generate_key(self, key: Union[str, Dict, Tuple]) -> str:
        """키 생성 및 정규화"""
        if isinstance(key, str):
            return key
        elif isinstance(key, (dict, tuple, list)):
            # 복잡한 객체는 해시로 변환
            key_str = json.dumps(key, sort_keys=True, default=str)
            return hashlib.md5(key_str.encode()).hexdigest()
        else:
            return str(key)
    
    def _serialize_value(self, value: Any) -> bytes:
        """값 직렬화 (압축 포함)"""
        try:
            # JSON 직렬화
            serialized = json.dumps(value, default=str, ensure_ascii=False)
            data = serialized.encode('utf-8')
            
            # 압축 (큰 데이터만)
            if self.enable_compression and len(data) > 1024:  # 1KB 이상만 압축
                import gzip
                data = gzip.compress(data)
                return b'GZIP:' + data
            
            return b'RAW:' + data
            
        except Exception as e:
            logger.warning(f"직렬화 실패: {e}")
            return b'RAW:' + str(value).encode('utf-8')
    
    def _deserialize_value(self, data: bytes) -> Any:
        """값 역직렬화 (압축 해제 포함)"""
        try:
            if data.startswith(b'GZIP:'):
                import gzip
                data = gzip.decompress(data[5:])
            elif data.startswith(b'RAW:'):
                data = data[4:]
            
            # JSON 역직렬화
            return json.loads(data.decode('utf-8'))
            
        except Exception as e:
            logger.warning(f"역직렬화 실패: {e}")
            return None
    
    def __contains__(self, key: Union[str, Dict, Tuple]) -> bool:
        """'in' 연산자 지원을 위한 메서드"""
        try:
            normalized_key = self._generate_key(key)
            return normalized_key in self._l1_cache
        except Exception as e:
            logger.warning(f"캐시 포함 확인 오류: {e}")
            return False
    
    def __getitem__(self, key: Union[str, Dict, Tuple]) -> Any:
        """딕셔너리 스타일 접근을 위한 메서드 (동기 버전)"""
        try:
            normalized_key = self._generate_key(key)
            if normalized_key in self._l1_cache:
                serialized_value = self._l1_cache[normalized_key]
                return self._deserialize_value(serialized_value)
            raise KeyError(f"Key not found: {key}")
        except Exception as e:
            logger.warning(f"캐시 접근 오류: {e}")
            raise KeyError(f"Key not found: {key}")
    
    def __setitem__(self, key: Union[str, Dict, Tuple], value: Any) -> None:
        """딕셔너리 스타일 설정을 위한 메서드 (동기 버전)"""
        try:
            normalized_key = self._generate_key(key)
            serialized_value = self._serialize_value(value)
            self._l1_cache[normalized_key] = serialized_value
            logger.debug(f"💾 캐시 저장 (동기): {normalized_key[:32]}...")
        except Exception as e:
            logger.warning(f"캐시 저장 오류 (동기): {e}")

    async def get(self, key: Union[str, Dict, Tuple]) -> Optional[Any]:
        """캐시에서 값 조회"""
        start_time = time.time()
        normalized_key = self._generate_key(key)
        
        try:
            # L1 캐시에서 조회
            if normalized_key in self._l1_cache:
                serialized_value = self._l1_cache[normalized_key]
                value = self._deserialize_value(serialized_value)
                
                if self.enable_stats:
                    self._stats.hits += 1
                    self._stats.total_requests += 1
                    self._update_response_time(time.time() - start_time)
                
                logger.debug(f"🎯 캐시 히트: {normalized_key[:32]}...")
                return value
            
            # 캐시 미스
            if self.enable_stats:
                self._stats.misses += 1
                self._stats.total_requests += 1
                self._update_response_time(time.time() - start_time)
            
            logger.debug(f"❌ 캐시 미스: {normalized_key[:32]}...")
            return None
            
        except Exception as e:
            logger.warning(f"캐시 조회 오류: {e}")
            return None
    
    async def set(
        self, 
        key: Union[str, Dict, Tuple], 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """캐시에 값 저장"""
        try:
            normalized_key = self._generate_key(key)
            serialized_value = self._serialize_value(value)
            
            # TTL 설정
            cache_ttl = ttl or self.ttl
            
            # L1 캐시에 저장
            if cache_ttl > 0:
                self._l1_cache[normalized_key] = serialized_value
            else:
                # TTL이 0이면 LRU 캐시 사용
                if not hasattr(self, '_lru_cache'):
                    self._lru_cache = LRUCache(maxsize=self.maxsize)
                self._lru_cache[normalized_key] = serialized_value
            
            logger.debug(f"💾 캐시 저장: {normalized_key[:32]}... (TTL: {cache_ttl}s)")
            return True
            
        except Exception as e:
            logger.warning(f"캐시 저장 오류: {e}")
            return False
    
    async def delete(self, key: Union[str, Dict, Tuple]) -> bool:
        """캐시에서 값 삭제"""
        try:
            normalized_key = self._generate_key(key)
            
            if normalized_key in self._l1_cache:
                del self._l1_cache[normalized_key]
                logger.debug(f"🗑️ 캐시 삭제: {normalized_key[:32]}...")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"캐시 삭제 오류: {e}")
            return False
    
    async def clear(self) -> None:
        """모든 캐시 삭제"""
        try:
            self._l1_cache.clear()
            if hasattr(self, '_lru_cache'):
                self._lru_cache.clear()
            
            # 통계 초기화
            if self.enable_stats:
                self._stats = CacheStats(last_reset=datetime.now())
                self._response_times.clear()
            
            logger.info("🧹 캐시 전체 삭제 완료")
            
        except Exception as e:
            logger.warning(f"캐시 삭제 오류: {e}")
    
    def _update_response_time(self, response_time: float) -> None:
        """응답 시간 통계 업데이트"""
        self._response_times.append(response_time)
        
        # 최근 100개 응답 시간만 유지
        if len(self._response_times) > 100:
            self._response_times = self._response_times[-100:]
        
        # 평균 응답 시간 계산
        if self._response_times:
            self._stats.avg_response_time = sum(self._response_times) / len(self._response_times)
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        if not self.enable_stats:
            return {"stats_enabled": False}
        
        # 히트율 계산
        if self._stats.total_requests > 0:
            self._stats.hit_rate = (self._stats.hits / self._stats.total_requests) * 100
        
        return {
            "stats": asdict(self._stats),
            "cache_info": {
                "l1_size": len(self._l1_cache),
                "l1_maxsize": self._l1_cache.maxsize,
                "l1_ttl": self.ttl,
                "compression_enabled": self.enable_compression
            },
            "performance": {
                "avg_response_time_ms": round(self._stats.avg_response_time * 1000, 2),
                "recent_response_times": len(self._response_times)
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """캐시 건강 상태 확인"""
        try:
            # 간단한 읽기/쓰기 테스트 (동기 버전)
            test_key = "health_check_test"
            test_value = {"timestamp": time.time()}
            
            # 직접 L1 캐시에 테스트
            try:
                serialized_value = self._serialize_value(test_value)
                self._l1_cache[test_key] = serialized_value
                
                # 읽기 테스트
                if test_key in self._l1_cache:
                    retrieved_value = self._deserialize_value(self._l1_cache[test_key])
                    is_healthy = retrieved_value is not None
                    
                    # 정리
                    del self._l1_cache[test_key]
                else:
                    is_healthy = False
                    
            except Exception as e:
                logger.warning(f"캐시 헬스 체크 테스트 실패: {e}")
                is_healthy = False
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "cache_size": len(self._l1_cache),
                "maxsize": self.maxsize,
                "ttl": self.ttl,
                "stats": self.get_stats() if self.enable_stats else None
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


class CacheManager:
    """
    다중 캐시 매니저
    
    여러 종류의 캐시를 중앙에서 관리합니다.
    """
    
    def __init__(self):
        self._caches: Dict[str, PerformanceCache] = {}
        logger.info("🏗️ CacheManager 초기화")
    
    def create_cache(
        self,
        name: str,
        maxsize: int = 1000,
        ttl: int = 3600,
        enable_compression: bool = True,
        enable_stats: bool = True
    ) -> PerformanceCache:
        """새로운 캐시 생성"""
        if name in self._caches:
            logger.warning(f"캐시 '{name}'이 이미 존재합니다. 기존 캐시를 반환합니다.")
            return self._caches[name]
        
        cache = PerformanceCache(
            maxsize=maxsize,
            ttl=ttl,
            enable_compression=enable_compression,
            enable_stats=enable_stats
        )
        
        self._caches[name] = cache
        logger.info(f"📦 캐시 '{name}' 생성 완료")
        return cache
    
    def get_cache(self, name: str) -> Optional[PerformanceCache]:
        """캐시 반환"""
        return self._caches.get(name)
    
    async def clear_all(self) -> None:
        """모든 캐시 삭제"""
        for name, cache in self._caches.items():
            await cache.clear()
            logger.info(f"🧹 캐시 '{name}' 삭제 완료")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """모든 캐시 통계 반환"""
        stats = {}
        for name, cache in self._caches.items():
            stats[name] = cache.get_stats()
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """모든 캐시 건강 상태 확인"""
        health = {}
        for name, cache in self._caches.items():
            health[name] = cache.health_check()
        
        # 전체 상태 판단
        all_healthy = all(
            cache_health.get("status") == "healthy" 
            for cache_health in health.values()
        )
        
        return {
            "overall_status": "healthy" if all_healthy else "unhealthy",
            "caches": health,
            "total_caches": len(self._caches)
        }
