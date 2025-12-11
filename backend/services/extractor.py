"""
LLM-based Issue Block Extractor

Extracts Symptom/Cause/Resolution blocks from Freshdesk tickets using:
- OpenAI GPT-4o-mini (primary)
- Google Gemini 1.5 Flash (fallback)

Features:
- Structured JSON output
- Batch processing (10 tickets at a time)
- Retry logic (3 attempts)
- Cost optimization
"""
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import json
import asyncio
from openai import AsyncOpenAI

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from backend.config import get_settings
from backend.utils.logger import get_logger
from backend.models.schemas import IssueBlock, BlockType

settings = get_settings()
logger = get_logger(__name__)

if not GENAI_AVAILABLE:
    logger.warning("google-generativeai not available, Gemini provider will not work")


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    GEMINI = "gemini"


class IssueBlockExtractor:
    """
    Extract Issue Blocks (Symptom/Cause/Resolution) from ticket content using LLM
    """

    def __init__(self, provider: LLMProvider = LLMProvider.OPENAI):
        """
        Initialize extractor with specified LLM provider

        Args:
            provider: LLM provider to use (default: OpenAI)
        """
        self.provider = provider
        self.max_retries = 3
        self.batch_size = 10

        # Initialize OpenAI client
        if provider == LLMProvider.OPENAI:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4o-mini"
        # Initialize Gemini
        elif provider == LLMProvider.GEMINI:
            if not GENAI_AVAILABLE:
                raise ImportError(
                    "google-generativeai is not installed. "
                    "Install it with: pip install google-generativeai"
                )
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")
            self.model = "gemini-2.0-flash-exp"

        logger.info(f"Initialized IssueBlockExtractor with {provider.value} ({self.model})")

    def _create_extraction_prompt(self, ticket_content: str) -> str:
        """
        Create prompt for issue block extraction

        Args:
            ticket_content: Ticket subject + description + conversations

        Returns:
            Formatted prompt string
        """
        return f"""아래 티켓의 전체 대화 내역을 꼼꼼히 분석하여 다음 JSON 형식으로 추출하세요:

{{
  "symptom": "고객이 겪은 문제 증상 (현상)",
  "cause": "문제의 원인 (대화 내역에서 파악된 실제 원인)",
  "resolution": "최종 해결 방법 또는 현재 진행 상황"
}}

분석 지침:
- symptom: 고객이 처음 보고한 문제 현상을 명확하게 요약
- cause: **전체 대화 내역을 분석하여** 파악된 문제의 근본 원인
  * 대화 중 밝혀진 기술적 원인, 설정 오류, 버그 등을 구체적으로 기술
  * 원인이 불명확하거나 아직 조사 중이면 null
- resolution: 마지막 대화까지 확인하여 최종 해결책 또는 진행 중인 조치사항
  * 해결 완료: 구체적인 해결 방법 기술
  * 진행 중: 현재 어떤 조치를 취하고 있는지 기술

티켓 내용:
{ticket_content}

JSON만 출력하세요:"""

    async def _extract_with_openai(
        self,
        ticket_content: str
    ) -> Dict[str, Optional[str]]:
        """
        Extract using OpenAI GPT-4o-mini

        Args:
            ticket_content: Combined ticket text

        Returns:
            Dictionary with symptom, cause, resolution

        Raises:
            Exception: On extraction failure after retries
        """
        prompt = self._create_extraction_prompt(ticket_content)

        for attempt in range(self.max_retries):
            try:
                response = await self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a technical support analyst extracting structured information from tickets."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=500
                )

                result_text = response.choices[0].message.content
                result = json.loads(result_text)

                # Validate required fields
                if "symptom" not in result:
                    raise ValueError("Missing 'symptom' field in extraction")

                return {
                    "symptom": result.get("symptom"),
                    "cause": result.get("cause"),
                    "resolution": result.get("resolution")
                }

            except Exception as e:
                logger.warning(
                    f"OpenAI extraction attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

    def _extract_with_gemini(
        self,
        ticket_content: str
    ) -> Dict[str, Optional[str]]:
        """
        Extract using Google Gemini (synchronous)

        Args:
            ticket_content: Combined ticket text

        Returns:
            Dictionary with symptom, cause, resolution

        Raises:
            Exception: On extraction failure after retries
        """
        # Gemini needs explicit schema definition
        prompt = f"""아래 티켓의 전체 대화 내역을 꼼꼼히 분석하여 다음 JSON 형식으로 추출하세요:

{{
  "symptom": "고객이 겪은 문제 증상 (현상)",
  "cause": "문제의 원인 (대화 내역에서 파악된 실제 원인)",
  "resolution": "최종 해결 방법 또는 현재 진행 상황"
}}

분석 지침:
- symptom: 고객이 처음 보고한 문제 현상을 명확하게 요약 (필수)
- cause: **전체 대화 내역을 분석하여** 파악된 문제의 근본 원인
  * 대화 중 밝혀진 기술적 원인, 설정 오류, 버그 등을 구체적으로 기술
  * 원인이 불명확하거나 아직 조사 중이면 null
- resolution: 마지막 대화까지 확인하여 최종 해결책 또는 진행 중인 조치사항
  * 해결 완료: 구체적인 해결 방법 기술
  * 진행 중: 현재 어떤 조치를 취하고 있는지 기술

티켓 내용:
{ticket_content}

JSON만 출력하세요:"""

        for attempt in range(self.max_retries):
            try:
                response = self.gemini_model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=500,
                        response_mime_type="application/json"
                    )
                )

                result = json.loads(response.text)

                # Gemini sometimes returns array, extract first element
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]

                # Validate required fields and ensure symptom is not null
                if "symptom" not in result or result["symptom"] is None:
                    raise ValueError(f"Missing 'symptom' field in extraction. Got: {result}")

                return {
                    "symptom": result.get("symptom"),
                    "cause": result.get("cause"),
                    "resolution": result.get("resolution")
                }

            except Exception as e:
                logger.warning(
                    f"Gemini extraction attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                raise

    async def extract_from_ticket(
        self,
        ticket_data: Dict[str, Any]
    ) -> Dict[str, Optional[str]]:
        """
        Extract issue blocks from a single ticket

        Args:
            ticket_data: Freshdesk ticket dictionary

        Returns:
            Dictionary with symptom, cause, resolution
        """
        # Combine ticket content
        subject = ticket_data.get("subject", "")
        description = ticket_data.get("description_text", "")

        # Include ALL conversations with timestamps and sender info for full context
        conversations = ""
        if "conversations" in ticket_data:
            conv_list = []
            for i, conv in enumerate(ticket_data["conversations"], 1):
                sender = conv.get("from_email", "Unknown")
                body = conv.get("body_text", "")
                created_at = conv.get("created_at", "")

                conv_list.append(f"[대화 {i}] {sender} ({created_at}):\n{body}")

            conversations = "\n\n".join(conv_list)

        ticket_content = f"""Subject: {subject}

Description:
{description}

모든 대화 내역 ({len(ticket_data.get('conversations', []))}개):
{conversations}"""

        logger.info(f"Extracting from ticket {ticket_data.get('id', 'unknown')}")

        # Call appropriate LLM
        if self.provider == LLMProvider.OPENAI:
            return await self._extract_with_openai(ticket_content)
        else:
            # Gemini is synchronous, wrap in async
            return await asyncio.to_thread(
                self._extract_with_gemini,
                ticket_content
            )

    async def extract_batch(
        self,
        tickets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract issue blocks from multiple tickets in batch

        Args:
            tickets: List of Freshdesk ticket dictionaries

        Returns:
            List of extraction results with ticket_id and blocks
        """
        logger.info(f"Processing batch of {len(tickets)} tickets")

        # Process in batches
        results = []
        for i in range(0, len(tickets), self.batch_size):
            batch = tickets[i:i + self.batch_size]
            logger.info(f"Processing batch {i // self.batch_size + 1} ({len(batch)} tickets)")

            # Extract concurrently within batch
            batch_tasks = [
                self.extract_from_ticket(ticket)
                for ticket in batch
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Combine results with ticket IDs
            for ticket, extraction in zip(batch, batch_results):
                if isinstance(extraction, Exception):
                    logger.error(f"Failed to extract from ticket {ticket.get('id')}: {extraction}")
                    results.append({
                        "ticket_id": ticket.get("id"),
                        "success": False,
                        "error": str(extraction)
                    })
                else:
                    results.append({
                        "ticket_id": ticket.get("id"),
                        "success": True,
                        "blocks": extraction
                    })

        logger.info(f"Batch extraction complete: {len([r for r in results if r['success']])} succeeded")
        return results


# Convenience function
async def extract_issue_blocks(
    tickets: List[Dict[str, Any]],
    provider: LLMProvider = LLMProvider.OPENAI
) -> List[Dict[str, Any]]:
    """
    Extract issue blocks from tickets using specified LLM provider

    Args:
        tickets: List of Freshdesk ticket dictionaries
        provider: LLM provider (default: OpenAI)

    Returns:
        List of extraction results
    """
    extractor = IssueBlockExtractor(provider=provider)
    return await extractor.extract_batch(tickets)
