"""
확장 가능한 API 키 관리 시스템

고객 증가에 대비한 다중 API 키 관리 및 부하 분산
"""

import os
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class APIKeyStrategy(Enum):
    """API 키 할당 전략"""
    ROUND_ROBIN = "round_robin"          # 순차 할당
    LOAD_BASED = "load_based"           # 부하 기반
    CUSTOMER_DEDICATED = "customer_dedicated"  # 고객 전용
    HYBRID = "hybrid"                   # 하이브리드


@dataclass
class APIKeyInfo:
    """API 키 정보"""
    key: str
    provider: str
    tier: str = "standard"              # standard, premium, enterprise
    max_rpm: int = 3500                 # 분당 최대 요청
    max_tpm: int = 200000              # 분당 최대 토큰
    daily_budget: float = 100.0        # 일일 예산 (USD)
    current_rpm: int = 0               # 현재 분당 요청
    current_tpm: int = 0               # 현재 분당 토큰
    daily_cost: float = 0.0            # 일일 사용 비용
    last_reset: float = field(default_factory=time.time)
    is_active: bool = True
    assigned_customers: List[str] = field(default_factory=list)
    
    @property
    def available_rpm(self) -> int:
        """사용 가능한 분당 요청"""
        return max(0, self.max_rpm - self.current_rpm)
    
    @property
    def available_tpm(self) -> int:
        """사용 가능한 분당 토큰"""
        return max(0, self.max_tpm - self.current_tpm)
    
    @property
    def remaining_budget(self) -> float:
        """남은 일일 예산"""
        return max(0.0, self.daily_budget - self.daily_cost)
    
    def can_handle_request(self, estimated_tokens: int = 1000) -> bool:
        """요청 처리 가능 여부"""
        return (
            self.is_active and
            self.available_rpm > 0 and
            self.available_tpm >= estimated_tokens and
            self.remaining_budget > 0.01  # 최소 예산
        )


class ScalableAPIKeyManager:
    """확장 가능한 API 키 관리자"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.keys: Dict[str, List[APIKeyInfo]] = defaultdict(list)
        self.strategy = APIKeyStrategy.HYBRID
        self.customer_assignments: Dict[str, Dict[str, str]] = {}
        
        # 키 사용량 추적
        self.usage_tracker = defaultdict(lambda: defaultdict(int))
        self.last_minute_reset = time.time()
        
        # 설정 로드
        self._load_configuration(config_path)
        self._initialize_keys()
        
        logger.info(f"ScalableAPIKeyManager 초기화 완료")
        logger.info(f"로드된 키: {[(provider, len(keys)) for provider, keys in self.keys.items()]}")
    
    def _load_configuration(self, config_path: Optional[str]):
        """설정 파일 로드"""
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.strategy = APIKeyStrategy(config.get('strategy', 'hybrid'))
                    self.customer_assignments = config.get('customer_assignments', {})
                logger.info(f"설정 로드 완료: {config_path}")
            except Exception as e:
                logger.warning(f"설정 로드 실패, 기본값 사용: {e}")
    
    def _initialize_keys(self):
        """환경변수에서 API 키들 초기화"""
        
        # OpenAI 키들
        openai_keys = []
        for i in range(1, 11):  # 최대 10개 키 지원
            key = os.getenv(f'OPENAI_API_KEY_{i}') or (os.getenv('OPENAI_API_KEY') if i == 1 else None)
            if key:
                openai_keys.append(APIKeyInfo(
                    key=key,
                    provider="openai",
                    tier=os.getenv(f'OPENAI_TIER_{i}', 'standard'),
                    max_rpm=int(os.getenv(f'OPENAI_MAX_RPM_{i}', '3500')),
                    max_tpm=int(os.getenv(f'OPENAI_MAX_TPM_{i}', '200000')),
                    daily_budget=float(os.getenv(f'OPENAI_DAILY_BUDGET_{i}', '100.0'))
                ))
        
        if openai_keys:
            self.keys["openai"] = openai_keys
            logger.info(f"OpenAI 키 {len(openai_keys)}개 로드")
        
        # Anthropic 키들
        anthropic_keys = []
        for i in range(1, 11):
            key = os.getenv(f'ANTHROPIC_API_KEY_{i}') or (os.getenv('ANTHROPIC_API_KEY') if i == 1 else None)
            if key:
                anthropic_keys.append(APIKeyInfo(
                    key=key,
                    provider="anthropic",
                    tier=os.getenv(f'ANTHROPIC_TIER_{i}', 'standard'),
                    max_rpm=int(os.getenv(f'ANTHROPIC_MAX_RPM_{i}', '5000')),
                    max_tpm=int(os.getenv(f'ANTHROPIC_MAX_TPM_{i}', '300000')),
                    daily_budget=float(os.getenv(f'ANTHROPIC_DAILY_BUDGET_{i}', '150.0'))
                ))
        
        if anthropic_keys:
            self.keys["anthropic"] = anthropic_keys
            logger.info(f"Anthropic 키 {len(anthropic_keys)}개 로드")
        
        # Google 키들
        google_keys = []
        for i in range(1, 11):
            key = os.getenv(f'GOOGLE_API_KEY_{i}') or (os.getenv('GOOGLE_API_KEY') if i == 1 else None)
            if key:
                google_keys.append(APIKeyInfo(
                    key=key,
                    provider="google",
                    tier=os.getenv(f'GOOGLE_TIER_{i}', 'standard'),
                    max_rpm=int(os.getenv(f'GOOGLE_MAX_RPM_{i}', '60')),
                    max_tpm=int(os.getenv(f'GOOGLE_MAX_TPM_{i}', '60000')),
                    daily_budget=float(os.getenv(f'GOOGLE_DAILY_BUDGET_{i}', '50.0'))
                ))
        
        if google_keys:
            self.keys["google"] = google_keys
            logger.info(f"Google 키 {len(google_keys)}개 로드")
    
    async def get_api_key(
        self, 
        provider: str, 
        customer_id: Optional[str] = None,
        estimated_tokens: int = 1000,
        priority: str = "normal"
    ) -> Tuple[Optional[str], Optional[APIKeyInfo]]:
        """
        최적의 API 키 선택
        
        Args:
            provider: LLM 제공자
            customer_id: 고객 ID
            estimated_tokens: 예상 토큰 수
            priority: 우선순위 (normal, high, enterprise)
        
        Returns:
            (api_key, key_info) 튜플
        """
        
        # 분당 사용량 리셋
        await self._reset_minute_counters()
        
        # 제공자별 키 목록
        provider_keys = self.keys.get(provider.lower(), [])
        if not provider_keys:
            logger.warning(f"{provider} 제공자의 API 키가 없습니다")
            return None, None
        
        # 전략별 키 선택
        if self.strategy == APIKeyStrategy.CUSTOMER_DEDICATED and customer_id:
            selected_key = self._get_dedicated_key(provider, customer_id, provider_keys)
        elif self.strategy == APIKeyStrategy.LOAD_BASED:
            selected_key = self._get_load_based_key(provider_keys, estimated_tokens)
        elif self.strategy == APIKeyStrategy.ROUND_ROBIN:
            selected_key = self._get_round_robin_key(provider_keys, estimated_tokens)
        else:  # HYBRID
            selected_key = self._get_hybrid_key(provider, customer_id, provider_keys, estimated_tokens, priority)
        
        if selected_key:
            # 사용량 업데이트
            selected_key.current_rpm += 1
            selected_key.current_tpm += estimated_tokens
            
            logger.debug(f"{provider} 키 선택: {selected_key.key[:8]}... (RPM: {selected_key.current_rpm}/{selected_key.max_rpm})")
            return selected_key.key, selected_key
        
        logger.warning(f"{provider} 제공자의 사용 가능한 키가 없습니다")
        return None, None
    
    def _get_dedicated_key(
        self, 
        provider: str, 
        customer_id: str, 
        keys: List[APIKeyInfo]
    ) -> Optional[APIKeyInfo]:
        """고객 전용 키 선택"""
        
        # 이미 할당된 키가 있는지 확인
        if customer_id in self.customer_assignments:
            assigned_key_id = self.customer_assignments[customer_id].get(provider)
            if assigned_key_id:
                for key in keys:
                    if key.key.endswith(assigned_key_id[-8:]) and key.can_handle_request():
                        return key
        
        # 새로운 키 할당 (enterprise tier 우선)
        enterprise_keys = [k for k in keys if k.tier == "enterprise" and k.can_handle_request()]
        if enterprise_keys:
            selected = min(enterprise_keys, key=lambda k: len(k.assigned_customers))
            selected.assigned_customers.append(customer_id)
            
            # 할당 정보 저장
            if customer_id not in self.customer_assignments:
                self.customer_assignments[customer_id] = {}
            self.customer_assignments[customer_id][provider] = selected.key
            
            return selected
        
        # enterprise 키가 없으면 일반 키에서 선택
        return self._get_load_based_key(keys, 1000)
    
    def _get_load_based_key(
        self, 
        keys: List[APIKeyInfo], 
        estimated_tokens: int
    ) -> Optional[APIKeyInfo]:
        """부하 기반 키 선택"""
        
        available_keys = [k for k in keys if k.can_handle_request(estimated_tokens)]
        if not available_keys:
            return None
        
        # 사용률이 가장 낮은 키 선택
        def usage_ratio(key: APIKeyInfo) -> float:
            rpm_ratio = key.current_rpm / key.max_rpm
            tpm_ratio = key.current_tpm / key.max_tpm
            budget_ratio = key.daily_cost / key.daily_budget
            return (rpm_ratio + tpm_ratio + budget_ratio) / 3
        
        return min(available_keys, key=usage_ratio)
    
    def _get_round_robin_key(
        self, 
        keys: List[APIKeyInfo], 
        estimated_tokens: int
    ) -> Optional[APIKeyInfo]:
        """라운드 로빈 키 선택"""
        
        available_keys = [k for k in keys if k.can_handle_request(estimated_tokens)]
        if not available_keys:
            return None
        
        # 순차 선택 (간단한 구현)
        current_time = int(time.time())
        index = current_time % len(available_keys)
        return available_keys[index]
    
    def _get_hybrid_key(
        self, 
        provider: str, 
        customer_id: Optional[str], 
        keys: List[APIKeyInfo], 
        estimated_tokens: int,
        priority: str
    ) -> Optional[APIKeyInfo]:
        """하이브리드 키 선택"""
        
        # 우선순위가 높은 요청은 premium tier 우선
        if priority in ["high", "enterprise"]:
            premium_keys = [k for k in keys if k.tier in ["premium", "enterprise"] and k.can_handle_request(estimated_tokens)]
            if premium_keys:
                return self._get_load_based_key(premium_keys, estimated_tokens)
        
        # 고객이 enterprise tier인 경우 전용 키 시도
        if customer_id and priority == "enterprise":
            dedicated = self._get_dedicated_key(provider, customer_id, keys)
            if dedicated:
                return dedicated
        
        # 일반적인 경우 부하 기반 선택
        return self._get_load_based_key(keys, estimated_tokens)
    
    async def _reset_minute_counters(self):
        """분당 카운터 리셋"""
        current_time = time.time()
        if current_time - self.last_minute_reset >= 60:
            for provider_keys in self.keys.values():
                for key in provider_keys:
                    key.current_rpm = 0
                    key.current_tpm = 0
            self.last_minute_reset = current_time
    
    def record_cost(self, api_key: str, cost: float):
        """비용 기록"""
        for provider_keys in self.keys.values():
            for key in provider_keys:
                if key.key == api_key:
                    key.daily_cost += cost
                    break
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """사용량 통계 반환"""
        stats = {}
        for provider, keys in self.keys.items():
            provider_stats = {
                "total_keys": len(keys),
                "active_keys": len([k for k in keys if k.is_active]),
                "total_rpm": sum(k.current_rpm for k in keys),
                "total_tpm": sum(k.current_tpm for k in keys),
                "total_daily_cost": sum(k.daily_cost for k in keys),
                "keys": [
                    {
                        "key_id": key.key[-8:],
                        "tier": key.tier,
                        "rpm_usage": f"{key.current_rpm}/{key.max_rpm}",
                        "tpm_usage": f"{key.current_tpm}/{key.max_tpm}",
                        "daily_cost": f"${key.daily_cost:.2f}/${key.daily_budget:.2f}",
                        "assigned_customers": len(key.assigned_customers)
                    }
                    for key in keys
                ]
            }
            stats[provider] = provider_stats
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """시스템 상태 확인"""
        health = {
            "status": "healthy",
            "issues": [],
            "recommendations": []
        }
        
        for provider, keys in self.keys.items():
            active_keys = [k for k in keys if k.is_active and k.can_handle_request()]
            
            if not active_keys:
                health["status"] = "warning"
                health["issues"].append(f"{provider}: 사용 가능한 키가 없음")
                health["recommendations"].append(f"{provider}: 추가 키 필요 또는 제한 완화")
            
            # 예산 부족 경고
            budget_low_keys = [k for k in keys if k.remaining_budget < 10.0]
            if budget_low_keys:
                health["status"] = "warning"
                health["issues"].append(f"{provider}: {len(budget_low_keys)}개 키의 예산 부족")
                health["recommendations"].append(f"{provider}: 예산 증액 또는 키 추가")
        
        return health


# 글로벌 인스턴스
scalable_key_manager = ScalableAPIKeyManager()
