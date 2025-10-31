"""
Input validation utilities
"""
import re
from typing import Optional


def validate_ticket_id(ticket_id: str) -> bool:
    """
    Validate Freshdesk ticket ID format

    Args:
        ticket_id: Ticket ID to validate

    Returns:
        True if valid format
    """
    # Freshdesk ticket IDs are typically numeric
    return ticket_id.isdigit()


def validate_email(email: str) -> bool:
    """
    Validate email format

    Args:
        email: Email address to validate

    Returns:
        True if valid email format
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user input

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text
    """
    # Remove null bytes
    text = text.replace('\x00', '')

    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length]

    return text.strip()
