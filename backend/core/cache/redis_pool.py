"""
Redis 연결 풀링 관리자

고성능 Redis 연결 풀을 제공하여 연결 오버헤드를 최소화합니다.
"""

import logging
import os
from typing import Optional, Any, Dict, Union
import aioredis
from aioredis import ConnectionPool
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class RedisPoolManager:
    """
    Redis 연결 풀 관리자 (싱글톤 패턴)
    
    멀티플 Redis 인스턴스와 연결 풀링을 지원합니다.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisPoolManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if RedisPoolManager._initialized:
            return
            
        self.pools: Dict[str, ConnectionPool] = {}
        self.clients: Dict[str, aioredis.Redis] = {}
        self._lock = asyncio.Lock()
        
        # 기본 설정
        self.default_config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'password': os.getenv('REDIS_PASSWORD'),
            'db': int(os.getenv('REDIS_DB', '0')),
            'encoding': 'utf-8',
            'decode_responses': True,
            'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '20')),
            'retry_on_timeout': True,
            'health_check_interval': int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', '30')),
        }
        
        RedisPoolManager._initialized = True
        logger.info("Redis 풀 매니저 초기화 완료")
    
    async def get_pool(self, pool_name: str = 'default', **kwargs) -> ConnectionPool:
        """
        Redis 연결 풀 획득 (lazy initialization)
        
        Args:
            pool_name: 풀 이름
            **kwargs: Redis 연결 설정 오버라이드
            
        Returns:
            ConnectionPool: Redis 연결 풀
        """
        async with self._lock:
            if pool_name not in self.pools:
                # 설정 병합
                config = self.default_config.copy()
                config.update(kwargs)
                
                # 연결 풀 생성
                self.pools[pool_name] = ConnectionPool(
                    host=config['host'],
                    port=config['port'],
                    password=config['password'],
                    db=config['db'],
                    encoding=config['encoding'],
                    decode_responses=config['decode_responses'],
                    max_connections=config['max_connections'],
                    retry_on_timeout=config['retry_on_timeout'],
                    health_check_interval=config['health_check_interval']
                )
                
                logger.info(f"Redis 풀 '{pool_name}' 생성 - {config['host']}:{config['port']}/{config['db']}")
            
            return self.pools[pool_name]
    
    async def get_client(self, pool_name: str = 'default', **kwargs) -> aioredis.Redis:
        """
        Redis 클라이언트 획득
        
        Args:
            pool_name: 풀 이름
            **kwargs: Redis 연결 설정 오버라이드
            
        Returns:
            aioredis.Redis: Redis 클라이언트
        """
        if pool_name not in self.clients:
            pool = await self.get_pool(pool_name, **kwargs)
            self.clients[pool_name] = aioredis.Redis(connection_pool=pool)
            
        return self.clients[pool_name]
    
    @asynccontextmanager
    async def get_connection(self, pool_name: str = 'default', **kwargs):
        """
        Redis 연결 컨텍스트 매니저
        
        Args:
            pool_name: 풀 이름
            **kwargs: Redis 연결 설정 오버라이드
            
        Yields:
            aioredis.Redis: Redis 클라이언트
        """
        client = await self.get_client(pool_name, **kwargs)
        try:
            yield client
        except Exception:
            # 연결 오류 시 재연결 시도
            logger.exception(f"Redis 연결 '{pool_name}' 오류 발생")
            raise
    
    async def health_check(self, pool_name: str = 'default') -> bool:
        """
        Redis 연결 상태 확인
        
        Args:
            pool_name: 풀 이름
            
        Returns:
            bool: 연결 상태 (True: 정상, False: 비정상)
        """
        try:
            async with self.get_connection(pool_name) as redis:
                await redis.ping()
                return True
        except Exception as e:
            logger.error(f"Redis 풀 '{pool_name}' 헬스체크 실패: {e}")
            return False
    
    async def get_pool_info(self, pool_name: str = 'default') -> Dict[str, Any]:
        """
        연결 풀 정보 조회
        
        Args:
            pool_name: 풀 이름
            
        Returns:
            Dict[str, Any]: 풀 정보
        """
        if pool_name not in self.pools:
            return {'status': 'not_initialized'}
        
        pool = self.pools[pool_name]
        return {
            'status': 'active',
            'max_connections': pool.max_connections,
            'created_connections': len(pool._created_connections),
            'available_connections': len(pool._available_connections),
            'in_use_connections': len(pool._in_use_connections)
        }
    
    async def close_pool(self, pool_name: str = 'default'):
        """
        특정 연결 풀 종료
        
        Args:
            pool_name: 풀 이름
        """
        if pool_name in self.clients:
            await self.clients[pool_name].close()
            del self.clients[pool_name]
            
        if pool_name in self.pools:
            await self.pools[pool_name].disconnect()
            del self.pools[pool_name]
            
        logger.info(f"Redis 풀 '{pool_name}' 종료 완료")
    
    async def close_all(self):
        """모든 연결 풀 종료"""
        for pool_name in list(self.pools.keys()):
            await self.close_pool(pool_name)
        
        logger.info("모든 Redis 풀 종료 완료")


class RedisCache:
    """
    Redis 기반 캐시 인터페이스
    
    TTL 지원과 자동 직렬화/역직렬화를 제공합니다.
    """
    
    def __init__(self, pool_name: str = 'default', key_prefix: str = ''):
        self.pool_manager = RedisPoolManager()
        self.pool_name = pool_name
        self.key_prefix = key_prefix
    
    def _make_key(self, key: str) -> str:
        """키에 prefix 적용"""
        if self.key_prefix:
            return f"{self.key_prefix}:{key}"
        return key
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        캐시에서 값 조회
        
        Args:
            key: 캐시 키
            default: 기본값
            
        Returns:
            Any: 캐시된 값 또는 기본값
        """
        try:
            async with self.pool_manager.get_connection(self.pool_name) as redis:
                value = await redis.get(self._make_key(key))
                if value is None:
                    return default
                
                # JSON 역직렬화 시도
                try:
                    import json
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
                    
        except Exception as e:
            logger.error(f"Redis GET 오류 - 키: {key}, 오류: {e}")
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        캐시에 값 저장
        
        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL (초)
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            async with self.pool_manager.get_connection(self.pool_name) as redis:
                # JSON 직렬화 시도
                if not isinstance(value, str):
                    import json
                    value = json.dumps(value, ensure_ascii=False, default=str)
                
                if ttl:
                    await redis.setex(self._make_key(key), ttl, value)
                else:
                    await redis.set(self._make_key(key), value)
                
                return True
                
        except Exception as e:
            logger.error(f"Redis SET 오류 - 키: {key}, 오류: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        캐시에서 키 삭제
        
        Args:
            key: 캐시 키
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            async with self.pool_manager.get_connection(self.pool_name) as redis:
                result = await redis.delete(self._make_key(key))
                return result > 0
                
        except Exception as e:
            logger.error(f"Redis DELETE 오류 - 키: {key}, 오류: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        캐시 키 존재 확인
        
        Args:
            key: 캐시 키
            
        Returns:
            bool: 존재 여부
        """
        try:
            async with self.pool_manager.get_connection(self.pool_name) as redis:
                result = await redis.exists(self._make_key(key))
                return result > 0
                
        except Exception as e:
            logger.error(f"Redis EXISTS 오류 - 키: {key}, 오류: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        패턴에 매칭되는 모든 키 삭제
        
        Args:
            pattern: 키 패턴 (예: "user:*")
            
        Returns:
            int: 삭제된 키 수
        """
        try:
            async with self.pool_manager.get_connection(self.pool_name) as redis:
                keys = await redis.keys(self._make_key(pattern))
                if keys:
                    result = await redis.delete(*keys)
                    return result
                return 0
                
        except Exception as e:
            logger.error(f"Redis CLEAR_PATTERN 오류 - 패턴: {pattern}, 오류: {e}")
            return 0


# 전역 인스턴스
redis_pool_manager = RedisPoolManager()
default_cache = RedisCache()

# 편의 함수들
async def get_redis_client(pool_name: str = 'default') -> aioredis.Redis:
    """Redis 클라이언트 획득"""
    return await redis_pool_manager.get_client(pool_name)

async def get_redis_connection(pool_name: str = 'default'):
    """Redis 연결 컨텍스트 매니저"""
    return redis_pool_manager.get_connection(pool_name)

async def health_check_redis(pool_name: str = 'default') -> bool:
    """Redis 헬스체크"""
    return await redis_pool_manager.health_check(pool_name)