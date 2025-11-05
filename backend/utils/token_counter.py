"""
Token Counting Utility

Provides accurate token counting for LLM inputs using tiktoken.
Essential for chunking strategy and token limit validation.

Author: AI Assistant POC
Date: 2025-11-05
"""

import tiktoken
from typing import Optional, Dict, Any
from backend.config import get_settings

settings = get_settings()


class TokenCounter:
    """
    Token counter using tiktoken for accurate GPT model token counting.

    Supports multiple model encodings:
    - gpt-4, gpt-3.5-turbo: cl100k_base
    - text-davinci-003: p50k_base
    - code models: p50k_base
    """

    def __init__(self, model_name: str = "gpt-4"):
        """
        Initialize token counter for specific model.

        Args:
            model_name: OpenAI model name for encoding selection
        """
        self.model_name = model_name
        self.encoding = self._get_encoding(model_name)

    def _get_encoding(self, model_name: str) -> tiktoken.Encoding:
        """Get appropriate encoding for model."""
        try:
            return tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            return tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text string.

        Args:
            text: Input text to count tokens

        Returns:
            Number of tokens

        Example:
            >>> counter = TokenCounter()
            >>> counter.count_tokens("Hello world")
            2
        """
        if not text:
            return 0

        return len(self.encoding.encode(text))

    def count_tokens_in_messages(
        self,
        messages: list[Dict[str, str]]
    ) -> int:
        """
        Count tokens in chat message format.

        OpenAI chat models use special token counting:
        - Each message: 3 tokens (role/name markers)
        - Reply priming: 3 tokens

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Total token count including overhead

        Example:
            >>> counter = TokenCounter()
            >>> messages = [
            ...     {"role": "system", "content": "You are helpful"},
            ...     {"role": "user", "content": "Hello"}
            ... ]
            >>> counter.count_tokens_in_messages(messages)
            15  # Approximate with overhead
        """
        if not messages:
            return 0

        num_tokens = 0

        # Token overhead per message
        tokens_per_message = 3
        tokens_per_name = 1

        for message in messages:
            num_tokens += tokens_per_message

            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += self.count_tokens(value)
                    if key == "name":
                        num_tokens += tokens_per_name

        # Reply priming
        num_tokens += 3

        return num_tokens

    def count_tokens_in_dict(self, data: Dict[str, Any]) -> int:
        """
        Count tokens in nested dictionary structure.

        Args:
            data: Dictionary with potentially nested text values

        Returns:
            Total token count for all text content
        """
        total_tokens = 0

        for key, value in data.items():
            if isinstance(value, str):
                total_tokens += self.count_tokens(value)
            elif isinstance(value, dict):
                total_tokens += self.count_tokens_in_dict(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        total_tokens += self.count_tokens(item)
                    elif isinstance(item, dict):
                        total_tokens += self.count_tokens_in_dict(item)

        return total_tokens

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        model_name: Optional[str] = None
    ) -> float:
        """
        Estimate API cost based on token count.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model_name: Override model for pricing

        Returns:
            Estimated cost in USD

        Note:
            Pricing as of 2025-01 (update regularly):
            - gpt-4: $0.03/1K input, $0.06/1K output
            - gpt-3.5-turbo: $0.0015/1K input, $0.002/1K output
        """
        model = model_name or self.model_name

        # Pricing table (update as needed)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        }

        # Fallback to gpt-4 pricing for unknown models
        rates = pricing.get(model, pricing["gpt-4"])

        input_cost = (input_tokens / 1000) * rates["input"]
        output_cost = (output_tokens / 1000) * rates["output"]

        return round(input_cost + output_cost, 6)

    def will_exceed_limit(
        self,
        text: str,
        limit: int,
        buffer: int = 500
    ) -> bool:
        """
        Check if text will exceed token limit with buffer.

        Args:
            text: Text to check
            limit: Token limit
            buffer: Safety buffer for response tokens

        Returns:
            True if text + buffer exceeds limit
        """
        tokens = self.count_tokens(text)
        return (tokens + buffer) > limit


# Global instance for convenience
_default_counter = None


def get_token_counter(model_name: str = "gpt-4") -> TokenCounter:
    """
    Get or create singleton token counter instance.

    Args:
        model_name: Model name for encoding

    Returns:
        TokenCounter instance
    """
    global _default_counter

    if _default_counter is None or _default_counter.model_name != model_name:
        _default_counter = TokenCounter(model_name)

    return _default_counter


def count_tokens(text: str, model_name: str = "gpt-4") -> int:
    """
    Convenience function for quick token counting.

    Args:
        text: Text to count
        model_name: Model for encoding

    Returns:
        Token count
    """
    counter = get_token_counter(model_name)
    return counter.count_tokens(text)


# Quick test
if __name__ == "__main__":
    counter = TokenCounter("gpt-4")

    # Test cases
    test_text = "This is a test message for token counting."
    test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"}
    ]

    print(f"Text tokens: {counter.count_tokens(test_text)}")
    print(f"Message tokens: {counter.count_tokens_in_messages(test_messages)}")
    print(f"Cost estimate: ${counter.estimate_cost(1000, 500):.4f}")
    print(f"Exceeds 10 limit: {counter.will_exceed_limit(test_text, 10)}")
