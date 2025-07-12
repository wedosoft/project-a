"""
배치 LLM 요약 생성기

여러 티켓을 한 번의 LLM 호출로 요약하여 성능을 최적화합니다.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .models.base import LLMRequest

logger = logging.getLogger(__name__)


class BatchSummarizer:
    """배치 요약 생성 클래스"""
    
    def __init__(self, llm_client):
        """
        Args:
            llm_client: LLM 클라이언트 인스턴스
        """
        self.llm_client = llm_client
        
    async def generate_batch_summaries(
        self,
        tickets: List[Dict[str, Any]],
        ui_language: str = "ko",
        max_batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        여러 티켓을 배치로 요약합니다.
        
        Args:
            tickets: 티켓 목록
            ui_language: UI 언어 코드
            max_batch_size: 한 번에 처리할 최대 티켓 수
            
        Returns:
            요약이 포함된 티켓 목록
        """
        if not tickets:
            return []
            
        # 배치 크기로 나누기
        batches = [tickets[i:i + max_batch_size] for i in range(0, len(tickets), max_batch_size)]
        results = []
        
        for batch_idx, batch in enumerate(batches):
            logger.info(f"🎯 [배치 요약] {batch_idx + 1}/{len(batches)} 배치 처리 중 (티켓 {len(batch)}개)")
            
            try:
                batch_results = await self._process_batch(batch, ui_language)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"❌ [배치 요약] 배치 {batch_idx + 1} 처리 실패: {e}")
                # 실패한 배치는 개별 처리로 폴백
                for ticket in batch:
                    results.append(self._create_fallback_summary(ticket))
                    
        return results
    
    async def _process_batch(
        self,
        batch: List[Dict[str, Any]],
        ui_language: str
    ) -> List[Dict[str, Any]]:
        """단일 배치를 처리합니다"""
        
        # 배치 프롬프트 생성
        batch_prompt = self._create_batch_prompt(batch, ui_language)
        
        # LLM 호출
        try:
            # 프로바이더에 맞는 모델 선택
            model = "gpt-4o-mini"  # 기본값
            if hasattr(self.llm_client, 'provider_type'):
                provider_type = str(self.llm_client.provider_type)
                if 'anthropic' in provider_type.lower():
                    model = "claude-3-haiku-20240307"
                elif 'gemini' in provider_type.lower():
                    model = "gemini-1.5-flash"
            
            # LLMRequest 객체 생성
            request = LLMRequest(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(ui_language)
                    },
                    {
                        "role": "user",
                        "content": batch_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # generate 메서드 호출
            response = await self.llm_client.generate(request)
            
            # 응답 성공 여부 확인
            if not response.success:
                logger.error(f"LLM 응답 실패: {response.error}")
                raise Exception(f"LLM 응답 실패: {response.error}")
                
            logger.info(f"✅ [배치 요약] LLM 응답 성공 - 모델: {response.model}")
            
            # 응답 파싱
            content = response.content  # LLMResponse에서 content 직접 접근
            summaries = self._parse_batch_response(content, batch)
            
            return summaries
            
        except Exception as e:
            logger.error(f"LLM 배치 호출 실패: {e}")
            # 개별 폴백 요약 생성
            return [self._create_fallback_summary(ticket) for ticket in batch]
    
    def _create_batch_prompt(
        self,
        batch: List[Dict[str, Any]],
        ui_language: str
    ) -> str:
        """배치 처리용 프롬프트를 생성합니다"""
        
        language_map = {
            'ko': '한국어',
            'en': '영어',
            'ja': '일본어',
            'zh': '중국어'
        }
        target_language = language_map.get(ui_language, '한국어')
        
        prompt_parts = [
            f"다음 {len(batch)}개의 티켓을 각각 {target_language}로 요약해주세요.",
            "각 티켓에 대해 JSON 형식으로 응답해주세요.",
            "",
            "응답 형식:",
            "```json",
            "[",
            '  {',
            '    "ticket_id": "티켓ID",',
            '    "summary": "간결한 요약 (2-3문장)",',
            '    "key_points": ["핵심포인트1", "핵심포인트2"],',
            '    "status": "해결/진행중/대기",',
            '    "urgency": "높음/보통/낮음"',
            '  }',
            "]",
            "```",
            "",
            "티켓 목록:",
            ""
        ]
        
        # 각 티켓 정보 추가
        for i, ticket in enumerate(batch, 1):
            prompt_parts.append(f"=== 티켓 {i} (ID: {ticket.get('id', 'unknown')}) ===")
            prompt_parts.append(f"제목: {ticket.get('subject', '제목 없음')}")
            
            content = ticket.get('content', '')
            if len(content) > 1000:
                content = content[:1000] + "..."
            prompt_parts.append(f"내용: {content}")
            
            # 메타데이터 정보
            metadata = ticket.get('metadata', {})
            if metadata.get('created_at'):
                prompt_parts.append(f"생성일: {metadata['created_at']}")
            if metadata.get('priority'):
                prompt_parts.append(f"우선순위: {metadata['priority']}")
                
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def _get_system_prompt(self, ui_language: str) -> str:
        """시스템 프롬프트를 반환합니다"""
        
        if ui_language == 'ko':
            return """당신은 고객 지원 티켓을 분석하고 요약하는 전문가입니다.
각 티켓의 핵심 내용을 파악하고 간결하게 요약해주세요.
기술적 문제는 구체적으로, 일반 문의는 명확하게 설명해주세요."""
        else:
            return """You are an expert in analyzing and summarizing customer support tickets.
Identify the key content of each ticket and provide a concise summary.
Be specific about technical issues and clear about general inquiries."""
    
    def _parse_batch_response(
        self,
        content: str,
        original_batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """배치 응답을 파싱합니다"""
        
        try:
            # JSON 추출
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("JSON 배열을 찾을 수 없습니다")
                
            json_str = content[json_start:json_end]
            summaries = json.loads(json_str)
            
            # 원본 티켓과 매칭
            results = []
            summary_map = {s['ticket_id']: s for s in summaries if 'ticket_id' in s}
            
            for ticket in original_batch:
                ticket_id = str(ticket.get('id', ''))
                
                if ticket_id in summary_map:
                    summary_data = summary_map[ticket_id]
                    results.append({
                        **ticket,
                        'content': summary_data.get('summary', ticket.get('content', '')),
                        'summary_metadata': {
                            'key_points': summary_data.get('key_points', []),
                            'status': summary_data.get('status', '알 수 없음'),
                            'urgency': summary_data.get('urgency', '보통'),
                            'generated_at': datetime.now().isoformat()
                        }
                    })
                else:
                    # 매칭되지 않은 경우 폴백
                    results.append(self._create_fallback_summary(ticket))
                    
            return results
            
        except Exception as e:
            logger.error(f"배치 응답 파싱 실패: {e}")
            # 전체 폴백
            return [self._create_fallback_summary(ticket) for ticket in original_batch]
    
    def _create_fallback_summary(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """폴백 요약을 생성합니다 - 오류를 명확히 표시"""
        
        ticket_id = ticket.get('id', 'unknown')
        logger.error(f"❌ [요약 생성 실패] 티켓 {ticket_id} 요약 생성 실패")
        
        # 프로젝트 원칙: fallback시 기본값 사용하지 않고 오류를 명확히 표시
        return {
            **ticket,
            'content': f"[오류] 티켓 요약 생성에 실패했습니다. (티켓 ID: {ticket_id})",
            'summary_metadata': {
                'error': True,
                'error_message': 'LLM 요약 생성 실패',
                'generated_at': datetime.now().isoformat()
            }
        }