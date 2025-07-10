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
            # 긴 대화에 대해 토큰 예산 증가 (비용 vs 품질 트레이드오프)
            conversation_count = len(ticket_data.get("conversations", []))
            if conversation_count > 40:
                max_tokens = 4000  # 40개 초과: 4000 토큰
                model_preference = "gpt-4o-mini"  # 긴 컨텍스트에 강한 모델
            elif conversation_count > 20:
                max_tokens = 3000  # 20-40개: 3000 토큰  
                model_preference = "gpt-4o-mini"
            else:
                max_tokens = 2000  # 20개 이하: 기본
                model_preference = None  # 라우터 선택
                
            response = await self.llm_manager.generate(
                messages=messages,
                model=model_preference,  # 긴 대화용 모델 우선
                max_tokens=max_tokens,
                temperature=0.1
            )
            
            # 3. LLM 응답 파싱 (LLMResponse.content 속성 사용)
            response_content = response.content if hasattr(response, 'content') else str(response)
            analysis_result = self._parse_llm_analysis(response_content, ticket_data, ui_language)
            
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
                # 적응형 미리보기: 대화 수에 따라 동적 조정
                body_text = conv.get("body_text", "")
                if len(conversations) <= 20:
                    preview_length = 1200  # 적은 대화: 상세히
                elif len(conversations) <= 40:
                    preview_length = 800   # 중간 대화: 균형
                else:
                    preview_length = 500   # 많은 대화: 압축
                    
                body = body_text[:preview_length]
                conversation_summary += f"대화 {i+1}: {body}{'...' if len(body_text) > preview_length else ''}\n"
        
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
        
        # 통합 분석 프롬프트 (영어로 작성하여 LLM 성능 최적화)
        prompt = f"""You are an expert ticket analysis specialist. Please analyze the following ticket comprehensively.

===== TICKET INFORMATION =====
Title: {subject}
Description: {description}
{conversation_summary}
{attachment_summary}

===== ANALYSIS REQUEST =====
Please analyze the following 4 aspects simultaneously and respond in JSON format:

1. **Language Detection**: Detect the primary language of the ticket content (ko/en/ja/zh)
2. **Important Conversation Selection**: Select conversation indices that contain problem-solving processes (max 25 conversations)
3. **Relevant Attachments**: Select attachment indices that are actually helpful for problem resolution (max 3 attachments)
4. **High-Quality Summary**: Summary including problem situation, root cause analysis, resolution process, and key insights

Analysis Criteria:
- Language: Determine the main conversation language even if technical terms are mixed
- Important conversations: Focus on initial problem reporting + resolution process + final results, especially those containing resolution keywords like "solved", "completed", "fixed", "deployed", "resolved", "confirmed"
- Attachments: Prioritize logs, screenshots, configuration files, and other technically helpful items (select maximum 3 most relevant)
- Summary: Reflect chronological flow while focusing on the resolution process

Response Format (JSON):
{{
  "language": "ko",
  "important_conversations": [0, 1, 15, 16, 45, 46, 47, 48, 49],
  "relevant_attachments": [0, 2],
  "summary": {{
    "problem": "Problem situation summary",
    "cause": "Root cause analysis", 
    "resolution": "Resolution process and results",
    "insights": "Key insights and future reference points"
  }},
  "metadata": {{
    "total_conversations": {len(conversations)},
    "selected_conversations": 9,
    "confidence": 0.95
  }}
}}

IMPORTANT: Please write the summary content in the SAME LANGUAGE as the detected ticket language, not in the UI language. The UI language '{ui_language}' is only for section headers."""

        return prompt
    
    def _get_section_headers(self, ui_language: str) -> Dict[str, str]:
        """UI 언어에 따른 섹션 헤더 반환"""
        if ui_language == "ko":
            return {
                "problem": "🔍 **문제 현황**",
                "cause": "💡 **원인 분석**", 
                "resolution": "⚡ **해결 진행상황**",
                "insights": "🎯 **중요 인사이트**"
            }
        else:  # 기본값: 영어
            return {
                "problem": "🔍 **Problem Overview**",
                "cause": "💡 **Root Cause Analysis**",
                "resolution": "⚡ **Resolution Progress**", 
                "insights": "🎯 **Key Insights**"
            }

    def _parse_llm_analysis(self, llm_response: str, ticket_data: Dict[str, Any], ui_language: str = "ko") -> TicketAnalysis:
        """LLM 응답을 파싱하여 TicketAnalysis 객체 생성"""
        
        try:
            # JSON 응답 파싱
            analysis = json.loads(llm_response.strip())
            
            # 언어 추출
            language = analysis.get("language", "ko")
            
            # 중요 대화 인덱스 추출
            important_conversations = analysis.get("important_conversations", [])
            
            # 관련 첨부파일 추출 (최대 3개로 제한)
            relevant_attachment_indices = analysis.get("relevant_attachments", [])
            all_attachments = ticket_data.get("metadata", {}).get("all_attachments", [])
            relevant_attachments = []
            
            # 최대 3개만 선택
            for idx in relevant_attachment_indices[:3]:
                if 0 <= idx < len(all_attachments):
                    relevant_attachments.append(all_attachments[idx])
            
            # 요약 구성 (UI 언어에 따른 섹션 헤더 사용)
            summary_parts = analysis.get("summary", {})
            if isinstance(summary_parts, dict):
                headers = self._get_section_headers(ui_language)
                summary = f"""{headers['problem']}
{summary_parts.get('problem', 'No information available' if ui_language != 'ko' else '정보 없음')}

{headers['cause']}
{summary_parts.get('cause', 'Under analysis' if ui_language != 'ko' else '분석 중')}

{headers['resolution']}
{summary_parts.get('resolution', 'In progress' if ui_language != 'ko' else '진행 중')}

{headers['insights']}
{summary_parts.get('insights', 'Further analysis needed' if ui_language != 'ko' else '추가 분석 필요')}"""
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
            relevant_attachments=ticket_data.get("metadata", {}).get("all_attachments", [])[:3],
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