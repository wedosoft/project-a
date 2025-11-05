"""
Ticket Chunking Utility

Implements intelligent chunking strategy for long ticket conversations
to stay within LLM token limits while preserving context quality.

Strategy:
- Keep subject + latest N conversations (most relevant)
- Summarize older conversations to preserve context
- Maintain token budget for response generation

Author: AI Assistant POC
Date: 2025-11-05
"""

from typing import Dict, List, Any, Optional
from backend.utils.token_counter import get_token_counter, TokenCounter


class TicketChunker:
    """
    Chunking service for managing long ticket conversations.

    Implements a "keep recent, summarize old" strategy to optimize
    for both context quality and token efficiency.
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        response_buffer: int = 1500,
        recent_conversation_count: int = 5,
        model_name: str = "gpt-4"
    ):
        """
        Initialize chunker with configuration.

        Args:
            max_tokens: Maximum tokens for input context
            response_buffer: Reserve tokens for LLM response
            recent_conversation_count: Number of recent conversations to keep
            model_name: Model name for token counting
        """
        self.max_tokens = max_tokens
        self.response_buffer = response_buffer
        self.recent_count = recent_conversation_count
        self.counter = get_token_counter(model_name)

        # Available tokens for context
        self.context_budget = max_tokens - response_buffer

    def chunk_ticket(
        self,
        ticket_context: Dict[str, Any],
        include_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Chunk ticket context to fit within token limits.

        Args:
            ticket_context: Ticket data with subject, description, conversations
            include_summary: Whether to summarize old conversations

        Returns:
            Chunked context with optimized token usage

        Example:
            >>> chunker = TicketChunker(max_tokens=4000)
            >>> context = {
            ...     "subject": "Login issue",
            ...     "description": "Cannot log in",
            ...     "conversations": [
            ...         {"body": "Old message 1", "user_id": 1},
            ...         {"body": "Old message 2", "user_id": 2},
            ...         # ... 50+ more conversations ...
            ...     ]
            ... }
            >>> chunked = chunker.chunk_ticket(context)
            >>> chunked.keys()
            dict_keys(['subject', 'description', 'summary', 'recent_conversations', 'metadata'])
        """
        subject = ticket_context.get('subject', '')
        description = ticket_context.get('description', '')
        conversations = ticket_context.get('conversations', [])

        # Calculate base tokens (subject + description)
        base_text = f"{subject}\n{description}"
        base_tokens = self.counter.count_tokens(base_text)

        # Budget remaining for conversations
        conversation_budget = self.context_budget - base_tokens

        if conversation_budget <= 0:
            # Even subject + description exceed budget
            return self._create_minimal_context(
                subject, description, conversations
            )

        # Split conversations into recent and old
        recent = conversations[-self.recent_count:] if conversations else []
        old = conversations[:-self.recent_count] if len(conversations) > self.recent_count else []

        # Count tokens for recent conversations
        recent_text = self._format_conversations(recent)
        recent_tokens = self.counter.count_tokens(recent_text)

        # Check if recent conversations fit
        if recent_tokens <= conversation_budget:
            # Fit! Now check if we need summary
            if not old or not include_summary:
                return {
                    'subject': subject,
                    'description': description,
                    'recent_conversations': recent,
                    'metadata': {
                        'total_conversations': len(conversations),
                        'included_conversations': len(recent),
                        'token_count': base_tokens + recent_tokens,
                        'chunked': len(old) > 0
                    }
                }

            # Generate summary for old conversations
            summary_budget = conversation_budget - recent_tokens
            summary = self._create_summary(old, summary_budget)

            return {
                'subject': subject,
                'description': description,
                'summary': summary,
                'recent_conversations': recent,
                'metadata': {
                    'total_conversations': len(conversations),
                    'summarized_conversations': len(old),
                    'included_conversations': len(recent),
                    'token_count': base_tokens + recent_tokens + self.counter.count_tokens(summary),
                    'chunked': True
                }
            }
        else:
            # Recent conversations alone exceed budget
            # Progressively reduce recent count
            return self._reduce_recent_conversations(
                subject,
                description,
                conversations,
                conversation_budget
            )

    def _format_conversations(self, conversations: List[Dict]) -> str:
        """Format conversations as text for token counting."""
        if not conversations:
            return ""

        formatted = []
        for conv in conversations:
            body = conv.get('body', '')
            user_id = conv.get('user_id', 'unknown')
            formatted.append(f"User {user_id}: {body}")

        return "\n".join(formatted)

    def _create_summary(
        self,
        conversations: List[Dict],
        max_tokens: int
    ) -> str:
        """
        Create summary of old conversations.

        For POC: Simple extraction of key points.
        For production: Use LLM summarization.

        Args:
            conversations: List of old conversations
            max_tokens: Maximum tokens for summary

        Returns:
            Summary text
        """
        if not conversations:
            return ""

        # POC: Simple summary (first + last messages)
        if len(conversations) <= 2:
            return self._format_conversations(conversations)

        # Extract key info
        summary_parts = [
            f"[Summary of {len(conversations)} earlier conversations]",
            f"First message: {conversations[0].get('body', '')[:100]}...",
            f"Last message: {conversations[-1].get('body', '')[:100]}..."
        ]

        summary = "\n".join(summary_parts)

        # Ensure summary fits within token budget
        if self.counter.count_tokens(summary) > max_tokens:
            # Truncate if needed
            summary = summary[:max_tokens * 4]  # Rough character estimate

        return summary

    def _reduce_recent_conversations(
        self,
        subject: str,
        description: str,
        conversations: List[Dict],
        budget: int
    ) -> Dict[str, Any]:
        """
        Progressively reduce recent conversations to fit budget.

        Args:
            subject: Ticket subject
            description: Ticket description
            conversations: All conversations
            budget: Available token budget

        Returns:
            Chunked context with reduced conversations
        """
        # Try reducing recent count
        for count in range(self.recent_count - 1, 0, -1):
            recent = conversations[-count:]
            recent_text = self._format_conversations(recent)
            recent_tokens = self.counter.count_tokens(recent_text)

            if recent_tokens <= budget:
                return {
                    'subject': subject,
                    'description': description,
                    'recent_conversations': recent,
                    'metadata': {
                        'total_conversations': len(conversations),
                        'included_conversations': count,
                        'token_count': recent_tokens,
                        'chunked': True,
                        'truncated': True
                    }
                }

        # Even single conversation exceeds budget
        return self._create_minimal_context(subject, description, conversations)

    def _create_minimal_context(
        self,
        subject: str,
        description: str,
        conversations: List[Dict]
    ) -> Dict[str, Any]:
        """Create minimal context when budget is severely limited."""
        # Truncate description if needed
        desc_budget = self.context_budget - self.counter.count_tokens(subject)
        truncated_desc = description

        if self.counter.count_tokens(description) > desc_budget:
            # Rough truncation (4 chars per token estimate)
            char_limit = desc_budget * 4
            truncated_desc = description[:char_limit] + "..."

        return {
            'subject': subject,
            'description': truncated_desc,
            'recent_conversations': [],
            'metadata': {
                'total_conversations': len(conversations),
                'included_conversations': 0,
                'token_count': self.counter.count_tokens(f"{subject}\n{truncated_desc}"),
                'chunked': True,
                'truncated': True,
                'minimal_mode': True
            }
        }

    def estimate_chunking_needed(
        self,
        ticket_context: Dict[str, Any]
    ) -> bool:
        """
        Quick check if chunking will be needed.

        Args:
            ticket_context: Full ticket context

        Returns:
            True if chunking required
        """
        total_text = f"{ticket_context.get('subject', '')}\n"
        total_text += f"{ticket_context.get('description', '')}\n"
        total_text += self._format_conversations(
            ticket_context.get('conversations', [])
        )

        total_tokens = self.counter.count_tokens(total_text)
        return total_tokens > self.context_budget


# Convenience function
def chunk_ticket_context(
    ticket_context: Dict[str, Any],
    max_tokens: int = 4000,
    model_name: str = "gpt-4"
) -> Dict[str, Any]:
    """
    Quick chunking function.

    Args:
        ticket_context: Ticket data
        max_tokens: Token limit
        model_name: Model for token counting

    Returns:
        Chunked context
    """
    chunker = TicketChunker(max_tokens=max_tokens, model_name=model_name)
    return chunker.chunk_ticket(ticket_context)


# Quick test
if __name__ == "__main__":
    chunker = TicketChunker(max_tokens=4000, recent_conversation_count=5)

    # Test with long ticket
    test_context = {
        'subject': 'Cannot access dashboard',
        'description': 'I am unable to log into the dashboard after the recent update.',
        'conversations': [
            {'body': f'Test message {i}', 'user_id': i % 2}
            for i in range(50)
        ]
    }

    chunked = chunker.chunk_ticket(test_context)

    print(f"Total conversations: {chunked['metadata']['total_conversations']}")
    print(f"Included conversations: {chunked['metadata']['included_conversations']}")
    print(f"Token count: {chunked['metadata']['token_count']}")
    print(f"Chunked: {chunked['metadata']['chunked']}")

    if 'summary' in chunked:
        print(f"\nSummary generated:")
        print(chunked['summary'][:200])
