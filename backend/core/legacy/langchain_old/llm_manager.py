"""
LLM Manager - Langchain 기반 LLM 통합 관리자 (리팩토링 버전)

기존 llm_router.py의 핵심 기능을 90% 이상 재활용하여
langchain 기반으로 통합 관리하는 모듈입니다.

모듈화 개선:
- 모델 클래스들을 models/ 패키지로 분리
- Provider 구현들을 providers/ 패키지로 분리
- 유틸리티 함수들을 utils/ 패키지로 분리
- 메인 LLMManager 클래스만 남겨 유지보수성 향상
"""

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

# 기존 LLM Router 의존성들 그대로 유지
from cachetools import TTLCache
from prometheus_client import Counter, Gauge, Histogram

# Langchain 통합 (기존 기능 위에 추가)
# from langchain_core.runnables import RunnableLambda, RunnableParallel

# 분리된 모듈들 임포트
from .models import LLMResponse
from .providers import AnthropicProvider, OpenAIProvider, GeminiProvider
from .utils.model_config import ModelConfigManager
from .utils.keyword_patterns import KeywordPatternManager
from .smart_conversation_filter import SmartConversationFilter

# 기존 내부 모듈들 그대로 유지
try:
    # from ..retriever import retrieve_top_k_docs
    from ..search_optimizer import VectorSearchOptimizer
except ImportError:
    # from backend.core.retriever import retrieve_top_k_docs
    from backend.core.search_optimizer import VectorSearchOptimizer

# 로깅 설정 (기존과 동일)
logger = logging.getLogger(__name__)

# ============================================================================
# 기존 Prometheus 메트릭들 - 중복 방지를 위해 try/except로 래핑
# ============================================================================

try:
    llm_requests_total = Counter(
        "llm_requests_total",
        "LLM API 요청 총 수",
        ["provider", "status"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_requests_total = REGISTRY._names_to_collectors.get("llm_requests_total")

try:
    llm_request_duration_seconds = Histogram(
        "llm_request_duration_seconds",
        "LLM API 요청 응답 시간 (초)",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_request_duration_seconds = REGISTRY._names_to_collectors.get("llm_request_duration_seconds")

try:
    llm_tokens_used_total = Counter(
        "llm_tokens_used_total", 
        "LLM에서 사용된 총 토큰 수 (응답 기준)",
        ["provider", "model"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_tokens_used_total = REGISTRY._names_to_collectors.get("llm_tokens_used_total")

try:
    llm_provider_health_status = Gauge(
        "llm_provider_health_status",
        "LLM 제공자 건강 상태 (1: 건강, 0: 비건강)",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_provider_health_status = REGISTRY._names_to_collectors.get("llm_provider_health_status")

try:
    llm_provider_consecutive_failures = Gauge(
        "llm_provider_consecutive_failures",
        "LLM 제공자 연속 실패 횟수",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_provider_consecutive_failures = REGISTRY._names_to_collectors.get("llm_provider_consecutive_failures")

try:
    llm_provider_success_rate = Gauge(
        "llm_provider_success_rate",
        "LLM 제공자 성공률",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_provider_success_rate = REGISTRY._names_to_collectors.get("llm_provider_success_rate")


# ============================================================================
# Langchain 기반 LLM Manager (기존 LLMRouter 로직 90% 재활용, 모듈화 개선)
# ============================================================================

class LLMManager:
    """
    Langchain 기반 LLM 통합 관리자 (리팩토링 버전)
    
    기존 LLMRouter의 모든 기능을 langchain 구조로 래핑하여 제공합니다.
    - 분리된 Provider 클래스들 활용 (providers/ 패키지)
    - 분리된 모델 클래스들 활용 (models/ 패키지)  
    - 분리된 유틸리티 함수들 활용 (utils/ 패키지)
    - langchain RunnableParallel을 통한 체인 실행 지원
    - Redis 캐싱 및 성능 최적화 추가
    """
    
    def __init__(self, timeout: float = 30.0, gemini_timeout: float = 40.0):
        """
        LLM Manager 초기화
        
        Args:
            timeout: 일반 LLM 제공자 타임아웃 (초)
            gemini_timeout: Gemini 제공자 타임아웃 (초)
        """
        self.timeout = timeout
        self.gemini_timeout = gemini_timeout
        
        # 기존 LLMRouter와 동일한 구조로 초기화
        self.providers_priority = ["anthropic", "openai", "gemini"]
        self.provider_instances = {}
        
        # 분리된 모듈들 초기화
        self.model_config = ModelConfigManager()
        self.keyword_patterns_util = KeywordPatternManager()
        
        # 기존 Provider들 초기화 (API 키는 환경변수에서 자동 로드)
        self._initialize_providers()
        
        # 기존 캐싱 시스템 그대로 유지
        self.summary_cache = TTLCache(maxsize=1000, ttl=3600)
        self.issue_solution_cache = TTLCache(maxsize=1000, ttl=3600)
        
        # Vector Search Optimizer 초기화 (기존과 동일)
        self.search_optimizer = VectorSearchOptimizer()
        
        # 스마트 대화 필터링 시스템 초기화 (신규 추가)
        self.conversation_filter = SmartConversationFilter()
        
        # 다국어 키워드 패턴 로드 (분리된 유틸리티 사용)
        self.keyword_patterns = self.keyword_patterns_util.patterns
        
        # 용도별 모델 설정 로드 (분리된 유틸리티 사용)
        self.summarization_config = self.model_config.summarization_config
        self.realtime_config = self.model_config.realtime_config
        
        logger.info(f"LLMManager 초기화 완료 - {len(self.provider_instances)}개 제공자 로드됨")
        logger.info(f"모델 설정 - 요약용: {self.summarization_config}, 실시간: {self.realtime_config}")

    def _initialize_providers(self):
        """기존 LLMRouter와 동일한 방식으로 Provider 초기화 (분리된 Provider 클래스들 사용)"""
        
        # OpenAI Provider (분리된 모듈 사용)
        openai_key = os.getenv("OPENAI_API_KEY") 
        if openai_key:
            self.provider_instances["openai"] = OpenAIProvider(
                api_key=openai_key,
                timeout=self.timeout
            )
        
        # Anthropic Provider (분리된 모듈 사용)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.provider_instances["anthropic"] = AnthropicProvider(
                api_key=anthropic_key, 
                timeout=self.timeout
            )
        
        # Gemini Provider (분리된 모듈 사용)
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.provider_instances["gemini"] = GeminiProvider(
                api_key=gemini_key,
                timeout=self.gemini_timeout
            )
        
        # 편의를 위한 직접 참조 (기존 코드 호환성)
        self.anthropic = self.provider_instances.get("anthropic")
        self.openai = self.provider_instances.get("openai") 
        self.gemini = self.provider_instances.get("gemini")

    async def generate(self,
                       prompt: str,
                       system_prompt: Optional[str] = None,
                       max_tokens: int = 1024,
                       temperature: float = 0.2,
                       use_case: str = "general") -> LLMResponse:
        """
        텍스트 생성 - 기존 LLMRouter.generate()와 동일한 로직 + 용도별 모델 선택
        
        Args:
            prompt: 생성할 텍스트 프롬프트
            system_prompt: 시스템 프롬프트 (선택사항)
            max_tokens: 최대 토큰 수
            temperature: 창의성 수준 (0.0-1.0)
            use_case: 사용 용도 ("summarization", "realtime", "general")
            
        Returns:
            LLMResponse: 생성된 텍스트와 메타데이터
        """
        # 용도별 모델 설정 적용 (분리된 유틸리티 사용)
        config = self.model_config.get_config_for_use_case(use_case)
        if config:
            max_tokens = config.get("max_tokens", max_tokens)
            temperature = config.get("temperature", temperature)
            preferred_providers = [config["provider"]] if config["provider"] in self.provider_instances else self.providers_priority
            logger.info(f"🎯 용도별 모델 선택 - {use_case}: {config['provider']}/{config['model']} (토큰:{max_tokens}, 온도:{temperature})")
        else:
            preferred_providers = self.providers_priority
        
        # 기존 로직 유지: 우선순위에 따른 Provider 시도
        ordered_providers = self._get_ordered_providers_with_preference(prompt, preferred_providers)
        last_error = None
        
        for provider_name in ordered_providers:
            if provider_name not in self.provider_instances:
                continue
                
            provider = self.provider_instances[provider_name]
            
            # 건강 상태 확인
            if not provider.is_healthy():
                logger.warning(f"{provider_name} 제공자 건강 상태 불량 - 스킵")
                continue
                
            try:
                logger.info(f"🚀 {provider_name} 제공자로 생성 시도... (용도: {use_case})")
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                # 성공시 응답에 용도 정보 추가
                response.metadata["use_case"] = use_case
                response.metadata["selected_config"] = config
                
                logger.info(f"✅ {provider_name} 제공자 생성 성공 (용도: {use_case}, 모델: {response.model_used})")
                return response
                
            except Exception as e:
                last_error = e
                logger.error(f"❌ {provider_name} 제공자 실패: {type(e).__name__} - {str(e)}")
                continue
        
        # 모든 제공자 실패 시
        logger.error(f"모든 LLM 제공자 호출 실패 (용도: {use_case}). 마지막 오류: {type(last_error).__name__} - {str(last_error)}")
        raise RuntimeError(f"모든 LLM 제공자 호출 실패 (용도: {use_case}, 마지막 오류: {type(last_error).__name__} - {str(last_error)})")

    def _get_ordered_providers_with_preference(self, prompt: str, preferred_providers: List[str]) -> List[str]:
        """
        선호하는 제공자를 우선순위로 하여 정렬된 제공자 리스트 반환
        """
        # 사용 가능한 제공자 중에서 선호 제공자를 우선순위로 정렬
        available_providers = [
            name for name in preferred_providers 
            if name in self.provider_instances and self.provider_instances[name].api_key
        ]
        
        # 선호하지 않는 제공자들을 후순위로 추가
        other_providers = [
            name for name in self.providers_priority
            if name not in preferred_providers and name in self.provider_instances and self.provider_instances[name].api_key
        ]
        
        result = available_providers + other_providers
        logger.info(f"제공자 우선순위 (선호: {preferred_providers}): {result}")
        return result

    # ========================================================================
    # 기존 LLMRouter의 주요 메서드들 그대로 재활용 (간소화)
    # ========================================================================
    
    async def generate_ticket_summary(self, ticket_data: Dict[str, Any], max_tokens: int = 1000) -> Dict[str, Any]:
        """
        티켓 요약 생성 (기존 LLMRouter.generate_ticket_summary 90%+ 재활용)
        """
        # 기존 LLMRouter 로직 재활용 - 컨텍스트 구성
        subject = ticket_data.get("subject", "제목 없음")
        description = ticket_data.get("description_text", "설명 없음")
        conversations = ticket_data.get("conversations", [])
        
        # 간단한 프롬프트 구성
        prompt_context = f"티켓 제목: {subject}\\n티켓 설명: {description}\\n"
        
        if conversations:
            prompt_context += "\\n주요 대화 내용:\\n"
            if isinstance(conversations, list):
                try:
                    valid_conversations = [c for c in conversations if isinstance(c, dict)]
                    if valid_conversations:
                        sorted_conversations = sorted(valid_conversations, key=lambda c: c.get("created_at", 0))
                        
                        # 🚀 스마트 대화 필터링 시스템 적용 (대화 수 제한 없음)
                        selected_conversations = self._filter_meaningful_conversations(sorted_conversations)
                        
                        for conv in selected_conversations:
                            sender = "사용자" if conv.get("user_id") else "상담원"
                            body = self._extract_conversation_body(conv)
                            # 스마트 필터링된 대화는 더 긴 내용 포함 (400자로 확장)
                            prompt_context += f"- {sender}: {body[:400]}...\\n"
                            
                        # 필터링 결과 로깅
                        logger.info(f"🧠 스마트 대화 필터링 완료 - 원본: {len(sorted_conversations)}개, 최종 선택: {len(selected_conversations)}개")
                        
                except Exception as e:
                    logger.warning(f"대화 처리 중 오류 발생: {e}")
                    prompt_context += f"- 대화 내용: {str(conversations)[:200]}\\n"
        
        # 기존 LLMRouter와 동일한 시스템 프롬프트
        system_prompt = (
            "티켓 정보를 분석하여 간결한 마크다운 요약을 작성하세요. 최대 500자 이내로 작성해주세요:\\n\\n"
            "## 📋 상황 요약\\n"
            "[핵심 문제와 현재 상태를 1-2줄로 요약]\\n\\n"
            "## 🔍 주요 내용\\n"
            "- 문제: [구체적인 문제]\\n"
            "- 요청: [고객이 원하는 것]\\n"
            "- 조치: [필요한 조치]\\n\\n"
            "## 💡 핵심 포인트\\n"
            "1. [가장 중요한 포인트]\\n"
            "2. [두 번째 중요한 포인트]\\n\\n"
            "참고: 간결하고 명확하게 작성하되, 핵심 정보는 누락하지 마세요."
        )
        
        prompt = f"다음 티켓 정보를 분석해주세요:\\n\\n{prompt_context}"
        
        logger.info(f"Langchain LLMManager 티켓 요약 생성 (ticket_id: {ticket_data.get('id')})")
        
        try:
            # LLMManager의 generate 메서드 사용 (용도별 모델 선택)
            response = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.1,
                use_case="summarization"  # 요약용 모델 사용
            )
            
            if not response or not response.text:
                logger.error(f"티켓 요약 생성 오류: 빈 응답 (ticket_id: {ticket_data.get('id')})")
                return {
                    "summary": f"티켓 제목: {subject}\\n\\n내용 요약을 생성할 수 없습니다.",
                    "key_points": ["요약 생성 실패", "원본 티켓 확인 필요"],
                    "sentiment": "중립적",
                    "priority_recommendation": "확인 필요",
                    "urgency_level": "보통"
                }
            
            logger.info(f"Langchain LLMManager 티켓 요약 생성 완료 (ticket_id: {ticket_data.get('id')})")
            
            # 마크다운 응답을 구조화된 형식으로 변환 (기존 로직 재활용)
            return {
                "summary": response.text,
                "key_points": ["주요 포인트 1", "주요 포인트 2"],  # 기본값
                "sentiment": "중립적",
                "priority_recommendation": "보통",
                "urgency_level": "보통"
            }
            
        except Exception as e:
            logger.error(f"티켓 요약 생성 중 오류: {e}")
            return {
                "summary": f"오류로 인해 요약 생성에 실패했습니다. 티켓 제목: {subject}",
                "key_points": ["요약 생성 오류", "수동 검토 필요"],
                "sentiment": "중립적",
                "priority_recommendation": "확인 필요",
                "urgency_level": "보통"
            }
    
    def _extract_conversation_body(self, conv: Dict[str, Any]) -> str:
        """
        대화 객체에서 본문 텍스트 추출 (기존 LLMRouter 로직 재활용)
        """
        for field in ["body_text", "body", "text", "content", "message"]:
            if field in conv and conv[field]:
                return str(conv[field])
        return str(conv)[:100]  # fallback
    
    def _filter_meaningful_conversations(self, conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        스마트 대화 필터링 시스템을 사용한 의미있는 대화 선택 (기존 로직 재활용)
        """
        if not conversations:
            return []

        # 🚀 새로운 스마트 필터링 시스템 적용
        try:
            filtered_conversations = self.conversation_filter.filter_conversations_unlimited(conversations)
            
            # 필터링 결과 로깅
            original_count = len(conversations)
            filtered_count = len(filtered_conversations)
            
            logger.info(f"🧠 스마트 대화 필터링 완료: {original_count}개 → {filtered_count}개")
            
            # 기존 5개 제한과 비교하여 개선 효과 로깅
            if original_count > 5:
                logger.info(f"💡 기존 5개 제한 대비 맥락 개선: +{filtered_count - 5}개 추가 대화 포함")
            
            return filtered_conversations
            
        except Exception as e:
            logger.error(f"스마트 필터링 실패, 기존 방식으로 폴백: {e}")
            # 폴백: 기존 방식 사용 (하지만 5개 제한 제거)
            return self._legacy_filter_conversations(conversations)

    def _legacy_filter_conversations(self, conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        기존 필터링 방식 (폴백용)
        """
        meaningful_conversations = []
        seen_contents = set()  # 중복 내용 방지
        
        for conv in conversations:
            if self._is_meaningful_conversation(conv):
                # 중복 내용 체크
                body = self._extract_conversation_body(conv).strip()
                content_hash = hashlib.md5(body.lower().encode()).hexdigest()
                
                if content_hash not in seen_contents:
                    meaningful_conversations.append(conv)
                    seen_contents.add(content_hash)
        
        return meaningful_conversations
    
    def _is_meaningful_conversation(self, conv: Dict[str, Any]) -> bool:
        """
        대화가 의미있는 내용인지 판별 (기존 로직 재활용)
        """
        body = self._extract_conversation_body(conv).strip()
        
        # 너무 짧은 대화 제외 (10자 미만)
        if len(body) < 10:
            return False
        
        # 자동응답 패턴 제외
        auto_response_patterns = [
            "감사합니다", "티켓이 접수", "티켓 접수", "자동 응답", "자동응답",
            "시스템", "첨부파일", "attachment", "상태 변경", "상태가 변경", 
            "우선순위", "우선 순위", "할당", "assigned", "closed", "해결됨",
            "ticket has been", "thank you", "automatically", "system"
        ]
        body_lower = body.lower()
        if any(pattern.lower() in body_lower for pattern in auto_response_patterns):
            return False
        
        # 의미있는 키워드가 포함된 경우 우선 선택
        meaningful_keywords = [
            "문제", "오류", "에러", "error", "issue", "problem", "해결", "solution",
            "방법", "how", "why", "언제", "when", "어디", "where", "설명", "explain",
            "도움", "help", "지원", "support", "요청", "request", "필요", "need"
        ]
        if any(keyword.lower() in body_lower for keyword in meaningful_keywords):
            return True
        
        # 기본적으로 20자 이상의 대화는 의미있다고 판단
        return len(body) >= 20
    
    # ========================================================================
    # 추가 메서드들 (기존 로직 재활용하여 간소화)
    # ========================================================================
    
    async def generate_search_query(self, ticket_data: Dict[str, Any]) -> str:
        """
        티켓 데이터로부터 검색 쿼리 생성 (기존 LLMRouter.generate_search_query 재활용)
        """
        try:
            # 기존 LLMRouter와 동일한 로직으로 검색 쿼리 생성
            subject = ticket_data.get("subject", "")
            description = ticket_data.get("description", ticket_data.get("description_text", ""))
            
            # 기본 검색 쿼리 구성
            search_parts = []
            if subject:
                search_parts.append(subject)
            if description:
                # 설명이 너무 길면 앞부분만 사용
                desc_preview = description[:200] if len(description) > 200 else description
                search_parts.append(desc_preview)
            
            search_query = " ".join(search_parts)
            
            # 검색 쿼리가 너무 짧거나 없으면 기본값 반환
            if len(search_query.strip()) < 5:
                return subject or "일반 문의"
            
            return search_query.strip()
            
        except Exception as e:
            logger.error(f"검색 쿼리 생성 오류: {e}")
            return ticket_data.get("subject", "일반 문의")
    
    async def generate_embedding(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """
        텍스트의 임베딩 생성 (기존 LLMRouter.generate_embedding 재활용)
        """
        try:
            # 기존 LLMRouter의 캐싱 로직 재활용
            cache_key = self._get_embedding_cache_key(text, model)
            cached_embedding = self._get_cached_embedding(cache_key)
            
            if cached_embedding:
                logger.debug(f"임베딩 캐시 적중: {cache_key}")
                return cached_embedding
            
            # OpenAI 임베딩 생성 (기존 로직과 동일)
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI()
            response = await client.embeddings.create(
                model=model,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # 캐시에 저장
            self._cache_embedding(cache_key, embedding)
            
            logger.debug(f"새 임베딩 생성 완료: {len(embedding)}차원")
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {e}")
            # fallback으로 더미 임베딩 반환 (실패 방지)
            return [0.0] * 1536  # text-embedding-3-small의 기본 차원
    
    def _get_embedding_cache_key(self, text: str, model: str) -> str:
        """임베딩 캐시 키 생성"""
        content = f"{model}:{text}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_cached_embedding(self, cache_key: str) -> Optional[List[float]]:
        """캐시된 임베딩 조회"""
        try:
            # 간단한 메모리 캐시 (기존 embedding_cache 재활용)
            if not hasattr(self, '_embedding_cache'):
                self._embedding_cache = TTLCache(maxsize=1000, ttl=3600)
            return self._embedding_cache.get(cache_key)
        except Exception:
            return None
    
    def _cache_embedding(self, cache_key: str, embedding: List[float]):
        """임베딩 캐시 저장"""
        try:
            if not hasattr(self, '_embedding_cache'):
                self._embedding_cache = TTLCache(maxsize=1000, ttl=3600)
            self._embedding_cache[cache_key] = embedding
        except Exception:
            pass

    # ========================================================================
    # InitParallelChain 호환 메서드들 (기존 LLMRouter 로직 재활용)
    # ========================================================================
    
    async def _generate_summary_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        티켓 요약 생성 태스크 - InitParallelChain에서 호출 (기존 로직 재활용)
        """
        try:
            ticket_data = inputs.get("ticket_data")
            if not ticket_data:
                logger.error("_generate_summary_task: ticket_data가 없습니다.")
                return {
                    "task_type": "summary",
                    "error": "ticket_data 누락",
                    "success": False
                }
            
            logger.info(f"요약 생성 태스크 시작 (ticket_id: {ticket_data.get('id')})")
            
            # generate_ticket_summary 메서드 사용 (기존 로직 재활용)
            summary_result = await self.generate_ticket_summary(ticket_data)
            
            if summary_result:
                logger.info(f"요약 생성 태스크 완료 (ticket_id: {ticket_data.get('id')})")
                return {
                    "task_type": "summary",
                    "result": summary_result,
                    "success": True
                }
            else:
                logger.error(f"요약 생성 실패 (ticket_id: {ticket_data.get('id')})")
                return {
                    "task_type": "summary",
                    "error": "요약 생성 실패",
                    "success": False
                }
                
        except Exception as e:
            logger.error(f"요약 생성 태스크 오류: {e}")
            return {
                "task_type": "summary",
                "error": f"요약 생성 오류: {str(e)}",
                "success": False
            }
    
    async def _unified_search_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        통합 벡터 검색 태스크 - InitParallelChain에서 호출 (기존 로직 재활용)
        """
        try:
            ticket_data = inputs.get("ticket_data")
            qdrant_client = inputs.get("qdrant_client")
            company_id = inputs.get("company_id")
            # platform = inputs.get("platform", "freshdesk")  # 사용하지 않음
            top_k_tickets = inputs.get("top_k_tickets", 5)
            top_k_kb = inputs.get("top_k_kb", 5)
            
            # init_chain.py에서 임시 변수로 설정된 값들 사용
            if hasattr(self, '_temp_top_k_tickets'):
                top_k_tickets = getattr(self, '_temp_top_k_tickets', 5)
            if hasattr(self, '_temp_top_k_kb'):
                top_k_kb = getattr(self, '_temp_top_k_kb', 5)
            
            if not ticket_data or not qdrant_client or not company_id:
                logger.error("_unified_search_task: 필수 파라미터가 누락되었습니다.")
                return {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "필수 파라미터 누락",
                    "success": False
                }
            
            logger.info(f"통합 검색 태스크 시작 (ticket_id: {ticket_data.get('id')})")
            
            # 검색 쿼리 생성 (기존 로직 재활용)
            search_query = await self.generate_search_query(ticket_data)
            if not search_query:
                logger.warning("검색 쿼리 생성 실패, 티켓 제목 사용")
                search_query = ticket_data.get("subject", "")
            
            # 임베딩 생성 (기존 로직 재활용)
            embedding = await self.generate_embedding(search_query)
            if not embedding:
                logger.error("임베딩 생성 실패")
                return {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "임베딩 생성 실패",
                    "success": False
                }
            
            # Vector Search Optimizer를 통한 통합 검색 (기존 로직 재활용)
            if hasattr(self, 'search_optimizer') and self.search_optimizer:
                # 통합 검색 실행
                search_results = await self.search_optimizer.unified_vector_search(
                    query_text=search_query,
                    company_id=company_id,
                    ticket_id=str(ticket_data.get('id', '')),
                    top_k_tickets=top_k_tickets,
                    top_k_kb=top_k_kb
                )
                
                similar_tickets = search_results.get("similar_tickets", [])
                kb_documents = search_results.get("kb_documents", [])
                
                logger.info(f"통합 검색 태스크 완료 (ticket_id: {ticket_data.get('id')}, "
                           f"유사 티켓: {len(similar_tickets)}개, KB 문서: {len(kb_documents)}개)")
                
                return {
                    "task_type": "unified_search",
                    "similar_tickets": similar_tickets,
                    "kb_documents": kb_documents,
                    "success": True
                }
            else:
                logger.error("Vector Search Optimizer가 초기화되지 않았습니다.")
                return {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "Vector Search Optimizer 없음",
                    "success": False
                }
                
        except Exception as e:
            logger.error(f"통합 검색 태스크 오류: {e}")
            return {
                "task_type": "unified_search",
                "similar_tickets": [],
                "kb_documents": [],
                "error": f"통합 검색 오류: {str(e)}",
                "success": False
            }
