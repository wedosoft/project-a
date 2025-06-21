"""
LLM 라우터 모듈 - 제공자 선택 및 라우팅 로직

이 모듈은 다음 기능을 제공합니다:
- 가중치 기반 LLM 제공자 선택
- 건강 상태 기반 폴백 로직
- 티켓 요약 생성
- 벡터 검색 최적화
"""

import os
import time
import re
from typing import Dict, List, Any, Optional, AsyncGenerator
from pydantic import BaseModel
import logging

from .clients import (
    LLMProvider, AnthropicProvider, OpenAIProvider, GeminiProvider
)
from .models import LLMResponse, LLMProviderStats
from .utils import VectorSearchOptimizer

logger = logging.getLogger(__name__)


class LLMProviderWeights(BaseModel):
    """LLM 제공자별 가중치 및 우선순위 관리"""
    provider_name: str
    base_weight: float = 1.0  # 기본 가중치 (1.0 = 100%)
    performance_multiplier: float = 1.0  # 성능 기반 배수
    cost_efficiency: float = 1.0  # 비용 효율성 점수
    latency_threshold_ms: float = 5000.0  # 지연 시간 임계값
    max_consecutive_failures: int = 5  # 최대 연속 실패 허용 횟수
    
    def calculate_dynamic_weight(self, stats: LLMProviderStats) -> float:
        """
        제공자의 통계 데이터를 기반으로 동적 가중치를 계산합니다.
        
        Args:
            stats: 제공자의 통계 데이터
            
        Returns:
            계산된 동적 가중치 (0.0 ~ 1.0)
        """
        if not stats or stats.total_requests == 0:
            return self.base_weight
            
        # 성공률 기반 가중치 (0.0 ~ 1.0)
        success_weight = stats.success_rate
        
        # 지연 시간 기반 가중치 계산
        avg_latency = stats.average_latency_ms
        if avg_latency <= self.latency_threshold_ms:
            latency_weight = 1.0
        else:
            # 임계값 초과 시 점진적으로 가중치 감소
            latency_weight = max(0.1, self.latency_threshold_ms / avg_latency)
        
        # 연속 실패 패널티 적용
        failure_penalty = 1.0
        if stats.consecutive_failures > 0:
            # 연속 실패가 늘어날수록 지수적으로 가중치 감소
            penalty_ratio = (
                stats.consecutive_failures / self.max_consecutive_failures
            )
            failure_penalty = max(0.1, 1.0 - penalty_ratio)
        
        # 최종 가중치 계산 (모든 요소의 가중 평균)
        dynamic_weight = (
            self.base_weight *
            success_weight *
            latency_weight *
            failure_penalty *
            self.performance_multiplier
        )
        
        return max(0.0, min(1.0, dynamic_weight))
    
    def should_exclude_provider(self, stats: LLMProviderStats) -> bool:
        """
        제공자를 일시적으로 제외해야 하는지 판단합니다.
        
        Args:
            stats: 제공자의 통계 데이터
            
        Returns:
            True면 제외, False면 포함
        """
        if not stats:
            return False
            
        # 연속 실패 횟수가 임계값을 초과하면 제외
        if stats.consecutive_failures >= self.max_consecutive_failures:
            return True
            
        # 최근 성공률이 매우 낮으면 제외 (최소 10회 요청 이후부터 적용)
        if stats.total_requests >= 10 and stats.success_rate < 0.3:
            return True
            
        return False


class LLMProviderSelector:
    """LLM 제공자 선택 로직을 관리하는 클래스"""
    
    def __init__(self):
        # 기본 제공자별 가중치 설정 (성능 우선순위)
        self.provider_weights = {
            "openai": LLMProviderWeights(
                provider_name="openai",
                base_weight=1.0,  # 최우선 (속도가 빠름)
                performance_multiplier=1.2,  # 성능 향상
                cost_efficiency=1.0,  # 비용 효율성 기준
                latency_threshold_ms=5000.0,  # 5초 (더 엄격한 기준)
                max_consecutive_failures=3
            ),
            "anthropic": LLMProviderWeights(
                provider_name="anthropic",
                base_weight=0.8,  # 두 번째 우선순위 (품질은 좋지만 느림)
                performance_multiplier=1.0,
                cost_efficiency=0.9,  # Claude는 조금 더 비싸지만 품질이 좋음
                latency_threshold_ms=8000.0,  # 8초
                max_consecutive_failures=3
            ),
            "gemini": LLMProviderWeights(
                provider_name="gemini",
                base_weight=0.6,  # 세 번째 우선순위 (폴백용)
                performance_multiplier=0.9,
                cost_efficiency=1.2,  # 가장 저렴함
                latency_threshold_ms=12000.0,  # 12초 (폴백용이므로 여유있게)
                max_consecutive_failures=5
            )
        }
        
    def select_best_provider(
        self, providers: Dict[str, LLMProvider]
    ) -> Optional[str]:
        """
        사용 가능한 제공자 중에서 가중치 기반으로 최적의 제공자를 선택합니다.
        
        Args:
            providers: 사용 가능한 제공자 딕셔너리
            
        Returns:
            선택된 제공자 이름 또는 None
        """
        if not providers:
            return None
            
        # 건강한 제공자만 필터링
        healthy_providers = {}
        provider_scores = {}
        
        for name, provider in providers.items():
            if not provider.is_healthy():
                logger.warning(f"제공자 {name}가 비건강 상태로 제외됩니다.")
                continue
                
            # 가중치 설정이 있는 제공자만 고려
            if name not in self.provider_weights:
                logger.warning(f"제공자 {name}에 대한 가중치 설정이 없습니다.")
                continue
                
            weights = self.provider_weights[name]
            
            # 제외 조건 확인
            if weights.should_exclude_provider(provider.stats):
                logger.warning(f"제공자 {name}가 제외 조건에 의해 제외됩니다.")
                continue
                
            # 동적 가중치 계산
            dynamic_weight = weights.calculate_dynamic_weight(provider.stats)
            
            healthy_providers[name] = provider
            provider_scores[name] = dynamic_weight
            
            logger.debug(f"제공자 {name} 점수: {dynamic_weight:.3f}")
        
        if not healthy_providers:
            logger.error("사용 가능한 건강한 제공자가 없습니다.")
            return None
            
        # 가장 높은 점수의 제공자 선택
        best_provider = max(provider_scores.items(), key=lambda x: x[1])
        selected_name = best_provider[0]
        selected_score = best_provider[1]
        
        logger.info(f"선택된 제공자: {selected_name} (점수: {selected_score:.3f})")
        return selected_name
    
    def get_fallback_order(
        self, providers: Dict[str, LLMProvider], exclude: Optional[str] = None
    ) -> List[str]:
        """
        폴백 순서를 가중치 기반으로 결정합니다.
        
        Args:
            providers: 사용 가능한 제공자 딕셔너리
            exclude: 제외할 제공자 이름
            
        Returns:
            폴백 순서 리스트
        """
        if not providers:
            return []
            
        provider_scores = []
        
        for name, provider in providers.items():
            if exclude and name == exclude:
                continue
                
            if name not in self.provider_weights:
                continue
                
            weights = self.provider_weights[name]
            
            # 완전히 죽은 제공자가 아니라면 폴백 후보에 포함
            # (is_healthy()는 더 엄격한 기준이므로 폴백에는 더 관대한 기준 적용)
            # 10회 연속 실패 시에만 완전 제외
            if provider.stats.consecutive_failures >= 10:
                continue
                
            # 가중치가 매우 낮더라도 폴백 후보에는 포함
            dynamic_weight = max(
                0.1, weights.calculate_dynamic_weight(provider.stats)
            )
            provider_scores.append((name, dynamic_weight))
        
        # 점수 기준으로 내림차순 정렬
        provider_scores.sort(key=lambda x: x[1], reverse=True)
        
        fallback_order = [name for name, _ in provider_scores]
        logger.debug(f"폴백 순서: {fallback_order}")
        
        return fallback_order


class LLMRouter:
    """LLM 라우팅 및 Fallback 로직 구현"""
    
    def __init__(self, timeout: float = 10.0, gemini_timeout: float = 20.0):
        """
        LLM 라우터 초기화
        
        Args:
            timeout: Anthropic, OpenAI용 기본 타임아웃
            gemini_timeout: Gemini용 별도 타임아웃 (더 긴 시간)
        """
        self.timeout = timeout
        self.anthropic = AnthropicProvider()
        self.openai = OpenAIProvider()
        self.gemini = GeminiProvider()
        
        # 제공자 우선순위 및 상태 관리
        # 성능 기반 우선순위: OpenAI > Anthropic > Gemini (응답 속도 최적화)
        self.providers_priority = ["openai", "anthropic", "gemini"]
        self.provider_instances: Dict[str, LLMProvider] = {
            "anthropic": self.anthropic,
            "openai": self.openai,
            "gemini": self.gemini
        }
        
        # 가중치 기반 제공자 선택기 초기화
        self.provider_selector = LLMProviderSelector()
        
        # 통합 벡터 검색 최적화 모듈 초기화
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.search_optimizer = VectorSearchOptimizer(redis_url=redis_url)

    async def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.2
    ) -> LLMResponse:
        """
        최적의 LLM 제공자를 선택하고, 실패 시 순차적으로 Fallback하여 텍스트 생성
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택사항)
            max_tokens: 최대 토큰 수
            temperature: 온도 설정
            
        Returns:
            LLM 응답 객체
            
        Raises:
            RuntimeError: 모든 LLM 제공자 호출이 실패한 경우
        """
        # 동적으로 시도할 제공자 목록 생성
        ordered_providers = self._get_ordered_providers(prompt)

        last_error: Optional[Exception] = None
        attempt_count = 0
        
        for provider_name in ordered_providers:
            provider = self.provider_instances[provider_name]
            attempt_count += 1
            
            if not provider.api_key:
                logger.warning(f"{provider.name} 제공자는 API 키가 없어 건너뜁니다.")
                continue
            if not provider.is_healthy():
                logger.warning(f"{provider.name} 제공자가 건강하지 않아 건너뜁니다 (성공률: {provider.stats.success_rate:.2f}, 연속실패: {provider.stats.consecutive_failures}).")
                continue

            try:
                logger.info(f"{provider.name} ({attempt_count}번째 시도)로 생성 시작...")
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                # 성공 시 메타데이터에 시도 정보 추가
                response.attempt_count = attempt_count
                response.is_fallback = attempt_count > 1
                if attempt_count > 1 and last_error:
                    response.previous_provider_error = f"{type(last_error).__name__}: {str(last_error)}"
                
                return response
            except Exception as e:
                logger.warning(f"{provider.name} 제공자로 생성 실패: {type(e).__name__} - {str(e)}. 다음 제공자로 Fallback 시도합니다.")
                last_error = e
        
        logger.error(f"모든 LLM 제공자 호출 실패. 마지막 오류: {type(last_error).__name__} - {str(last_error)} (총 {attempt_count}번 시도)")
        raise RuntimeError(f"모든 LLM 제공자 호출 실패 (마지막 오류: {type(last_error).__name__} - {str(last_error)})")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        """
        최적의 LLM 제공자를 선택하고, 스트리밍 방식으로 텍스트 생성
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택사항)
            max_tokens: 최대 토큰 수
            temperature: 온도 설정
            
        Yields:
            str: 생성된 텍스트 청크들
            
        Raises:
            RuntimeError: 모든 LLM 제공자 호출이 실패한 경우
        """
        # 동적으로 시도할 제공자 목록 생성
        ordered_providers = self._get_ordered_providers(prompt)

        last_error: Optional[Exception] = None
        attempt_count = 0
        
        for provider_name in ordered_providers:
            provider = self.provider_instances[provider_name]
            attempt_count += 1
            
            if not provider.api_key:
                logger.warning(f"{provider.name} 제공자는 API 키가 없어 건너뜁니다.")
                continue
            if not provider.is_healthy():
                logger.warning(f"{provider.name} 제공자가 건강하지 않아 건너뜁니다 (성공률: {provider.stats.success_rate:.2f}, 연속실패: {provider.stats.consecutive_failures}).")
                continue

            try:
                logger.info(f"{provider.name} ({attempt_count}번째 시도)로 스트리밍 생성 시작...")
                async for chunk in provider.generate_stream(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                ):
                    yield chunk
                return  # 성공 시 종료
            except Exception as e:
                logger.warning(f"{provider.name} 제공자로 스트리밍 생성 실패: {type(e).__name__} - {str(e)}. 다음 제공자로 Fallback 시도합니다.")
                last_error = e
        
        logger.error(f"모든 LLM 제공자 스트리밍 호출 실패. 마지막 오류: {type(last_error).__name__} - {str(last_error)} (총 {attempt_count}번 시도)")
        raise RuntimeError(f"모든 LLM 제공자 스트리밍 호출 실패 (마지막 오류: {type(last_error).__name__} - {str(last_error)})")

    def _get_ordered_providers(self, prompt: str) -> List[str]:
        """
        요청 특성 및 제공자 상태를 기반으로 시도할 제공자 이름 목록을 우선순위대로 반환합니다.
        가중치 기반 선택 로직을 사용하여 동적으로 최적의 순서를 결정합니다.
        
        Args:
            prompt: 사용자 프롬프트 (분석용)
            
        Returns:
            우선순위대로 정렬된 제공자 이름 목록
        """
        # 1. 먼저 최고 우선순위 제공자 선택
        best_provider = self.provider_selector.select_best_provider(self.provider_instances)
        
        if not best_provider:
            # 모든 제공자가 사용 불가능한 경우 기존 우선순위 사용
            logger.warning("가중치 기반 선택에서 건강한 제공자를 찾지 못해 기존 우선순위를 사용합니다.")
            available_providers = [
                name for name in self.providers_priority 
                if self.provider_instances[name].api_key
            ]
            logger.info(f"기본 우선순위 제공자 순서: {available_providers}")
            return available_providers
        
        # 2. 폴백 순서 결정 (선택된 제공자 제외)
        fallback_order = self.provider_selector.get_fallback_order(
            self.provider_instances, 
            exclude=best_provider
        )
        
        # 3. 최종 순서: 최선의 제공자 + 폴백 순서
        ordered_list = [best_provider] + fallback_order
        
        # 4. API 키가 없는 제공자 제거 (최종 검증)
        valid_providers = [
            name for name in ordered_list 
            if self.provider_instances[name].api_key
        ]
        
        if not valid_providers:
            logger.error("사용 가능한 LLM 제공자가 없습니다 (API 키 부재).")
            return []
        
        logger.info(f"가중치 기반 제공자 순서: {valid_providers}")
        return valid_providers

    def _extract_conversation_body(self, conv: Dict[str, Any]) -> str:
        """
        대화 딕셔너리에서 본문 텍스트를 안전하게 추출합니다.
        여러 가능한 필드를 순서대로 시도합니다.
        
        Args:
            conv: 대화 항목 딕셔너리
            
        Returns:
            추출된 본문 텍스트
        """
        if not isinstance(conv, dict):
            return str(conv)[:300]
            
        # 가능한 필드들을 우선순위대로 시도
        for field in ["body_text", "body", "text", "content", "message"]:
            if field in conv and conv[field]:
                content = conv[field]
                # HTML 태그 제거 시도
                if isinstance(content, str) and "<" in content and ">" in content:
                    try:
                        # 간단한 HTML 태그 제거 (실패하면 원본 사용)
                        content = re.sub(r'<[^>]+>', ' ', content)
                    except:
                        pass
                return str(content)
        
        # 필드를 찾지 못한 경우 전체 딕셔너리를 문자열로 변환
        try:
            # 너무 길면 잘라내기
            return str(conv)[:300]
        except:
            return "내용을 추출할 수 없음"
    
    async def generate_ticket_summary(self, ticket_data: Dict[str, Any], max_tokens: int = 1000) -> Dict[str, Any]:
        """
        티켓 데이터를 기반으로 LLM을 사용하여 요약문과 주요 정보를 생성합니다.
        
        Args:
            ticket_data: 티켓 정보가 포함된 딕셔너리
            max_tokens: 요약문 최대 토큰 수
            
        Returns:
            생성된 티켓 요약 정보를 포함하는 딕셔너리
            {
                'summary': '요약문',
                'key_points': ['핵심 포인트 1', '핵심 포인트 2', ...],
                'sentiment': '감정 상태',
                'urgency_level': '긴급도',
                'priority_recommendation': '우선순위 추천'
            }
            
        Raises:
            RuntimeError: 모든 LLM 제공자 호출이 실패한 경우
        """
        # 컨텍스트 빌더를 사용하여 LLM 프롬프트에 적합한 형태로 티켓 정보 구성
        subject = ticket_data.get("subject", "제목 없음")
        description = ticket_data.get("description_text", "설명 없음")
        conversations = ticket_data.get("conversations", [])
        
        # 간단한 프롬프트 구성
        prompt_context = f"티켓 제목: {subject}\n티켓 설명: {description}\n"
        
        if conversations:
            prompt_context += "\n최근 대화 내용:\n"
            # conversations의 타입에 따라 적절히 처리
            if isinstance(conversations, list):
                try:
                    # 대화 항목들을 필터링하고 시간 순서대로 정렬
                    valid_conversations = [c for c in conversations if isinstance(c, dict)]
                    
                    if valid_conversations:
                        # 시간순으로 정렬 (오래된 순 -> 최신순)
                        sorted_conversations = sorted(
                            valid_conversations,
                            key=lambda x: x.get('created_at', ''),
                            reverse=False
                        )
                        
                        # 최근 5개 대화만 포함
                        recent_conversations = sorted_conversations[-5:]
                        
                        for i, conv in enumerate(recent_conversations, 1):
                            body_text = self._extract_conversation_body(conv)
                            if body_text and body_text.strip():
                                prompt_context += f"{i}. {body_text[:200]}\n"
                except Exception as e:
                    logger.warning(f"대화 내용 처리 중 오류 발생: {e}")
                    # 오류 발생 시 기본 처리
                    if conversations:
                        first_conv = conversations[0]
                        body_text = self._extract_conversation_body(first_conv)
                        if body_text:
                            prompt_context += f"1. {body_text[:200]}\n"
        
        # 요약 생성 프롬프트
        system_prompt = """당신은 고객 지원 티켓 분석 전문가입니다. 주어진 티켓 정보를 분석하여 다음 형식의 JSON으로 응답해주세요:

{
    "summary": "티켓의 핵심 내용을 2-3문장으로 요약",
    "key_points": ["주요 이슈나 요구사항을 3-5개 항목으로 나열"],
    "sentiment": "고객의 감정 상태 (긍정적/중립적/부정적/화난상태)",
    "urgency_level": "긴급도 (낮음/보통/높음/매우높음)",
    "priority_recommendation": "처리 우선순위 추천 (낮음/보통/높음/긴급)"
}

분석 시 다음 사항을 고려해주세요:
- 고객의 언어 톤과 감정
- 문제의 기술적 복잡성
- 비즈니스 영향도
- 시간 민감성"""

        user_prompt = f"""다음 고객 지원 티켓을 분석해주세요:

{prompt_context}

위 티켓 정보를 바탕으로 요약, 핵심 포인트, 감정 분석, 긴급도, 우선순위를 JSON 형식으로 제공해주세요."""

        try:
            # LLM 호출
            response = await self.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.1  # 일관성을 위해 낮은 온도 사용
            )
            
            # JSON 파싱 시도
            try:
                import json
                # 응답에서 JSON 부분만 추출
                response_text = response.text.strip()
                
                # JSON 블록 찾기
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif '{' in response_text and '}' in response_text:
                    # 첫 번째 { 부터 마지막 } 까지 추출
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    json_text = response_text[json_start:json_end]
                else:
                    json_text = response_text
                
                parsed_result = json.loads(json_text)
                
                # 필수 필드 검증 및 기본값 설정
                result = {
                    'summary': parsed_result.get('summary', '요약 생성 실패'),
                    'key_points': parsed_result.get('key_points', ['분석 실패']),
                    'sentiment': parsed_result.get('sentiment', '중립적'),
                    'urgency_level': parsed_result.get('urgency_level', '보통'),
                    'priority_recommendation': parsed_result.get('priority_recommendation', '보통'),
                    'raw_response': response.text,
                    'provider_used': response.model_used,
                    'tokens_used': response.tokens_used
                }
                
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"LLM 응답을 JSON으로 파싱 실패: {e}")
                # 파싱 실패 시 기본 응답 반환
                return {
                    'summary': f"티켓 주제: {subject}",
                    'key_points': [description[:100] if description else "설명 없음"],
                    'sentiment': '중립적',
                    'urgency_level': '보통',
                    'priority_recommendation': '보통',
                    'raw_response': response.text,
                    'provider_used': response.model_used,
                    'tokens_used': response.tokens_used,
                    'parsing_error': str(e)
                }
                
        except Exception as e:
            logger.error(f"티켓 요약 생성 실패: {e}")
            raise RuntimeError(f"티켓 요약 생성 중 오류 발생: {str(e)}")

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        모든 제공자의 통계 정보를 반환합니다.
        
        Returns:
            제공자별 통계 정보 딕셔너리
        """
        stats = {}
        for name, provider in self.provider_instances.items():
            stats[name] = {
                "provider_name": provider.name,
                "is_healthy": provider.is_healthy(),
                "has_api_key": bool(provider.api_key),
                "total_requests": provider.stats.total_requests,
                "successful_requests": provider.stats.successful_requests,
                "failed_requests": provider.stats.failed_requests,
                "success_rate": provider.stats.success_rate,
                "average_latency_ms": provider.stats.average_latency_ms,
                "consecutive_failures": provider.stats.consecutive_failures,
                "total_tokens_used": provider.stats.total_tokens_used,
                "last_error_timestamp": provider.stats.last_error_timestamp
            }
        return stats

    async def health_check(self) -> Dict[str, Any]:
        """
        모든 제공자의 건강 상태를 확인합니다.
        
        Returns:
            전체 라우터 건강 상태 정보
        """
        provider_health = {}
        healthy_count = 0
        total_count = 0
        
        for name, provider in self.provider_instances.items():
            if not provider.api_key:
                status = "api_key_missing"
            elif provider.is_healthy():
                status = "healthy"
                healthy_count += 1
            else:
                status = "unhealthy"
            
            provider_health[name] = {
                "status": status,
                "success_rate": provider.stats.success_rate,
                "consecutive_failures": provider.stats.consecutive_failures,
                "average_latency_ms": provider.stats.average_latency_ms
            }
            
            if provider.api_key:  # API 키가 있는 제공자만 카운트
                total_count += 1
        
        overall_status = "healthy" if healthy_count > 0 else "unhealthy"
        if total_count == 0:
            overall_status = "no_providers"
        
        return {
            "overall_status": overall_status,
            "healthy_providers": healthy_count,
            "total_providers": total_count,
            "providers": provider_health,
            "timestamp": time.time()
        }
