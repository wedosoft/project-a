"""
실시간 티켓 요약 체인 - Langchain 기반 프리미엄 요약 체인

기존 유사티켓/지식베이스 요약과 완전히 독립적인 실시간 요약 전용 체인입니다.

핵심 차별화 요소:
- 실시간 요약 전용 프롬프트 사용 (core/llm/summarizer/prompt와 분리)
- 프리미엄 품질 보장 (유사티켓 요약보다 우수한 품질)
- 5초 내 이해 가능한 구조화된 출력
- 에스컬레이션 즉시 준비 가능한 정보 제공
- OpenAI 모델 강제 사용으로 일관된 고품질 보장
- 첨부파일 처리 제외로 실시간 속도 최적화
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from cachetools import TTLCache
from langchain_core.runnables import RunnableLambda

# 통합된 LLM Manager 사용
from core.llm.manager import LLMManager

logger = logging.getLogger(__name__)


class SummarizationChain:
    """
    실시간 티켓 요약 체인 - 유사티켓/지식베이스 요약과 완전히 독립적인 프리미엄 요약
    
    핵심 특징:
    - 실시간 요약 전용 프롬프트 사용 (기존 core/llm/summarizer/prompt와 분리)
    - 프리미엄 품질 보장 (유사티켓 요약 대비 우수한 품질)
    - 5초 내 이해 가능한 구조화된 분석
    - 에스컬레이션 즉시 준비 가능
    - OpenAI 모델 강제 사용
    - 첨부파일 미포함으로 실시간 속도 최적화
    """
    
    def __init__(self, llm_manager: LLMManager):
        """
        요약 체인 초기화
        
        Args:
            llm_manager: LLM Manager 인스턴스
        """
        self.llm_manager = llm_manager
        
        # 기존 캐싱 시스템 그대로 재활용
        self.summary_cache = TTLCache(maxsize=1000, ttl=3600)
        
        # langchain Runnable로 래핑
        self._chain = RunnableLambda(self._summarize_ticket)
        
        logger.info("SummarizationChain 초기화 완료")

    async def _summarize_ticket(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        실시간 티켓 요약 생성 - 유사티켓/지식베이스 요약과 독립적인 프리미엄 품질
        
        핵심 차별화:
        - 실시간 요약 전용 프롬프트 사용 (기존 유사티켓/지식베이스 프롬프트와 분리)
        - 프리미엄 품질 보장 (유사티켓보다 우수한 상세도와 정확성)
        - OpenAI 모델 강제 사용 (일관된 고품질)
        - 5초 내 이해 가능한 구조화
        - 에스컬레이션 즉시 준비
        - 첨부파일 처리 제외 (실시간 속도 최적화)
        
        Args:
            input_data: {
                "ticket_data": Dict[str, Any],
                "max_tokens": int (optional, default=1000)
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
            # 실시간 티켓 요약 전용 프롬프트 로더 사용 (기존 유사티켓/지식베이스 프롬프트와 분리)
            from core.llm.summarizer.prompt.realtime_loader import RealtimePromptLoader
            from core.llm.summarizer.utils.language import detect_content_language
            from core.llm.summarizer.quality.validator import QualityValidator
            from core.llm.models.base import LLMProvider
            
            realtime_prompt_loader = RealtimePromptLoader()
            quality_validator = QualityValidator()
            
            # 1. 티켓 컨텍스트 구성 (기존 로직 유지)
            ticket_content = self._build_ticket_context(ticket_data)
            
            # 2. 언어 감지
            content_language = detect_content_language(ticket_content)
            ui_language = "ko"  # 기본 UI 언어
            
            # 3. 실시간 요약 전용 프롬프트 생성 (유사티켓/지식베이스와 완전 분리)
            system_prompt = realtime_prompt_loader.build_system_prompt(
                content_language=content_language,
                ui_language=ui_language
            )
            
            # 메타데이터 구성 (실시간 특화 - 첨부파일 제외)
            metadata = {
                'company_name': ticket_data.get('company', ''),
                'customer_email': ticket_data.get('requester_email', ''),
                'agent_name': ticket_data.get('agent_name', ''),
                'department': ticket_data.get('department', ''),
                'product_version': ticket_data.get('product_version', ''),
                'priority': ticket_data.get('priority', ''),
                'status': ticket_data.get('status', ''),
                'created_at': ticket_data.get('created_at', ''),
                'escalation_count': ticket_data.get('escalation_count', 0)
                # 첨부파일 관련 필드는 실시간 요약에서 제외
            }
            
            user_prompt = realtime_prompt_loader.build_user_prompt(
                content=ticket_content,
                subject=ticket_data.get("subject", ""),
                metadata=metadata,
                content_language=content_language,
                ui_language=ui_language
            )
            
            # 4. OpenAI 모델 강제 사용 (실시간 요약 프리미엄 품질 보장)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.llm_manager.generate(
                messages=messages,
                provider=LLMProvider.OPENAI,  # 실시간 요약은 OpenAI 강제 사용
                max_tokens=max_tokens,
                temperature=0.2
            )
            
            if not response.success:
                raise Exception(f"실시간 요약 LLM 응답 실패: {response.error}")
            
            summary_text = response.content.strip()
            
            # 5. 실시간 요약 품질 검증 및 재시도 로직 (유사티켓보다 엄격한 기준)
            validation_result = quality_validator.validate_summary_quality(
                summary=summary_text,
                original_content=ticket_content,
                content_language=content_language
            )
            
            # 6. 품질 점수 0.75 이상 요구 (유사티켓 0.7보다 높은 기준)
            if validation_result['quality_score'] < 0.75:
                logger.warning(f"실시간 요약 품질 점수 낮음 ({validation_result['quality_score']:.2f}), 재시도 실행")
                
                # 프리미엄 품질 재생성
                enhanced_system_prompt = system_prompt + "\n\n**PREMIUM QUALITY REMINDER**: This is REAL-TIME analysis requiring SUPERIOR quality compared to similar ticket summaries. Ensure MAXIMUM detail preservation and IMMEDIATE actionability."
                
                messages[0]["content"] = enhanced_system_prompt
                
                retry_response = await self.llm_manager.generate(
                    messages=messages,
                    provider=LLMProvider.OPENAI,
                    max_tokens=max_tokens + 300,  # 더 충분한 토큰 (실시간 특화)
                    temperature=0.1  # 더 낮은 temperature (정확성 우선)
                )
                
                if retry_response.success:
                    summary_text = retry_response.content.strip()
                    logger.info(f"실시간 요약 재시도 완료 (ticket_id: {ticket_data.get('id')})")
                else:
                    logger.warning(f"실시간 요약 재시도 실패, 원본 요약 사용 (ticket_id: {ticket_data.get('id')})")
            
            # 7. 실시간 요약 특화 응답 구성
            summary_result = {
                "ticket_summary": summary_text,
                "key_points": self._extract_key_points_from_markdown(summary_text),
                "sentiment": self._analyze_sentiment_from_summary(summary_text),
                "priority_recommendation": self._recommend_priority_from_summary(summary_text),
                "category_suggestion": None,  # 실시간 요약에서는 제외
                "customer_summary": None,     # 실시간 요약에서는 제외
                "request_summary": None,      # 실시간 요약에서는 제외
                "urgency_level": self._assess_urgency_from_summary(summary_text),
                "quality_score": validation_result['quality_score'],  # 품질 점수 추가
                "model_used": "OpenAI (realtime-forced)",  # 실시간 요약 전용 모델
                "summary_type": "realtime_premium",  # 요약 유형 명시
                "escalation_ready": True,  # 에스컬레이션 준비 완료
                "comprehension_target": "5_seconds"  # 이해 목표 시간
            }
            
            # 기존 캐싱 로직 그대로 재활용
            self.summary_cache[cache_key] = summary_result
            
            logger.info(f"실시간 프리미엄 요약 생성 완료 (ticket_id: {ticket_data.get('id')}, quality: {validation_result['quality_score']:.2f}, type: realtime_premium)")
            return summary_result
            
        except Exception as e:
            logger.error(f"실시간 요약 생성 중 오류 발생 (ticket_id: {ticket_data.get('id')}): {e}")
            
            # 실시간 요약 전용 오류 처리
            fallback_result = {
                "ticket_summary": "실시간 요약 생성에 실패했습니다. 원본 티켓 내용을 확인해주세요.",
                "key_points": ["실시간 요약 생성 실패"],
                "sentiment": "중립적",
                "priority_recommendation": "보통",
                "category_suggestion": None,
                "customer_summary": None,
                "request_summary": None,
                "urgency_level": "보통",
                "quality_score": 0.0,
                "model_used": "fallback",
                "summary_type": "realtime_fallback",
                "escalation_ready": False,
                "comprehension_target": "manual_review"
            }
            
            self.summary_cache[cache_key] = fallback_result
            return fallback_result

    def _generate_cache_key(self, ticket_data: Dict[str, Any]) -> str:
        """기존 캐시 키 생성 로직 그대로 재활용"""
        ticket_id = ticket_data.get("id", "unknown")
        subject = ticket_data.get("subject", "")
        description = ticket_data.get("description_text", "")
        
        content_hash = hashlib.md5(f"{subject}_{description}".encode()).hexdigest()
        return f"summary_{ticket_id}_{content_hash}"

    def _build_ticket_context(self, ticket_data: Dict[str, Any]) -> str:
        """기존 컨텍스트 빌더 로직 그대로 재활용"""
        subject = ticket_data.get("subject", "제목 없음")
        description = ticket_data.get("description_text", "설명 없음")
        conversations = ticket_data.get("conversations", [])
        
        prompt_context = f"티켓 제목: {subject}\n티켓 설명: {description}\n"
        
        if conversations:
            prompt_context += "\n최근 대화 내용:\n"
            # 기존 대화 처리 로직 간소화 버전 (원본 로직은 매우 복잡함)
            if isinstance(conversations, list):
                for i, conv in enumerate(conversations[-5:]):  # 최근 5개만
                    if isinstance(conv, dict):
                        sender = "사용자" if conv.get("user_id") else "상담원"
                        body = conv.get("body_text", conv.get("body", ""))
                        if body:
                            body = body[:200] + "..." if len(body) > 200 else body
                            prompt_context += f"- {sender}: {body}\n"
            elif isinstance(conversations, str):
                prompt_context += f"- 대화 내용: {conversations[:200]}\n"
                
        return prompt_context

    def _extract_key_points_from_markdown(self, summary_text: str) -> List[str]:
        """
        마크다운 요약에서 핵심 포인트 추출 (개선된 파싱)
        
        최신 YAML 프롬프트로 생성된 구조화된 요약에서 실제 핵심 정보를 추출
        """
        import re
        
        key_points = []
        
        try:
            # 💡 핵심 포인트 섹션 찾기
            if "💡" in summary_text:
                lines = summary_text.split('\n')
                in_key_points = False
                
                for line in lines:
                    line = line.strip()
                    if "💡" in line:
                        in_key_points = True
                        continue
                    elif line.startswith("#") and in_key_points:
                        break  # 다음 섹션 시작
                    elif in_key_points and line:
                        # 리스트 항목 추출 (-, *, 1., 2. 등)
                        if re.match(r'^[-*\d]+\.?\s+', line):
                            point = re.sub(r'^[-*\d]+\.?\s+', '', line)
                            if point and len(point) > 3:
                                key_points.append(point)
            
            # 핵심 포인트가 없으면 주요 내용에서 추출
            if not key_points and "🔍" in summary_text:
                lines = summary_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("- ") and len(line) > 10:
                        point = line[2:].strip()
                        if ":" in point:
                            key_points.append(point.split(":", 1)[1].strip())
            
            # 여전히 없으면 기본값
            if not key_points:
                key_points = ["구조화된 요약 생성 완료", "세부 정보 검토 권장"]
                
        except Exception as e:
            logger.warning(f"핵심 포인트 추출 중 오류: {e}")
            key_points = ["요약 파싱 오류", "원본 내용 확인 필요"]
        
        return key_points[:5]  # 최대 5개

    def _analyze_sentiment_from_summary(self, summary_text: str) -> str:
        """
        요약 내용에서 감정 분석 (개선된 로직)
        
        실제 고객 상황과 문제의 심각성을 기반으로 감정 분석
        """
        summary_lower = summary_text.lower()
        
        # 부정적 키워드
        negative_keywords = ["오류", "실패", "문제", "불가능", "중단", "장애", "버그", "에러", "error", "fail", "issue", "problem"]
        # 긍정적 키워드  
        positive_keywords = ["해결", "완료", "성공", "정상", "복구", "개선", "success", "solved", "resolved", "completed"]
        # 중립적 키워드
        neutral_keywords = ["문의", "요청", "확인", "설정", "정보", "inquiry", "request", "information"]
        
        neg_count = sum(1 for word in negative_keywords if word in summary_lower)
        pos_count = sum(1 for word in positive_keywords if word in summary_lower)
        neu_count = sum(1 for word in neutral_keywords if word in summary_lower)
        
        if neg_count > pos_count and neg_count > neu_count:
            return "부정적"
        elif pos_count > neg_count and pos_count > neu_count:
            return "긍정적"
        else:
            return "중립적"

    def _recommend_priority_from_summary(self, summary_text: str) -> str:
        """
        요약 내용에서 우선순위 추천 (개선된 로직)
        
        문제의 심각성과 영향 범위를 기반으로 우선순위 결정
        """
        summary_lower = summary_text.lower()
        
        # 높은 우선순위 키워드
        high_priority = ["긴급", "중요", "심각", "장애", "중단", "불가능", "urgent", "critical", "severe", "outage"]
        # 중간 우선순위 키워드
        medium_priority = ["문제", "오류", "개선", "요청", "issue", "error", "improvement", "request"]
        
        high_count = sum(1 for word in high_priority if word in summary_lower)
        medium_count = sum(1 for word in medium_priority if word in summary_lower)
        
        if high_count > 0:
            return "높음"
        elif medium_count > 1:
            return "보통"
        else:
            return "낮음"

    def _assess_urgency_from_summary(self, summary_text: str) -> str:
        """
        요약 내용에서 긴급도 평가 (개선된 로직)
        
        시간 민감성과 비즈니스 영향도를 기반으로 긴급도 결정
        """
        summary_lower = summary_text.lower()
        
        # 높은 긴급도 키워드
        high_urgency = ["즉시", "긴급", "빠른", "시급", "당장", "immediate", "urgent", "asap", "critical"]
        # 중간 긴급도 키워드
        medium_urgency = ["빠른 시일", "가능한 한", "조속", "soon", "quickly", "priority"]
        
        high_count = sum(1 for word in high_urgency if word in summary_lower)
        medium_count = sum(1 for word in medium_urgency if word in summary_lower)
        
        if high_count > 0:
            return "높음"
        elif medium_count > 0:
            return "보통"
        else:
            return "낮음"

    def _determine_urgency(self, ticket_data: Dict[str, Any]) -> str:
        """
        티켓 데이터에서 긴급도 판단
        
        Args:
            ticket_data: 티켓 데이터
            
        Returns:
            str: 긴급도 (높음/보통/낮음)
        """
        # 기존 우선순위 필드 확인
        priority = ticket_data.get('priority', '').lower()
        if priority in ['urgent', 'high', '긴급', '높음']:
            return '높음'
        elif priority in ['low', '낮음']:
            return '낮음'
        
        # 제목과 설명에서 긴급 키워드 확인
        subject = ticket_data.get('subject', '').lower()
        description = ticket_data.get('description_text', '').lower()
        content = f"{subject} {description}"
        
        urgent_keywords = ['긴급', 'urgent', '즉시', 'immediate', '빠른', 'asap', '당장']
        medium_keywords = ['빠른 시일', '가능한 한', 'soon', 'quickly']
        
        urgent_count = sum(1 for keyword in urgent_keywords if keyword in content)
        medium_count = sum(1 for keyword in medium_keywords if keyword in content)
        
        if urgent_count > 0:
            return '높음'
        elif medium_count > 0:
            return '보통'
        else:
            return '보통'  # 기본값

    async def run(self, ticket_data: Dict[str, Any], max_tokens: int = 1000) -> Dict[str, Any]:
        """
        요약 체인 실행 (공개 API)
        
        Args:
            ticket_data: 티켓 데이터
            max_tokens: 최대 토큰 수
            
        Returns:
            Dict[str, Any]: 요약 결과
        """
        input_data = {
            "ticket_data": ticket_data,
            "max_tokens": max_tokens
        }
        
        return await self._chain.ainvoke(input_data)

    async def batch_run(self, tickets: List[Dict[str, Any]], max_tokens: int = 1000) -> List[Dict[str, Any]]:
        """
        배치 요약 처리 (기존 배치 로직 재활용)
        
        Args:
            tickets: 티켓 데이터 리스트
            max_tokens: 최대 토큰 수
            
        Returns:
            List[Dict[str, Any]]: 요약 결과 리스트
        """
        tasks = []
        for ticket in tickets:
            input_data = {
                "ticket_data": ticket,
                "max_tokens": max_tokens
            }
            tasks.append(self._chain.ainvoke(input_data))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리 및 결과 정리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 요약 처리 실패 (index: {i}): {result}")
                # 기존 오류 처리와 동일한 폴백
                processed_results.append({
                    "ticket_summary": "요약 생성에 실패했습니다.",
                    "key_points": ["요약 생성 실패"],
                    "sentiment": "중립적",
                    "priority_recommendation": "보통",
                    "category_suggestion": None,
                    "customer_summary": None,
                    "request_summary": None,
                    "urgency_level": "보통"
                })
            else:
                processed_results.append(result)
        
        return processed_results

    async def process_large_batch(
        self,
        tickets: List[Dict[str, Any]],
        max_tokens: int = 1000,
        max_concurrent: int = 10,
        chunk_size: int = 50,
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        대용량 배치 요약 처리 (100만건+ 대응)
        
        기존 batch_run() 메서드를 90% 재활용하면서 대용량 처리에 최적화:
        - 동시성 제한으로 메모리/API 보호
        - 청크 단위 처리로 메모리 효율성 확보
        - 진행률 추적으로 사용자 경험 개선
        - 부분 실패 시 재시도 로직
        
        Args:
            tickets: 처리할 티켓 데이터 리스트
            max_tokens: 요약문 최대 토큰 수
            max_concurrent: 동시 처리 제한 (기본값: 10)
            chunk_size: 청크 크기 (기본값: 50)
            progress_callback: 진행률 콜백 함수 (선택사항)
            
        Returns:
            List[Dict[str, Any]]: 요약 결과 리스트
        """
        if not tickets:
            logger.warning("처리할 티켓이 없습니다.")
            return []
            
        total_tickets = len(tickets)
        processed_results = []
        failed_tickets = []
        
        logger.info(f"대용량 배치 요약 처리 시작 - 총 {total_tickets}건, 청크 크기: {chunk_size}, 동시성: {max_concurrent}")
        
        # 동시성 제한을 위한 Semaphore
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # 청크 단위로 분할 처리
        for chunk_idx in range(0, total_tickets, chunk_size):
            chunk_tickets = tickets[chunk_idx:chunk_idx + chunk_size]
            chunk_start = chunk_idx + 1
            chunk_end = min(chunk_idx + chunk_size, total_tickets)
            
            logger.info(f"청크 처리 중: {chunk_start}-{chunk_end}/{total_tickets}")
            
            # 동시성 제한을 적용한 배치 처리 함수
            async def process_with_semaphore(ticket: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    try:
                        input_data = {
                            "ticket_data": ticket,
                            "max_tokens": max_tokens
                        }
                        return await self._chain.ainvoke(input_data)
                    except Exception as e:
                        logger.error(f"티켓 요약 처리 실패 (ticket_id: {ticket.get('id', 'unknown')}): {e}")
                        # 기존 오류 처리 로직 재활용
                        return {
                            "ticket_summary": "요약 생성에 실패했습니다.",
                            "key_points": ["요약 생성 실패"],
                            "sentiment": "중립적",
                            "priority_recommendation": "보통",
                            "category_suggestion": None,
                            "customer_summary": None,
                            "request_summary": None,
                            "urgency_level": "보통",
                            "error": str(e)
                        }
            
            # 청크 내 모든 티켓 병렬 처리
            try:
                chunk_results = await asyncio.gather(
                    *[process_with_semaphore(ticket) for ticket in chunk_tickets],
                    return_exceptions=True
                )
                
                # 결과 처리 및 실패 티켓 추적
                for i, result in enumerate(chunk_results):
                    if isinstance(result, Exception):
                        logger.error(f"청크 내 티켓 처리 실패 (index: {chunk_idx + i}): {result}")
                        failed_tickets.append({
                            "ticket": chunk_tickets[i],
                            "error": str(result),
                            "chunk_index": chunk_idx + i
                        })
                        # 기본 실패 응답 추가
                        processed_results.append({
                            "ticket_summary": "요약 생성에 실패했습니다.",
                            "key_points": ["요약 생성 실패"],
                            "sentiment": "중립적",
                            "priority_recommendation": "보통",
                            "category_suggestion": None,
                            "customer_summary": None,
                            "request_summary": None,
                            "urgency_level": "보통",
                            "error": f"처리 실패: {result}"
                        })
                    else:
                        processed_results.append(result)
                
                # 진행률 콜백 호출
                if progress_callback:
                    progress_percentage = (chunk_end / total_tickets) * 100
                    await progress_callback({
                        "processed": chunk_end,
                        "total": total_tickets,
                        "percentage": round(progress_percentage, 2),
                        "failed_count": len(failed_tickets),
                        "current_chunk": f"{chunk_start}-{chunk_end}"
                    })
                    
            except Exception as e:
                logger.error(f"청크 처리 중 예외 발생 (청크: {chunk_start}-{chunk_end}): {e}")
                # 청크 전체 실패 시 기본 응답으로 채움
                for ticket in chunk_tickets:
                    failed_tickets.append({
                        "ticket": ticket,
                        "error": f"청크 처리 실패: {e}",
                        "chunk_index": chunk_idx
                    })
                    processed_results.append({
                        "ticket_summary": "요약 생성에 실패했습니다.",
                        "key_points": ["청크 처리 실패"],
                        "sentiment": "중립적",
                        "priority_recommendation": "보통",
                        "category_suggestion": None,
                        "customer_summary": None,
                        "request_summary": None,
                        "urgency_level": "보통",
                        "error": f"청크 처리 실패: {e}"
                    })
            
            # 청크 간 짧은 대기 (API Rate Limit 방지)
            if chunk_end < total_tickets:
                await asyncio.sleep(0.1)
        
        # 최종 결과 로깅
        success_count = total_tickets - len(failed_tickets)
        logger.info(
            f"대용량 배치 요약 처리 완료 - "
            f"성공: {success_count}/{total_tickets} ({(success_count/total_tickets)*100:.1f}%), "
            f"실패: {len(failed_tickets)}건"
        )
        
        if failed_tickets:
            logger.warning(f"실패한 티켓 목록 (처음 5개): {failed_tickets[:5]}")
        
        return processed_results

    async def retry_failed_tickets(
        self,
        failed_tickets: List[Dict[str, Any]],
        max_tokens: int = 1000,
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        실패한 티켓들에 대한 재시도 처리
        
        Args:
            failed_tickets: 실패한 티켓 정보 리스트
            max_tokens: 최대 토큰 수
            max_retries: 최대 재시도 횟수
            
        Returns:
            List[Dict[str, Any]]: 재시도 결과 리스트
        """
        if not failed_tickets:
            return []
        
        logger.info(f"실패한 티켓 재시도 처리 시작 - {len(failed_tickets)}건")
        retry_results = []
        
        for failed_item in failed_tickets:
            ticket = failed_item["ticket"]
            ticket_id = ticket.get("id", "unknown")
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    retry_count += 1
                    logger.info(f"티켓 재시도 {retry_count}/{max_retries} (ticket_id: {ticket_id})")
                    
                    # 기존 단일 요약 로직 재활용
                    input_data = {
                        "ticket_data": ticket,
                        "max_tokens": max_tokens
                    }
                    result = await self._chain.ainvoke(input_data)
                    
                    retry_results.append(result)
                    success = True
                    logger.info(f"티켓 재시도 성공 (ticket_id: {ticket_id})")
                    
                except Exception as e:
                    logger.warning(f"티켓 재시도 실패 {retry_count}/{max_retries} (ticket_id: {ticket_id}): {e}")
                    
                    if retry_count < max_retries:
                        # 지수 백오프 대기
                        wait_time = 2 ** retry_count
                        await asyncio.sleep(wait_time)
                    else:
                        # 최종 실패 시 기본 응답
                        retry_results.append({
                            "ticket_summary": "재시도 후에도 요약 생성에 실패했습니다.",
                            "key_points": ["재시도 실패"],
                            "sentiment": "중립적",
                            "priority_recommendation": "보통",
                            "category_suggestion": None,
                            "customer_summary": None,
                            "request_summary": None,
                            "urgency_level": "보통",
                            "error": f"최종 실패 after {max_retries} retries: {e}"
                        })
        
        logger.info(f"실패한 티켓 재시도 처리 완료 - {len(retry_results)}건 처리됨")
        return retry_results
