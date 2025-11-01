"""
Unit tests for LLM-based Issue Block Extractor

Tests:
- OpenAI extraction with retry logic
- Gemini extraction with retry logic
- Batch processing
- Error handling
- JSON validation
- Prompt creation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from backend.services.extractor import (
    IssueBlockExtractor,
    LLMProvider,
    extract_issue_blocks
)


@pytest.fixture
def sample_ticket():
    """Sample ticket data for testing"""
    return {
        "id": 123,
        "subject": "Login not working",
        "description_text": "Cannot login to the system. Getting error 500.",
        "conversations": [
            {"body_text": "We are investigating the issue."},
            {"body_text": "Database connection was fixed."},
            {"body_text": "Issue resolved."}
        ]
    }


@pytest.fixture
def sample_extraction():
    """Sample extraction result"""
    return {
        "symptom": "로그인 시 500 에러 발생",
        "cause": "데이터베이스 연결 문제",
        "resolution": "데이터베이스 연결 복구 완료"
    }


class TestExtractorInitialization:
    """Test extractor initialization"""

    def test_openai_initialization(self):
        """Test OpenAI provider initialization"""
        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        assert extractor.provider == LLMProvider.OPENAI
        assert extractor.model == "gpt-4o-mini"
        assert extractor.max_retries == 3
        assert extractor.batch_size == 10
        assert hasattr(extractor, "openai_client")

    def test_gemini_initialization(self):
        """Test Gemini provider initialization"""
        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel") as mock_model:
                extractor = IssueBlockExtractor(provider=LLMProvider.GEMINI)

                assert extractor.provider == LLMProvider.GEMINI
                assert extractor.model == "gemini-2.0-flash-exp"
                assert hasattr(extractor, "gemini_model")


class TestPromptCreation:
    """Test extraction prompt creation"""

    def test_prompt_contains_ticket_content(self, sample_ticket):
        """Test prompt includes ticket information"""
        extractor = IssueBlockExtractor()

        ticket_content = f"""Subject: {sample_ticket['subject']}

Description:
{sample_ticket['description_text']}

Recent Conversations:
We are investigating the issue.

Database connection was fixed.

Issue resolved."""

        prompt = extractor._create_extraction_prompt(ticket_content)

        assert sample_ticket["subject"] in prompt
        assert sample_ticket["description_text"] in prompt
        assert "JSON" in prompt
        assert "symptom" in prompt
        assert "cause" in prompt
        assert "resolution" in prompt


class TestOpenAIExtraction:
    """Test OpenAI extraction logic"""

    @pytest.mark.asyncio
    async def test_successful_extraction(self, sample_ticket, sample_extraction):
        """Test successful OpenAI extraction"""
        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_extraction)

        with patch.object(
            extractor.openai_client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            ticket_content = "Test content"
            result = await extractor._extract_with_openai(ticket_content)

            assert result["symptom"] == sample_extraction["symptom"]
            assert result["cause"] == sample_extraction["cause"]
            assert result["resolution"] == sample_extraction["resolution"]

    @pytest.mark.asyncio
    async def test_retry_on_error(self):
        """Test retry logic on API errors"""
        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        # First two calls fail, third succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "symptom": "test", "cause": "test", "resolution": "test"
        })

        mock_create = AsyncMock(side_effect=[
            Exception("API error"),
            Exception("API error"),
            mock_response
        ])

        with patch.object(
            extractor.openai_client.chat.completions,
            "create",
            mock_create
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await extractor._extract_with_openai("test content")

        assert mock_create.call_count == 3
        assert result["symptom"] == "test"

    @pytest.mark.asyncio
    async def test_missing_symptom_field(self):
        """Test validation error when symptom is missing"""
        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        # Response missing required 'symptom' field
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "cause": "test",
            "resolution": "test"
        })

        with patch.object(
            extractor.openai_client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ValueError, match="Missing 'symptom' field"):
                    await extractor._extract_with_openai("test content")


class TestGeminiExtraction:
    """Test Gemini extraction logic"""

    def test_successful_extraction(self, sample_extraction):
        """Test successful Gemini extraction"""
        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel") as mock_model_class:
                extractor = IssueBlockExtractor(provider=LLMProvider.GEMINI)

                # Mock Gemini response
                mock_response = MagicMock()
                mock_response.text = json.dumps(sample_extraction)
                extractor.gemini_model.generate_content = MagicMock(
                    return_value=mock_response
                )

                result = extractor._extract_with_gemini("test content")

                assert result["symptom"] == sample_extraction["symptom"]
                assert result["cause"] == sample_extraction["cause"]
                assert result["resolution"] == sample_extraction["resolution"]

    def test_retry_on_error(self):
        """Test retry logic on Gemini API errors"""
        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel"):
                extractor = IssueBlockExtractor(provider=LLMProvider.GEMINI)

                # First two calls fail, third succeeds
                mock_response = MagicMock()
                mock_response.text = json.dumps({
                    "symptom": "test", "cause": "test", "resolution": "test"
                })

                extractor.gemini_model.generate_content = MagicMock(side_effect=[
                    Exception("API error"),
                    Exception("API error"),
                    mock_response
                ])

                with patch("time.sleep"):
                    result = extractor._extract_with_gemini("test content")

                assert extractor.gemini_model.generate_content.call_count == 3
                assert result["symptom"] == "test"


class TestExtractFromTicket:
    """Test single ticket extraction"""

    @pytest.mark.asyncio
    async def test_extract_with_conversations(self, sample_ticket, sample_extraction):
        """Test extraction includes conversations"""
        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_extraction)

        with patch.object(
            extractor.openai_client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response
        ) as mock_create:
            result = await extractor.extract_from_ticket(sample_ticket)

            # Check that prompt was called
            assert mock_create.called
            call_args = mock_create.call_args[1]
            prompt = call_args["messages"][1]["content"]

            # Verify conversations were included
            assert "모든 대화 내역" in prompt
            assert sample_ticket["conversations"][0]["body_text"] in prompt

    @pytest.mark.asyncio
    async def test_extract_without_conversations(self, sample_extraction):
        """Test extraction works without conversations"""
        ticket = {
            "id": 123,
            "subject": "Test",
            "description_text": "Test description"
        }

        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_extraction)

        with patch.object(
            extractor.openai_client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await extractor.extract_from_ticket(ticket)

            assert result["symptom"] == sample_extraction["symptom"]


class TestBatchExtraction:
    """Test batch processing"""

    @pytest.mark.asyncio
    async def test_batch_processing(self, sample_ticket, sample_extraction):
        """Test batch extraction of multiple tickets"""
        tickets = [
            {**sample_ticket, "id": i}
            for i in range(25)  # 25 tickets (3 batches of 10, 10, 5)
        ]

        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_extraction)

        with patch.object(
            extractor.openai_client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            results = await extractor.extract_batch(tickets)

            assert len(results) == 25
            assert all(r["success"] for r in results)
            assert all("blocks" in r for r in results)

    @pytest.mark.asyncio
    async def test_batch_with_failures(self, sample_ticket):
        """Test batch processing handles failures gracefully"""
        tickets = [sample_ticket] * 5

        extractor = IssueBlockExtractor(provider=LLMProvider.OPENAI)

        # Mock some failures
        with patch.object(
            extractor,
            "extract_from_ticket",
            new_callable=AsyncMock,
            side_effect=[
                {"symptom": "test", "cause": "test", "resolution": "test"},
                Exception("API error"),
                {"symptom": "test", "cause": "test", "resolution": "test"},
                Exception("API error"),
                {"symptom": "test", "cause": "test", "resolution": "test"}
            ]
        ):
            results = await extractor.extract_batch(tickets)

            assert len(results) == 5
            assert sum(1 for r in results if r["success"]) == 3
            assert sum(1 for r in results if not r["success"]) == 2

    @pytest.mark.asyncio
    async def test_convenience_function(self, sample_ticket, sample_extraction):
        """Test convenience function extract_issue_blocks"""
        tickets = [sample_ticket]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_extraction)

        with patch("backend.services.extractor.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client

            results = await extract_issue_blocks(tickets, provider=LLMProvider.OPENAI)

            assert len(results) == 1
            assert results[0]["success"]
