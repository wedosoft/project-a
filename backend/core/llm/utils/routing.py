"""
라우팅 모듈
"""

import logging
import random
from typing import Dict, Tuple, Any, Optional
from ..models.base import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)


class ProviderRouter:
    """LLM 제공자 라우팅 관리자"""
    
    def __init__(self):
        # 제공자별 가중치 (성능, 비용, 신뢰성 기반)
        self.provider_weights = {
            LLMProvider.GEMINI: 1.0,      # 빠르고 저렴
            LLMProvider.OPENAI: 0.8,      # 안정적이지만 비쌈
            LLMProvider.ANTHROPIC: 0.9,   # 품질 좋지만 느림
        }
        
        # 제공자별 실패 카운트
        self.failure_counts = {
            provider: 0 for provider in LLMProvider
        }
    
    async def select_provider(self, 
                            available_providers: Dict[LLMProvider, Any], 
                            request: LLMRequest) -> Tuple[LLMProvider, Any]:
        """
        최적의 제공자 선택
        
        Args:
            available_providers: 사용 가능한 제공자들
            request: LLM 요청
            
        Returns:
            (선택된 제공자 타입, 제공자 인스턴스)
        """
        if not available_providers:
            raise RuntimeError("사용 가능한 제공자가 없습니다.")
        
        # 건강한 제공자들만 필터링
        healthy_providers = {}
        
        for provider_type, provider_instance in available_providers.items():
            if await self._is_provider_healthy(provider_type, provider_instance):
                healthy_providers[provider_type] = provider_instance
        
        if not healthy_providers:
            # 모든 제공자가 불건전하면 첫 번째를 사용
            logger.warning("모든 제공자가 불건전합니다. 첫 번째 제공자를 사용합니다.")
            provider_type = list(available_providers.keys())[0]
            return provider_type, available_providers[provider_type]
        
        # 가중치 기반 선택
        selected_provider = self._weighted_selection(healthy_providers, request)
        
        logger.debug(f"선택된 제공자: {selected_provider.value}")
        return selected_provider, healthy_providers[selected_provider]
    
    async def _is_provider_healthy(self, provider_type: LLMProvider, provider_instance: Any) -> bool:
        """제공자 건강 상태 확인"""
        # 연속 실패가 5회 이상이면 불건전
        if self.failure_counts[provider_type] >= 5:
            return False
        
        try:
            return await provider_instance.health_check()
        except Exception:
            return False
    
    def _weighted_selection(self, 
                          providers: Dict[LLMProvider, Any], 
                          request: LLMRequest) -> LLMProvider:
        """가중치 기반 제공자 선택"""
        
        # 요청 특성에 따른 가중치 조정
        adjusted_weights = {}
        
        for provider_type in providers.keys():
            base_weight = self.provider_weights.get(provider_type, 1.0)
            
            # 실패 횟수에 따른 가중치 감소
            failure_penalty = max(0.1, 1.0 - (self.failure_counts[provider_type] * 0.1))
            
            # 요청 길이에 따른 조정
            length_factor = self._get_length_factor(provider_type, request)
            
            adjusted_weights[provider_type] = base_weight * failure_penalty * length_factor
        
        # 가중치에 따른 무작위 선택
        total_weight = sum(adjusted_weights.values())
        if total_weight == 0:
            return random.choice(list(providers.keys()))
        
        rand_val = random.uniform(0, total_weight)
        current_weight = 0
        
        for provider_type, weight in adjusted_weights.items():
            current_weight += weight
            if rand_val <= current_weight:
                return provider_type
        
        return list(providers.keys())[0]  # 폴백
    
    def _get_length_factor(self, provider_type: LLMProvider, request: LLMRequest) -> float:
        """요청 길이에 따른 가중치 조정 팩터"""
        
        # 전체 메시지 길이 계산
        total_length = sum(len(msg.get("content", "")) for msg in request.messages)
        
        # 길이별 제공자 선호도
        if total_length < 1000:  # 짧은 요청
            preferences = {
                LLMProvider.GEMINI: 1.2,      # Gemini가 빠름
                LLMProvider.OPENAI: 1.0,
                LLMProvider.ANTHROPIC: 0.9,
            }
        elif total_length < 5000:  # 중간 요청
            preferences = {
                LLMProvider.OPENAI: 1.1,      # OpenAI가 안정적
                LLMProvider.ANTHROPIC: 1.0,
                LLMProvider.GEMINI: 0.9,
            }
        else:  # 긴 요청
            preferences = {
                LLMProvider.ANTHROPIC: 1.2,   # Anthropic이 긴 텍스트에 좋음
                LLMProvider.GEMINI: 1.1,
                LLMProvider.OPENAI: 0.8,
            }
        
        return preferences.get(provider_type, 1.0)
    
    def record_success(self, provider_type: LLMProvider):
        """성공 기록"""
        self.failure_counts[provider_type] = max(0, self.failure_counts[provider_type] - 1)
    
    def record_failure(self, provider_type: LLMProvider):
        """실패 기록"""
        self.failure_counts[provider_type] += 1
        logger.warning(f"{provider_type.value} 실패 카운트: {self.failure_counts[provider_type]}")
    
    def reset_failure_count(self, provider_type: LLMProvider):
        """실패 카운트 리셋"""
        self.failure_counts[provider_type] = 0
