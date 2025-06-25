"""
LLM 기반 첨부파일 선별기 - 의미적 관련성 기반 지능형 선별

이 모듈의 핵심:
- LLM이 직접 첨부파일의 관련성 판단
- 다국어 의미적 이해
- 맥락 기반 선별 로직
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ...manager import get_llm_manager
from ...models.base import LLMProvider

logger = logging.getLogger(__name__)


class LLMAttachmentSelector:
    """LLM을 활용한 지능형 첨부파일 선별기"""

    def __init__(self):
        self.llm_manager = get_llm_manager()
        self.max_selected = 3
        self.prompt_version = "v1.0"

    async def select_relevant_attachments(
        self,
        attachments: List[Dict[str, Any]],
        content: str,
        subject: str = ""
    ) -> List[Dict[str, Any]]:
        """
        LLM을 사용하여 관련성 높은 첨부파일 선별

        Args:
            attachments: 전체 첨부파일 리스트
            content: 티켓 내용 (통합 내용)
            subject: 티켓 제목

        Returns:
            선별된 첨부파일 리스트 (최대 3개)
        """
        if not attachments:
            logger.debug("첨부파일이 없어 빈 리스트 반환")
            return []

        if len(attachments) <= self.max_selected:
            logger.info(f"첨부파일 {len(attachments)}개가 최대 선별 개수 이하이므로 모두 반환")
            return attachments

        logger.info(f"LLM 기반 첨부파일 선별 시작: 총 {len(attachments)}개 파일")

        try:
            # LLM에게 첨부파일 선별 요청
            selected_files = await self._request_llm_selection(
                attachments, content, subject
            )

            # 선별된 파일 정보를 원본 첨부파일과 매칭
            result = self._match_selected_files(selected_files, attachments)

            selection_rate = len(result) / len(attachments) * 100
            logger.info(f"LLM 선별 완료: {len(result)}개 파일 선택됨 "
                        f"(전체 {len(attachments)}개 중 {selection_rate:.1f}%)")

            return result

        except Exception as e:
            logger.error(f"LLM 첨부파일 선별 실패, rule-based로 fallback: {e}")
            # fallback to rule-based selection
            from .selector import select_relevant_attachments
            return select_relevant_attachments(attachments, content, subject)

    async def _request_llm_selection(
        self,
        attachments: List[Dict[str, Any]],
        content: str,
        subject: str
    ) -> List[Dict[str, str]]:
        """LLM에게 첨부파일 선별 요청"""

        # 첨부파일 메타데이터만 추출 (content는 제외)
        attachment_metadata = []
        for i, att in enumerate(attachments):
            metadata = {
                "index": i,
                "name": att.get('name', f'file_{i}'),
                "content_type": att.get('content_type', 'unknown'),
                "size": att.get('size', 0),
                "description": (att.get('description', '') or
                                att.get('alt_text', ''))
            }
            attachment_metadata.append(metadata)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            attachment_metadata, content, subject)

        response = await self.llm_manager.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            provider=LLMProvider.OPENAI,
            max_tokens=800,
            temperature=0.1,  # 일관성을 위해 낮게 설정
            model_preference=["gpt-4o-mini"]
        )

        if not response or not response.success:
            raise Exception("LLM 응답 실패")

        # JSON 응답 파싱
        try:
            result = json.loads(response.content.strip())
            return result.get('selected_files', [])
        except json.JSONDecodeError as e:
            logger.error(f"LLM 응답 JSON 파싱 실패: {e}, 원본: {response.content}")
            raise Exception("JSON 파싱 실패")

    def _build_system_prompt(self) -> str:
        """시스템 프롬프트 생성"""
        return """You are an intelligent attachment selector for customer support tickets.

Your task is to analyze ticket content and select the most relevant
attachments (maximum 3) that would help support agents resolve
the issue effectively.

Selection Criteria:
1. **Direct Relevance**: Files directly mentioned in the ticket content
2. **Problem Context**: Files that provide context for the reported
   issue (logs, screenshots, configs)
3. **Solution Support**: Files that would help in troubleshooting
   or resolution
4. **File Importance**:
   - Log files (.log, .txt) - High priority for technical issues
   - Screenshots/Images (.png, .jpg) - High priority for UI/visual issues
   - Configuration files (.json, .xml, .yml) - High priority for setup issues
   - Documents (.pdf, .doc) - Medium priority for reference

Avoid selecting:
- Files with no clear connection to the issue
- Duplicate or redundant files
- Files that are too large without clear relevance
- Generic files without specific context

Always respond in valid JSON format with reasoning for each selection."""

    def _build_user_prompt(
        self,
        attachment_metadata: List[Dict],
        content: str,
        subject: str
    ) -> str:
        """사용자 프롬프트 생성"""
        attachments_json = json.dumps(
            attachment_metadata, ensure_ascii=False, indent=2)

        return f"""Analyze this support ticket and select the most
relevant attachments (maximum 3).

**Ticket Subject:** {subject}

**Ticket Content:**
{content[:2000]}{"..." if len(content) > 2000 else ""}

**Available Attachments:**
{attachments_json}

Please select the most relevant attachments and respond in this
exact JSON format:

{{
  "selected_files": [
    {{
      "index": 0,
      "name": "filename.ext",
      "relevance_score": 9,
      "reason": "Brief explanation of why this file is relevant"
    }}
  ],
  "selection_summary": "Brief summary of selection strategy used"
}}

Requirements:
- Select maximum 3 files
- Include relevance_score (1-10, where 10 is most relevant)
- Provide clear reason for each selection
- Only select files with relevance_score >= 6
- If no files meet the criteria, return empty selected_files array"""

    def _match_selected_files(
        self,
        selected_files: List[Dict[str, str]],
        original_attachments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """선별된 파일 정보를 원본 첨부파일과 매칭"""
        result = []

        for selected in selected_files:
            try:
                index = int(selected.get('index', -1))
                if 0 <= index < len(original_attachments):
                    attachment = original_attachments[index].copy()
                    # LLM 선별 정보 추가
                    attachment['llm_selection'] = {
                        'relevance_score': selected.get('relevance_score', 0),
                        'reason': selected.get('reason', ''),
                        'selected_at': datetime.utcnow().isoformat(),
                        'selector_version': self.prompt_version
                    }
                    result.append(attachment)
                    logger.debug(
                        f"파일 매칭 성공: {attachment.get('name')} "
                        f"(점수: {selected.get('relevance_score')})")
                else:
                    logger.warning(f"잘못된 파일 인덱스: {index}")
            except Exception as e:
                logger.error(f"파일 매칭 오류: {e}")
                continue

        return result[:self.max_selected]  # 최대 개수 제한


# 권장 함수형 인터페이스 - 요약 기반 첨부파일 선별
async def select_relevant_attachments_llm(
    attachments: List[Dict[str, Any]],
    content: str,
    subject: str = "",
    summary: str = ""
) -> List[Dict[str, Any]]:
    """
    LLM 기반 첨부파일 선별 - 요약 기반 개선된 방식
    
    로직:
    - 0개: 빈 리스트 반환
    - 1-2개: 모두 반환 (선별 불필요)
    - 3개 이상: LLM으로 최대 3개 선별 (요약 정보 활용)
    
    Args:
        attachments: 전체 첨부파일 리스트
        content: 원본 티켓 내용
        subject: 티켓 제목
        summary: 이미 생성된 티켓 요약 (있으면 더 정확한 선별 가능)
    """
    if not attachments:
        return []
        
    # 2개 이하면 모두 반환 (선별할 필요 없음)
    if len(attachments) <= 2:
        logger.info(f"첨부파일 {len(attachments)}개 - 모두 반환")
        return attachments
        
    # 3개 이상이면 LLM 선별 (요약 정보 활용)
    logger.info(f"첨부파일 {len(attachments)}개 - LLM 선별 시작"
                f"{'(요약 기반)' if summary else '(내용 기반)'}")
    
    selector = LLMAttachmentSelector()
    
    # 요약이 있으면 요약을 주요 컨텍스트로 사용
    analysis_content = f"""
티켓 요약:
{summary}

원본 내용:
{content[:1000]}{"..." if len(content) > 1000 else ""}
""" if summary else content
    
    return await selector.select_relevant_attachments(
        attachments, analysis_content, subject
    )
