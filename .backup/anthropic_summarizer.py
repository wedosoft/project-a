"""
Anthropic 기법이 적용된 고급 요약기

이 모듈은 Constitutional AI, Chain-of-Thought, XML 구조화 등
Anthropic 프롬프트 엔지니어링 기법을 활용하여 고품질의 일관된 요약을 생성합니다.
품질 검증 시스템과 폴백 메커니즘을 포함하여 안정성을 보장합니다.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json

from .summarizer import CoreSummarizer
from ..prompt.anthropic_builder import AnthropicPromptBuilder
from ..quality.anthropic_validator import AnthropicQualityValidator
from ..config.anthropic_config import AnthropicConfig

logger = logging.getLogger(__name__)


class AnthropicSummarizer(CoreSummarizer):
    """Anthropic 프롬프트 엔지니어링 기법이 적용된 요약기"""
    
    def __init__(self, config: Optional[AnthropicConfig] = None):
        """
        Args:
            config: Anthropic 설정. None이면 환경변수에서 로드
        """
        super().__init__()
        
        # 설정 초기화
        self.config = config or AnthropicConfig.from_env()
        
        # Anthropic 컴포넌트 초기화
        self.anthropic_builder = AnthropicPromptBuilder()
        self.quality_validator = AnthropicQualityValidator()
        
        # 성능 메트릭
        self.metrics = {
            'total_requests': 0,
            'anthropic_requests': 0,
            'fallback_requests': 0,
            'quality_failures': 0,
            'avg_response_time': 0.0,
            'success_rate': 0.0
        }
        
        logger.debug(f"AnthropicSummarizer 초기화 완료 (활성화: {self.config.enabled})")
    
    async def generate_anthropic_summary(self,
                                       content: str,
                                       content_type: str,
                                       subject: str,
                                       metadata: Dict[str, Any],
                                       content_language: str = "ko",
                                       ui_language: str = "ko",
                                       max_retries: Optional[int] = None) -> str:
        """
        Anthropic 기법을 활용한 고품질 요약 생성
        
        Args:
            content: 요약할 내용
            content_type: 콘텐츠 타입 (ticket_view, ticket_similar 등)
            subject: 제목
            metadata: 메타데이터
            content_language: 콘텐츠 언어
            ui_language: UI 언어
            max_retries: 최대 재시도 횟수
            
        Returns:
            str: Anthropic 기법이 적용된 고품질 요약
        """
        start_time = time.time()
        self.metrics['total_requests'] += 1
        
        # 설정 확인
        if not self.config.enabled or content_type != "ticket_view":
            logger.debug(f"Anthropic 기법 비활성화 또는 지원하지 않는 타입: {content_type}")
            return await self._fallback_to_standard_summary(
                content, content_type, subject, metadata, content_language, ui_language
            )
        
        max_retries = max_retries or self.config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Anthropic 요약 생성 시도 {attempt + 1}/{max_retries + 1}")
                
                # 1. Constitutional AI 기반 시스템 프롬프트 생성
                system_prompt = self.anthropic_builder.build_constitutional_system_prompt(
                    template_name="anthropic_ticket_view",
                    content_language=content_language,
                    ui_language=ui_language,
                    context=metadata
                )
                
                # 2. XML 구조화된 사용자 프롬프트 생성
                user_prompt = self.anthropic_builder.build_xml_structured_user_prompt(
                    template_name="anthropic_ticket_view",
                    content=content,
                    subject=subject,
                    metadata=metadata,
                    content_language=content_language,
                    ui_language=ui_language
                )
                
                # 3. LLM 호출 (Chain-of-Thought 추론 활성화)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                # 높은 품질을 위한 모델 설정
                llm_response = await self._call_anthropic_llm(messages)
                
                if not llm_response.success:
                    logger.warning(f"LLM 호출 실패 (시도 {attempt + 1}): {llm_response.error}")
                    continue
                
                summary = llm_response.content.strip()
                
                # 4. Anthropic 기법 준수 검증
                validation_results = self.anthropic_builder.validate_anthropic_compliance(
                    summary, "anthropic_ticket_view"
                )
                
                quality_score = self.quality_validator.calculate_anthropic_quality_score(
                    summary, validation_results
                )
                
                # 5. 품질 기준 확인
                quality_threshold = self.anthropic_builder.get_quality_threshold("anthropic_ticket_view")
                
                if quality_score >= quality_threshold:
                    # 성공
                    self.metrics['anthropic_requests'] += 1
                    response_time = time.time() - start_time
                    self._update_metrics(response_time, True)
                    
                    logger.info(f"✅ Anthropic 고품질 요약 생성 성공 (점수: {quality_score:.2f}, 시간: {response_time:.2f}s)")
                    return summary
                else:
                    logger.warning(f"⚠️ 품질 점수 부족 (시도 {attempt + 1}/{max_retries + 1}): {quality_score:.2f} < {quality_threshold}")
                    self.metrics['quality_failures'] += 1
                    
                    if attempt == max_retries:
                        logger.error("❌ 최대 재시도 후에도 품질 기준 미달, 기존 방식으로 폴백")
                        break
                
            except Exception as e:
                logger.error(f"Anthropic 요약 생성 실패 (시도 {attempt + 1}): {e}")
                if attempt == max_retries:
                    break
                
                # 재시도 간격 적용
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        
        # 폴백: 기존 방식으로 요약 생성
        return await self._fallback_to_standard_summary(
            content, content_type, subject, metadata, content_language, ui_language
        )
    
    async def generate_realtime_summary(self,
                                      content: str,
                                      subject: str,
                                      retry_context: Optional[str] = None,
                                      ui_language: str = "ko") -> str:
        """
        실시간 요약 생성 (재시도 이유별 적응형)
        
        Args:
            content: 티켓 내용
            subject: 티켓 제목
            retry_context: 재시도 컨텍스트
            ui_language: UI 언어
            
        Returns:
            str: 실시간 요약
        """
        try:
            # 실시간 요약용 프롬프트 생성
            prompts = self.anthropic_builder.build_realtime_summary_prompt(
                content=content,
                subject=subject,
                retry_context=retry_context,
                ui_language=ui_language
            )
            
            messages = [
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ]
            
            # 빠른 응답을 위한 설정
            llm_response = await self._call_fast_llm(messages)
            
            if llm_response.success:
                return llm_response.content.strip()
            else:
                logger.error(f"실시간 요약 LLM 호출 실패: {llm_response.error}")
                return self._get_fallback_realtime_summary(subject)
                
        except Exception as e:
            logger.error(f"실시간 요약 생성 실패: {e}")
            return self._get_fallback_realtime_summary(subject)
    
    async def select_relevant_attachments(self,
                                        content: str,
                                        subject: str,
                                        attachments: List[Dict[str, Any]],
                                        metadata: Optional[Dict[str, Any]] = None,
                                        ui_language: str = "ko") -> Dict[str, Any]:
        """
        관련성 높은 첨부파일 선별
        
        Args:
            content: 티켓 내용
            subject: 티켓 제목
            attachments: 첨부파일 목록
            metadata: 메타데이터
            ui_language: UI 언어
            
        Returns:
            Dict[str, Any]: 선별 결과
        """
        try:
            if not attachments:
                return {
                    "selected_attachments": [],
                    "total_selected": 0,
                    "selection_summary": "첨부파일이 없습니다.",
                    "confidence_score": 1.0
                }
            
            # 첨부파일 선별용 프롬프트 생성
            prompts = self.anthropic_builder.build_attachment_selection_prompt(
                content=content,
                subject=subject,
                attachments=attachments,
                metadata=metadata,
                ui_language=ui_language
            )
            
            messages = [
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ]
            
            llm_response = await self._call_anthropic_llm(messages)
            
            if llm_response.success:
                # JSON 응답 파싱
                try:
                    result = json.loads(llm_response.content.strip())
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"첨부파일 선별 JSON 파싱 실패: {e}")
                    return self._get_fallback_attachment_selection(attachments)
            else:
                logger.error(f"첨부파일 선별 LLM 호출 실패: {llm_response.error}")
                return self._get_fallback_attachment_selection(attachments)
                
        except Exception as e:
            logger.error(f"첨부파일 선별 실패: {e}")
            return self._get_fallback_attachment_selection(attachments)
    
    async def analyze_ticket_comprehensively(self,
                                           ticket_data: Dict[str, Any],
                                           ui_language: str = "ko") -> Dict[str, Any]:
        """
        티켓 종합 분석
        
        Args:
            ticket_data: 티켓 전체 데이터
            ui_language: UI 언어
            
        Returns:
            Dict[str, Any]: 종합 분석 결과
        """
        try:
            # 종합 분석용 프롬프트 생성
            prompts = self.anthropic_builder.build_comprehensive_analysis_prompt(
                ticket_data=ticket_data,
                ui_language=ui_language
            )
            
            messages = [
                {"role": "system", "content": prompts['system']},
                {"role": "user", "content": prompts['user']}
            ]
            
            # 종합 분석을 위해 더 많은 토큰과 시간 허용
            llm_response = await self._call_comprehensive_llm(messages)
            
            if llm_response.success:
                try:
                    result = json.loads(llm_response.content.strip())
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"종합 분석 JSON 파싱 실패: {e}")
                    return self._get_fallback_comprehensive_analysis(ticket_data)
            else:
                logger.error(f"종합 분석 LLM 호출 실패: {llm_response.error}")
                return self._get_fallback_comprehensive_analysis(ticket_data)
                
        except Exception as e:
            logger.error(f"종합 분석 실패: {e}")
            return self._get_fallback_comprehensive_analysis(ticket_data)
    
    async def _call_anthropic_llm(self, messages: List[Dict[str, str]]):
        """Anthropic 최적화 LLM 호출"""
        try:
            return await self._get_manager().generate_for_use_case(
                messages=messages,
                use_case="anthropic_ticket_view",
                temperature=self.config.temperature,
                max_tokens=1500,
                model_provider=self.config.model_provider,
                model_name=self.config.model_name
            )
        except Exception as e:
            logger.error(f"Anthropic LLM 호출 실패: {e}")
            raise
    
    async def _call_fast_llm(self, messages: List[Dict[str, str]]):
        """빠른 응답용 LLM 호출"""
        try:
            return await self._get_manager().generate_for_use_case(
                messages=messages,
                use_case="realtime_summary",
                temperature=0.1,
                max_tokens=500,
                timeout=10
            )
        except Exception as e:
            logger.error(f"빠른 LLM 호출 실패: {e}")
            raise
    
    async def _call_comprehensive_llm(self, messages: List[Dict[str, str]]):
        """종합 분석용 LLM 호출"""
        try:
            return await self._get_manager().generate_for_use_case(
                messages=messages,
                use_case="comprehensive_analysis",
                temperature=0.2,
                max_tokens=3000,
                timeout=45
            )
        except Exception as e:
            logger.error(f"종합 분석 LLM 호출 실패: {e}")
            raise
    
    async def _fallback_to_standard_summary(self,
                                          content: str,
                                          content_type: str,
                                          subject: str,
                                          metadata: Dict[str, Any],
                                          content_language: str,
                                          ui_language: str) -> str:
        """기존 방식으로 폴백"""
        try:
            self.metrics['fallback_requests'] += 1
            logger.info("🔄 기존 요약 방식으로 폴백")
            
            return await super().generate_summary(
                content=content,
                content_type=content_type,
                subject=subject,
                metadata=metadata,
                ui_language=ui_language
            )
        except Exception as e:
            logger.error(f"폴백 요약 생성 실패: {e}")
            return f"요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _get_fallback_realtime_summary(self, subject: str) -> str:
        """실시간 요약 폴백"""
        return f"""
🚨 **긴급도**: 보통
📋 **핵심 문제**: {subject}
👤 **고객 상태**: 확인 필요
⚡ **즉시 조치**: 수동 티켓 검토 필요
💼 **비즈니스 영향**: 평가 필요
        """.strip()
    
    def _get_fallback_attachment_selection(self, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """첨부파일 선별 폴백"""
        # 간단한 휴리스틱으로 처음 3개 선택
        selected = attachments[:3] if len(attachments) > 3 else attachments
        
        return {
            "selected_attachments": [
                {
                    "filename": att.get('filename', ''),
                    "selection_reason": "기본 선별 규칙 적용",
                    "relevance_score": 0.5,
                    "priority": "medium"
                }
                for att in selected
            ],
            "total_selected": len(selected),
            "selection_summary": "기본 선별 규칙을 사용하여 첨부파일을 선별했습니다.",
            "confidence_score": 0.5
        }
    
    def _get_fallback_comprehensive_analysis(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """종합 분석 폴백"""
        return {
            "analysis_summary": {
                "ticket_id": ticket_data.get('ticket_id', ''),
                "analysis_timestamp": datetime.now().isoformat(),
                "overall_severity": "medium",
                "confidence_level": 0.5
            },
            "customer_analysis": {
                "customer_tier": "standard",
                "satisfaction_level": "neutral",
                "churn_risk": "low"
            },
            "technical_analysis": {
                "problem_category": "일반",
                "complexity_rating": "medium"
            },
            "business_analysis": {
                "business_priority": "medium",
                "escalation_required": False
            },
            "resolution_analysis": {
                "recommended_solution": "추가 조사 필요",
                "success_probability": 0.7
            },
            "action_plan": {
                "immediate_actions": [
                    {
                        "action": "수동 티켓 검토",
                        "responsible": "담당 상담원",
                        "priority": "medium"
                    }
                ]
            }
        }
    
    def _update_metrics(self, response_time: float, success: bool):
        """메트릭 업데이트"""
        # 평균 응답 시간 업데이트
        if self.metrics['total_requests'] > 1:
            self.metrics['avg_response_time'] = (
                (self.metrics['avg_response_time'] * (self.metrics['total_requests'] - 1) + response_time) / 
                self.metrics['total_requests']
            )
        else:
            self.metrics['avg_response_time'] = response_time
        
        # 성공률 업데이트
        if success:
            successful_requests = self.metrics['anthropic_requests']
            self.metrics['success_rate'] = successful_requests / self.metrics['total_requests']
        else:
            self.metrics['success_rate'] = (
                self.metrics['anthropic_requests'] / self.metrics['total_requests']
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        return {
            **self.metrics,
            "config": {
                "enabled": self.config.enabled,
                "quality_threshold": self.config.quality_threshold,
                "max_retries": self.config.max_retries,
                "model_provider": self.config.model_provider,
                "model_name": self.config.model_name
            }
        }
    
    def update_config(self, new_config: AnthropicConfig):
        """설정 업데이트"""
        self.config = new_config
        logger.info(f"AnthropicSummarizer 설정 업데이트: {new_config}")
    
    def reload_templates(self):
        """템플릿 다시 로드"""
        try:
            self.anthropic_builder.reload_templates()
            logger.info("AnthropicSummarizer 템플릿 다시 로드 완료")
        except Exception as e:
            logger.error(f"템플릿 다시 로드 실패: {e}")
    
    # 편의 메서드들
    async def generate_summary(self,
                             content: str,
                             content_type: str,
                             subject: str,
                             metadata: Dict[str, Any],
                             content_language: str = "ko",
                             ui_language: str = "ko") -> str:
        """
        기본 요약 생성 (Anthropic 기법 적용)
        
        이 메서드는 기존 CoreSummarizer의 인터페이스를 유지하면서
        Anthropic 기법을 적용합니다.
        """
        return await self.generate_anthropic_summary(
            content=content,
            content_type=content_type,
            subject=subject,
            metadata=metadata,
            content_language=content_language,
            ui_language=ui_language
        )