"""
Tests for Pydantic schemas to verify validation logic
"""
import pytest
from datetime import datetime
from uuid import uuid4
from pydantic import ValidationError

from backend.models.schemas import (
    BlockType,
    ApprovalStatus,
    SourceType,
    IssueBlock,
    IssueBlockCreate,
    KBBlock,
    KBBlockCreate,
    SearchResult,
    TicketContext,
    ProposedAction,
    FeedbackLog,
    MetricsPayload,
    ComplianceCheckResult,
)


class TestIssueBlockValidation:
    """Test IssueBlock model validation"""

    def test_valid_issue_block_symptom(self):
        """Test valid symptom block with minimum 10 chars"""
        block = IssueBlockCreate(
            tenant_id="test-tenant",
            ticket_id="TICKET-001",
            block_type=BlockType.SYMPTOM,
            content="Short symptom description"
        )
        assert block.block_type == BlockType.SYMPTOM
        assert len(block.content) >= 10

    def test_valid_issue_block_cause(self):
        """Test valid cause block with minimum 20 chars"""
        block = IssueBlockCreate(
            tenant_id="test-tenant",
            ticket_id="TICKET-001",
            block_type=BlockType.CAUSE,
            content="This is the root cause explanation with enough detail"
        )
        assert block.block_type == BlockType.CAUSE
        assert len(block.content) >= 20

    def test_valid_issue_block_resolution(self):
        """Test valid resolution block with minimum 30 chars"""
        block = IssueBlockCreate(
            tenant_id="test-tenant",
            ticket_id="TICKET-001",
            block_type=BlockType.RESOLUTION,
            content="This is the detailed resolution with step-by-step instructions"
        )
        assert block.block_type == BlockType.RESOLUTION
        assert len(block.content) >= 30

    def test_symptom_too_short(self):
        """Test symptom block fails with less than 10 chars"""
        with pytest.raises(ValidationError) as exc_info:
            IssueBlockCreate(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                block_type=BlockType.SYMPTOM,
                content="Short"  # Only 5 chars
            )
        assert "symptom content must be at least 10 characters" in str(exc_info.value)

    def test_cause_too_short(self):
        """Test cause block fails with less than 20 chars"""
        with pytest.raises(ValidationError) as exc_info:
            IssueBlockCreate(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                block_type=BlockType.CAUSE,
                content="Short cause"  # Only 11 chars
            )
        assert "cause content must be at least 20 characters" in str(exc_info.value)

    def test_resolution_too_short(self):
        """Test resolution block fails with less than 30 chars"""
        with pytest.raises(ValidationError) as exc_info:
            IssueBlockCreate(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                block_type=BlockType.RESOLUTION,
                content="Short resolution text"  # Only 21 chars
            )
        assert "resolution content must be at least 30 characters" in str(exc_info.value)

    def test_invalid_tenant_id_format(self):
        """Test tenant_id validation with invalid characters"""
        with pytest.raises(ValidationError):
            IssueBlockCreate(
                tenant_id="tenant@invalid!",  # Contains invalid characters
                ticket_id="TICKET-001",
                block_type=BlockType.SYMPTOM,
                content="Valid symptom content here"
            )

    def test_valid_tenant_id_formats(self):
        """Test various valid tenant_id formats"""
        valid_ids = ["tenant-1", "tenant_2", "TenantABC", "tenant-abc_123"]
        for tenant_id in valid_ids:
            block = IssueBlockCreate(
                tenant_id=tenant_id,
                ticket_id="TICKET-001",
                block_type=BlockType.SYMPTOM,
                content="Valid symptom content"
            )
            assert block.tenant_id == tenant_id

    def test_meta_validation(self):
        """Test meta field validation"""
        # Valid meta
        block = IssueBlockCreate(
            tenant_id="test-tenant",
            ticket_id="TICKET-001",
            block_type=BlockType.SYMPTOM,
            content="Valid symptom",
            meta={"lang": "ko", "tags": ["auth", "error"]}
        )
        assert block.meta["lang"] == "ko"
        assert "auth" in block.meta["tags"]

        # Invalid meta - lang is not a string
        with pytest.raises(ValidationError):
            IssueBlockCreate(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                block_type=BlockType.SYMPTOM,
                content="Valid symptom",
                meta={"lang": 123}  # Should be string
            )


class TestSearchResult:
    """Test SearchResult model"""

    def test_valid_search_result_case(self):
        """Test valid search result from case"""
        result = SearchResult(
            id=uuid4(),
            content="Matching issue content",
            block_type=BlockType.SYMPTOM,
            score=0.85,
            source_type=SourceType.ISSUE_CASE,
            confidence=0.9,
            excerpt="Matching issue...",
            ticket_id="TICKET-001",
            product="Product A",
            created_at=datetime.utcnow()
        )
        assert result.source_type == SourceType.ISSUE_CASE
        assert result.score == 0.85
        assert result.confidence == 0.9

    def test_valid_search_result_kb(self):
        """Test valid search result from KB"""
        result = SearchResult(
            id=uuid4(),
            content="KB article content",
            score=0.75,
            source_type=SourceType.KB_ARTICLE,
            article_id="KB-001"
        )
        assert result.source_type == SourceType.KB_ARTICLE
        assert result.block_type is None  # KB doesn't have block_type

    def test_score_range_validation(self):
        """Test score must be between 0 and 1"""
        with pytest.raises(ValidationError):
            SearchResult(
                id=uuid4(),
                content="Content",
                score=1.5,  # Invalid
                source_type=SourceType.ISSUE_CASE
            )


class TestFeedbackLog:
    """Test FeedbackLog model"""

    def test_valid_event_types(self):
        """Test all valid event types"""
        valid_events = ["view", "edit", "approve", "reject", "modify", "request_changes"]
        for event_type in valid_events:
            log = FeedbackLog(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                agent_id="agent-001",
                event_type=event_type
            )
            assert log.event_type == event_type

    def test_invalid_event_type(self):
        """Test invalid event type fails validation"""
        with pytest.raises(ValidationError):
            FeedbackLog(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                agent_id="agent-001",
                event_type="invalid_event"
            )

    def test_rating_range(self):
        """Test rating must be between 1 and 5"""
        # Valid ratings
        for rating in [1, 2, 3, 4, 5]:
            log = FeedbackLog(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                agent_id="agent-001",
                event_type="approve",
                rating=rating
            )
            assert log.rating == rating

        # Invalid ratings
        with pytest.raises(ValidationError):
            FeedbackLog(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                agent_id="agent-001",
                event_type="approve",
                rating=6  # Too high
            )


class TestMetricsPayload:
    """Test MetricsPayload model"""

    def test_valid_metric_types(self):
        """Test all valid metric types"""
        valid_metrics = ["recall", "ndcg", "precision", "f1", "mrr", "map"]
        for metric_type in valid_metrics:
            metrics = MetricsPayload(
                tenant_id="test-tenant",
                metric_type=metric_type,
                score=0.85,
                k=10,
                total_results=20,
                relevant_results=15,
                latency_ms=125.5
            )
            assert metrics.metric_type == metric_type

    def test_invalid_metric_type(self):
        """Test invalid metric type fails"""
        with pytest.raises(ValidationError):
            MetricsPayload(
                tenant_id="test-tenant",
                metric_type="invalid_metric",
                score=0.85,
                k=10,
                total_results=20,
                relevant_results=15,
                latency_ms=125.5
            )

    def test_k_range(self):
        """Test k must be between 1 and 100"""
        with pytest.raises(ValidationError):
            MetricsPayload(
                tenant_id="test-tenant",
                metric_type="recall",
                score=0.85,
                k=0,  # Too low
                total_results=20,
                relevant_results=15,
                latency_ms=125.5
            )


class TestComplianceCheckResult:
    """Test ComplianceCheckResult model"""

    def test_valid_check_types(self):
        """Test all valid check types"""
        valid_checks = ["pii", "dlp", "policy", "security", "gdpr", "hipaa"]
        for check_type in valid_checks:
            result = ComplianceCheckResult(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                check_type=check_type,
                passed=True,
                severity="low"
            )
            assert result.check_type == check_type

    def test_valid_severity_levels(self):
        """Test all valid severity levels"""
        valid_severities = ["low", "medium", "high", "critical"]
        for severity in valid_severities:
            result = ComplianceCheckResult(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                check_type="pii",
                passed=False,
                severity=severity,
                violations=["Found PII in content"]
            )
            assert result.severity == severity

    def test_invalid_severity(self):
        """Test invalid severity fails"""
        with pytest.raises(ValidationError):
            ComplianceCheckResult(
                tenant_id="test-tenant",
                ticket_id="TICKET-001",
                check_type="pii",
                passed=False,
                severity="extreme",  # Invalid
                violations=["Found PII"]
            )


class TestKBBlock:
    """Test KBBlock model"""

    def test_renamed_field_constraints(self):
        """Test that 'constraints' field (formerly constraint_text) works"""
        kb = KBBlockCreate(
            tenant_id="test-tenant",
            article_id="KB-001",
            intent="Help user reset password",
            step="1. Click forgot password 2. Enter email 3. Check inbox",
            constraints="Password must be 8+ characters with special chars"
        )
        assert kb.constraints == "Password must be 8+ characters with special chars"
        assert not hasattr(kb, "constraint_text")  # Old name should not exist


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
