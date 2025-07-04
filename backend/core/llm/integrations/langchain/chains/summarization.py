"""
실시간 티켓 요약 체인 - Anthropic 기법 적용된 프리미엄 요약 체인

기존 유사티켓/지식베이스 요약과 완전히 독립적인 실시간 요약 전용 체인입니다.
Anthropic 프롬프트 엔지니어링 기법(Constitutional AI, XML 구조화)을 적용했습니다.

핵심 차별화 요소:
- Anthropic 최적화 프롬프트 시스템 (YAML 기반, 하드코딩 제거)
- Constitutional AI 원칙 적용 (도움되고, 해롭지 않고, 정직한 요약)
- 프리미엄 품질 보장 (유사티켓 요약보다 우수한 품질)
- 5초 내 이해 가능한 구조화된 출력
- 에스컬레이션 즉시 준비 가능한 정보 제공
- 사용자 맞춤형 재시도 시스템 (이유별 품질 향상 전략)
- 첨부파일 처리 제외로 실시간 속도 최적화
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional
from enum import Enum

from cachetools import TTLCache
from langchain_core.runnables import RunnableLambda

# 통합된 LLM Manager 사용
from core.llm.manager import LLMManager
# Anthropic 요약기 통합
from core.llm.summarizer.core.anthropic_summarizer import AnthropicSummarizer

logger = logging.getLogger(__name__)


class RetryReason(Enum):
    """사용자 재시도 요청 이유"""
    QUALITY_LOW = "quality_low"  # 품질이 낮음
    DETAIL_INSUFFICIENT = "detail_insufficient"  # 세부사항 부족
    TONE_INAPPROPRIATE = "tone_inappropriate"  # 톤이 부적절
    FORMAT_POOR = "format_poor"  # 포맷이 나쁨
    LANGUAGE_UNCLEAR = "language_unclear"  # 언어가 불분명
    PRIORITY_WRONG = "priority_wrong"  # 우선순위 잘못 판단
    SOLUTION_MISSING = "solution_missing"  # 해결책 제안 부족


class SummarizationChain:
    """
    실시간 티켓 요약 체인 - Anthropic 기법 적용된 프리미엄 요약
    
    핵심 특징:
    - Anthropic 최적화 프롬프트 시스템 (YAML 기반, 하드코딩 제거)
    - Constitutional AI 원칙 적용 (도움되고, 해롭지 않고, 정직한 요약)
    - 프리미엄 품질 보장 (유사티켓 요약 대비 우수한 품질)
    - 5초 내 이해 가능한 구조화된 분석
    - 에스컬레이션 즉시 준비 가능한 정보 제공
    - 사용자 맞춤형 재시도 시스템 (이유별 품질 향상 전략)
    - 첨부파일 처리 제외로 실시간 속도 최적화
    """
    
    def __init__(self, cache_size: int = 1000, cache_ttl: int = 3600):
        """
        실시간 요약 체인 초기화
        
        Args:
            cache_size: 캐시 크기
            cache_ttl: 캐시 TTL (초)
        """
        self.summary_cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        self.llm_manager = LLMManager()
        self._anthropic_summarizer = None
        
        # 재시도 컨텍스트 매핑
        self.retry_context_mapping = {
            RetryReason.QUALITY_LOW: "quality_retry",
            RetryReason.DETAIL_INSUFFICIENT: "quality_retry", 
            RetryReason.TONE_INAPPROPRIATE: "quality_retry",
            RetryReason.FORMAT_POOR: "length_retry",
            RetryReason.LANGUAGE_UNCLEAR: "quality_retry",
            RetryReason.PRIORITY_WRONG: "quality_retry",
            RetryReason.SOLUTION_MISSING: "quality_retry"
        }
        
        logger.info("실시간 요약 체인 (Anthropic 최적화) 초기화 완료")
    
    def build_chain(self):
        """실시간 요약 체인 구성"""
        return RunnableLambda(self.run_summary)
    
    async def run_summary(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        실시간 티켓 요약 실행 - Anthropic 기법 적용
        
        기존 유사티켓/지식베이스 요약과 완전히 분리된 실시간 전용 요약
        - Constitutional AI 원칙 적용
        - XML 구조화된 응답
        - 5초 내 이해 가능한 구조화
        - 에스컬레이션 즉시 준비
        - 첨부파일 처리 제외 (실시간 속도 최적화)
        
        Args:
            input_data: {
                "ticket_data": Dict[str, Any],
                "max_tokens": int (optional, default=1000),
                "retry_reason": RetryReason (optional)
            }
            
        Returns:
            Dict[str, Any]: 생성된 실시간 티켓 요약 정보
        """
        ticket_data = input_data["ticket_data"]
        max_tokens = input_data.get("max_tokens", 1000)
        
        # 기존 캐싱 로직 그대로 재활용
        cache_key = self._generate_cache_key(ticket_data)
        if cache_key in self.summary_cache:
            logger.info(f"캐시에서 티켓 요약 반환 (ticket_id: {ticket_data.get('id')})")
            return self.summary_cache[cache_key]
        
        try:
            # Anthropic 요약기 초기화 (지연 로딩)
            if not self._anthropic_summarizer:
                self._anthropic_summarizer = AnthropicSummarizer()
            
            from core.llm.summarizer.utils.language import detect_content_language
            
            # 1. 티켓 컨텍스트 구성 (기존 로직 유지)
            ticket_content = self._build_ticket_context(ticket_data)
            
            # 2. 언어 감지
            content_language = detect_content_language(ticket_content)
            ui_language = "ko"  # 기본 UI 언어
            
            # 3. 재시도 컨텍스트 결정
            retry_context = input_data.get("retry_reason")
            if retry_context:
                retry_context = self._map_retry_reason_to_context(retry_context)
            
            # 4. Anthropic 실시간 요약 생성 (Constitutional AI + XML 구조화)
            summary = await self._anthropic_summarizer.generate_realtime_summary(
                content=ticket_content,
                subject=ticket_data.get('subject', ''),
                retry_context=retry_context,
                ui_language=ui_language
            )
            
            # 5. 실시간 요약 결과 구성
            result = {
                "summary": summary,
                "ticket_id": ticket_data.get('id'),
                "model_info": {
                    "provider": "anthropic_optimized",
                    "model": "realtime_summary",
                    "anthropic_techniques": [
                        "constitutional_ai",
                        "xml_structuring",
                        "realtime_optimization"
                    ]
                },
                "quality_metrics": {
                    "response_time": time.time(),
                    "content_language": content_language,
                    "ui_language": ui_language,
                    "retry_context": retry_context
                },
                "metadata": {
                    "company_name": ticket_data.get('company', ''),
                    "agent_name": ticket_data.get('agent_name', ''),
                    "priority": ticket_data.get('priority', ''),
                    "category": ticket_data.get('category', ''),
                    "status": ticket_data.get('status', ''),
                    "created_at": ticket_data.get('created_at', ''),
                    "updated_at": ticket_data.get('updated_at', '')
                }
            }
            
            # 캐시에 저장
            self.summary_cache[cache_key] = result
            
            logger.info(f"✅ Anthropic 실시간 요약 생성 완료 (ticket_id: {ticket_data.get('id')})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Anthropic 실시간 요약 생성 실패: {e}")
            
            # 폴백: 간단한 기본 요약 제공
            fallback_summary = self._generate_fallback_summary(ticket_data)
            
            result = {
                "summary": fallback_summary,
                "ticket_id": ticket_data.get('id'),
                "model_info": {
                    "provider": "fallback",
                    "model": "basic_summary",
                    "anthropic_techniques": []
                },
                "quality_metrics": {
                    "response_time": time.time(),
                    "error": str(e)
                },
                "metadata": {
                    "company_name": ticket_data.get('company', ''),
                    "priority": ticket_data.get('priority', ''),
                    "status": ticket_data.get('status', '')
                }
            }
            
            return result
    
    def _build_ticket_context(self, ticket_data: Dict[str, Any]) -> str:
        """티켓 컨텍스트 구성 (기존 로직 유지)"""
        context_parts = []
        
        # 티켓 기본 정보
        if ticket_data.get('subject'):
            context_parts.append(f"제목: {ticket_data['subject']}")
        
        if ticket_data.get('description'):
            context_parts.append(f"설명: {ticket_data['description']}")
        
        # 대화 내역
        if ticket_data.get('conversations'):
            context_parts.append("대화 내역:")
            for conv in ticket_data['conversations']:
                author = conv.get('author', '알 수 없음')
                content = conv.get('content', '')
                timestamp = conv.get('created_at', '')
                context_parts.append(f"[{timestamp}] {author}: {content}")
        
        # 메타데이터
        metadata_parts = []
        if ticket_data.get('priority'):
            metadata_parts.append(f"우선순위: {ticket_data['priority']}")
        if ticket_data.get('status'):
            metadata_parts.append(f"상태: {ticket_data['status']}")
        if ticket_data.get('category'):
            metadata_parts.append(f"카테고리: {ticket_data['category']}")
        if ticket_data.get('company'):
            metadata_parts.append(f"회사: {ticket_data['company']}")
        
        if metadata_parts:
            context_parts.append("메타데이터: " + ", ".join(metadata_parts))
        
        return "\n\n".join(context_parts)
    
    def _map_retry_reason_to_context(self, retry_reason: RetryReason) -> str:
        """재시도 이유를 컨텍스트로 매핑"""
        return self.retry_context_mapping.get(retry_reason, "initial")
    
    def _generate_cache_key(self, ticket_data: Dict[str, Any]) -> str:
        """캐시 키 생성"""
        key_data = {
            'id': ticket_data.get('id'),
            'updated_at': ticket_data.get('updated_at'),
            'subject': ticket_data.get('subject', '')[:100],  # 제목 일부만
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _generate_fallback_summary(self, ticket_data: Dict[str, Any]) -> str:
        """폴백 요약 생성"""
        subject = ticket_data.get('subject', '제목 없음')
        priority = ticket_data.get('priority', '보통')
        status = ticket_data.get('status', '확인 필요')
        company = ticket_data.get('company', '회사 정보 없음')
        
        return f"""
🚨 **긴급도**: {priority}
📋 **핵심 문제**: {subject}
👤 **고객 상태**: {company} - 확인 필요
⚡ **즉시 조치**: 수동 티켓 검토 필요
💼 **비즈니스 영향**: 평가 필요 (현재 상태: {status})

※ 시스템 오류로 인해 기본 요약을 제공합니다. 상세한 분석을 위해 수동 검토를 진행해주세요.
        """.strip()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        return {
            "cache_size": len(self.summary_cache),
            "cache_maxsize": self.summary_cache.maxsize,
            "cache_ttl": self.summary_cache.ttl,
            "cache_hits": getattr(self.summary_cache, 'hits', 0),
            "cache_misses": getattr(self.summary_cache, 'misses', 0)
        }
    
    def clear_cache(self):
        """캐시 클리어"""
        self.summary_cache.clear()
        logger.info("실시간 요약 캐시 클리어 완료")
    
    def get_anthropic_metrics(self) -> Dict[str, Any]:
        """Anthropic 요약기 메트릭 조회"""
        if self._anthropic_summarizer:
            return self._anthropic_summarizer.get_metrics()
        return {"error": "Anthropic 요약기가 초기화되지 않음"}


# 편의 함수들 (기존 인터페이스 호환성 유지)
def create_summarization_chain(cache_size: int = 1000, cache_ttl: int = 3600):
    """실시간 요약 체인 생성 (Anthropic 최적화)"""
    chain = SummarizationChain(cache_size=cache_size, cache_ttl=cache_ttl)
    return chain.build_chain()


async def run_realtime_summary(ticket_data: Dict[str, Any], 
                              max_tokens: int = 1000,
                              retry_reason: Optional[RetryReason] = None) -> Dict[str, Any]:
    """
    실시간 요약 실행 (Anthropic 기법 적용)
    
    Args:
        ticket_data: 티켓 데이터
        max_tokens: 최대 토큰 수
        retry_reason: 재시도 이유
        
    Returns:
        Dict[str, Any]: 요약 결과
    """
    chain = SummarizationChain()
    
    input_data = {
        "ticket_data": ticket_data,
        "max_tokens": max_tokens
    }
    
    if retry_reason:
        input_data["retry_reason"] = retry_reason
    
    return await chain.run_summary(input_data)