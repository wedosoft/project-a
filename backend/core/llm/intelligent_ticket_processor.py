"""
LLM 기반 통합 티켓 처리기

언어 감지, 첨부파일 선별, 대화 분석, 요약을 하나의 LLM 호출로 통합 처리
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TicketAnalysis:
    """티켓 분석 결과"""
    language: str
    important_conversation_indices: List[int]
    relevant_attachments: List[Dict[str, Any]]
    summary: str
    processing_metadata: Dict[str, Any]


class IntelligentTicketProcessor:
    """
    LLM 기반 통합 티켓 처리기
    
    단일 LLM 호출로 다음 작업들을 통합 처리:
    1. 언어 감지 (다국어 지원)
    2. 중요 대화 선별 (해결과정 포함)
    3. 관련 첨부파일 선별
    4. 고품질 티켓 요약 생성
    """
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
    
    async def process_ticket_intelligently(
        self, 
        ticket_data: Dict[str, Any], 
        ui_language: str = "ko"
    ) -> TicketAnalysis:
        """
        티켓을 지능적으로 통합 분석
        
        Args:
            ticket_data: 티켓 데이터 (대화, 첨부파일 포함)
            ui_language: UI 언어
            
        Returns:
            TicketAnalysis: 통합 분석 결과
        """
        try:
            # 1. 통합 분석 프롬프트 생성
            analysis_prompt = self._build_integrated_analysis_prompt(ticket_data, ui_language)
            
            # 2. 단일 LLM 호출로 모든 분석 수행
            logger.info(f"🧠 LLM 통합 분석 시작 - 티켓 ID: {ticket_data.get('id')}")
            
            # LLM Manager는 messages 형태를 기대함
            messages = [
                {"role": "user", "content": analysis_prompt}
            ]
            
            # Use-case에 따른 적절한 모델 선택 (LLM Manager의 라우팅 활용)
            response = await self.llm_manager.generate(
                messages=messages,
                model=None,  # 라우터가 최적 모델 선택
                max_tokens=2000,
                temperature=0.1
            )
            
            # 3. LLM 응답 파싱 (LLMResponse.content 속성 사용)
            response_content = response.content if hasattr(response, 'content') else str(response)
            analysis_result = self._parse_llm_analysis(response_content, ticket_data)
            
            logger.info(f"✅ LLM 통합 분석 완료 - 언어: {analysis_result.language}, "
                       f"중요 대화: {len(analysis_result.important_conversation_indices)}개, "
                       f"관련 첨부파일: {len(analysis_result.relevant_attachments)}개")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ LLM 통합 분석 실패: {e}")
            # 폴백: 기존 방식
            return await self._fallback_processing(ticket_data, ui_language)
    
    def _build_integrated_analysis_prompt(self, ticket_data: Dict[str, Any], ui_language: str) -> str:
        """통합 분석용 프롬프트 구성"""
        
        # 티켓 기본 정보
        subject = ticket_data.get("subject", "")
        description = ticket_data.get("description") or ticket_data.get("description_text", "")
        
        # 대화 정보
        conversations = ticket_data.get("conversations", [])
        conversation_summary = ""
        if conversations:
            conversation_summary = f"\n대화 목록 (총 {len(conversations)}개):\n"
            for i, conv in enumerate(conversations):
                body = conv.get("body_text", "")[:300]  # 첫 300자만
                conversation_summary += f"대화 {i+1}: {body}{'...' if len(conv.get('body_text', '')) > 300 else ''}\n"
        
        # 첨부파일 정보
        attachments = ticket_data.get("metadata", {}).get("all_attachments", [])
        attachment_summary = ""
        if attachments:
            attachment_summary = f"\n첨부파일 목록 (총 {len(attachments)}개):\n"
            for i, att in enumerate(attachments):
                name = att.get("name", "unknown")
                size_mb = round(att.get("size", 0) / (1024*1024), 2)
                content_type = att.get("content_type", "")
                attachment_summary += f"파일 {i+1}: {name} ({size_mb}MB, {content_type})\n"
        
        # 통합 분석 프롬프트
        prompt = f"""당신은 고급 티켓 분석 전문가입니다. 다음 티켓을 종합적으로 분석해주세요.

===== 티켓 정보 =====
제목: {subject}
설명: {description}
{conversation_summary}
{attachment_summary}

===== 분석 요청 =====
다음 4가지를 동시에 분석하여 JSON 형태로 응답해주세요:

1. **언어 감지**: 티켓의 주요 언어 (ko/en/ja/zh)
2. **중요 대화 선별**: 문제 해결과정이 포함된 중요한 대화들의 인덱스 (최대 15개)
3. **관련 첨부파일**: 문제 해결에 실제로 도움이 되는 첨부파일들의 인덱스
4. **고품질 요약**: 문제 상황, 원인 분석, 해결 과정, 중요 인사이트를 포함한 요약

분석 기준:
- 언어: 기술용어가 섞여있어도 주요 대화 언어 판단
- 중요 대화: 초기 문제 제기 + 해결 과정 + 최종 결과 중심
- 첨부파일: 로그, 스크린샷, 설정파일 등 기술적 도움이 되는 것 우선
- 요약: 시간순 흐름을 반영하되 해결 과정에 중점

응답 형식 (JSON):
{{
  "language": "ko",
  "important_conversations": [0, 1, 15, 16, 45, 46, 47, 48, 49],
  "relevant_attachments": [0, 2],
  "summary": {{
    "problem": "문제 상황 요약",
    "cause": "원인 분석",
    "resolution": "해결 과정 및 결과",
    "insights": "중요 인사이트 및 향후 참고사항"
  }},
  "metadata": {{
    "total_conversations": {len(conversations)},
    "selected_conversations": 9,
    "confidence": 0.95
  }}
}}

UI 언어가 '{ui_language}'이므로 요약은 해당 언어로 작성해주세요."""

        return prompt
    
    def _parse_llm_analysis(self, llm_response: str, ticket_data: Dict[str, Any]) -> TicketAnalysis:
        """LLM 응답을 파싱하여 TicketAnalysis 객체 생성"""
        
        try:
            # JSON 응답 파싱
            analysis = json.loads(llm_response.strip())
            
            # 언어 추출
            language = analysis.get("language", "ko")
            
            # 중요 대화 인덱스 추출
            important_conversations = analysis.get("important_conversations", [])
            
            # 관련 첨부파일 추출
            relevant_attachment_indices = analysis.get("relevant_attachments", [])
            all_attachments = ticket_data.get("metadata", {}).get("all_attachments", [])
            relevant_attachments = []
            
            for idx in relevant_attachment_indices:
                if 0 <= idx < len(all_attachments):
                    relevant_attachments.append(all_attachments[idx])
            
            # 요약 구성
            summary_parts = analysis.get("summary", {})
            if isinstance(summary_parts, dict):
                summary = f"""🔍 **문제 현황**
{summary_parts.get('problem', '정보 없음')}

💡 **원인 분석**
{summary_parts.get('cause', '분석 중')}

⚡ **해결 진행상황**
{summary_parts.get('resolution', '진행 중')}

🎯 **중요 인사이트**
{summary_parts.get('insights', '추가 분석 필요')}"""
            else:
                summary = str(summary_parts)
            
            # 메타데이터
            metadata = analysis.get("metadata", {})
            
            return TicketAnalysis(
                language=language,
                important_conversation_indices=important_conversations,
                relevant_attachments=relevant_attachments,
                summary=summary,
                processing_metadata=metadata
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM 응답 JSON 파싱 실패: {e}")
            # 텍스트 기반 폴백
            return self._parse_text_fallback(llm_response, ticket_data)
        
        except Exception as e:
            logger.error(f"LLM 응답 파싱 중 오류: {e}")
            raise
    
    def _parse_text_fallback(self, llm_response: str, ticket_data: Dict[str, Any]) -> TicketAnalysis:
        """JSON 파싱 실패 시 텍스트 기반 폴백"""
        
        # 기본 설정
        conversations = ticket_data.get("conversations", [])
        total_conversations = len(conversations)
        
        # 후반 대화 중심으로 선별 (기존 로직)
        if total_conversations <= 15:
            important_indices = list(range(total_conversations))
        else:
            # 초반 3개 + 후반 12개
            important_indices = (
                list(range(min(3, total_conversations))) +
                list(range(max(0, total_conversations - 12), total_conversations))
            )
            important_indices = sorted(set(important_indices))
        
        return TicketAnalysis(
            language="ko",  # 기본값
            important_conversation_indices=important_indices,
            relevant_attachments=ticket_data.get("metadata", {}).get("all_attachments", [])[:3],  # 처음 3개
            summary=llm_response,  # LLM 응답을 그대로 요약으로 사용
            processing_metadata={"fallback": True, "total_conversations": total_conversations}
        )
    
    async def _fallback_processing(self, ticket_data: Dict[str, Any], ui_language: str) -> TicketAnalysis:
        """LLM 통합 처리 실패 시 기존 방식으로 폴백"""
        
        logger.warning("LLM 통합 처리 실패, 기존 방식으로 폴백")
        
        # 기존 언어 감지
        from .summarizer.utils.language import detect_content_language
        content = ticket_data.get("description", "")
        language = detect_content_language(content, ui_language)
        
        # 기존 대화 선별 (후반 중심)
        conversations = ticket_data.get("conversations", [])
        total_conversations = len(conversations)
        
        if total_conversations <= 10:
            important_indices = list(range(total_conversations))
        else:
            important_indices = list(range(max(0, total_conversations - 10), total_conversations))
        
        # 기존 요약 생성
        try:
            from .summarizer.core.summarizer import CoreSummarizer
            summarizer = CoreSummarizer()
            summary = await summarizer.generate_summary(
                content=content,
                content_type="ticket_view",
                subject=ticket_data.get("subject", ""),
                metadata=ticket_data.get("metadata", {}),
                ui_language=ui_language
            )
        except Exception as e:
            logger.error(f"폴백 요약 생성 실패: {e}")
            summary = "요약을 생성할 수 없습니다."
        
        return TicketAnalysis(
            language=language,
            important_conversation_indices=important_indices,
            relevant_attachments=ticket_data.get("metadata", {}).get("all_attachments", [])[:5],
            summary=summary,
            processing_metadata={"fallback": True, "method": "legacy"}
        )
    
    def get_optimized_ticket_content(
        self, 
        ticket_data: Dict[str, Any], 
        analysis: TicketAnalysis
    ) -> str:
        """분석 결과를 바탕으로 최적화된 티켓 콘텐츠 생성"""
        
        content_parts = []
        
        # 기본 정보
        if ticket_data.get("subject"):
            content_parts.append(f"제목: {ticket_data['subject']}")
        
        if ticket_data.get("description") or ticket_data.get("description_text"):
            desc = ticket_data.get("description_text") or ticket_data.get("description")
            content_parts.append(f"설명: {desc}")
        
        # LLM이 선별한 중요 대화들
        conversations = ticket_data.get("conversations", [])
        if conversations and analysis.important_conversation_indices:
            content_parts.append(f"중요 대화 ({len(analysis.important_conversation_indices)}개):")
            
            for idx in analysis.important_conversation_indices:
                if 0 <= idx < len(conversations):
                    conv = conversations[idx]
                    if conv.get("body_text"):
                        # LLM이 선별한 대화는 더 많은 내용 포함
                        body_text = conv["body_text"][:1000]  # 1000자까지
                        content_parts.append(f"대화 {idx+1}: {body_text}{'...' if len(conv['body_text']) > 1000 else ''}")
        
        return "\n".join(content_parts)


# 전역 인스턴스
_intelligent_processor = None


def get_intelligent_processor():
    """지능형 티켓 처리기 싱글톤 인스턴스 반환"""
    global _intelligent_processor
    if _intelligent_processor is None:
        from .manager import LLMManager
        llm_manager = LLMManager()
        _intelligent_processor = IntelligentTicketProcessor(llm_manager)
    return _intelligent_processor