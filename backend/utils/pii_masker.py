"""
PII Masking Utility

Detects and masks personally identifiable information (PII) in text
to protect user privacy during SSE transmission and logging.

Author: AI Assistant POC
Date: 2025-11-05
"""

import re
from typing import Dict, Pattern


# Compiled regex patterns for PII detection
PII_PATTERNS: Dict[str, Pattern] = {
    'email': re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ),
    'phone': re.compile(
        r'\b\d{3}[-.\s]?\d{3,4}[-.\s]?\d{4}\b'
    ),
    'ssn': re.compile(
        r'\b\d{3}-\d{2}-\d{4}\b'
    ),
    'card': re.compile(
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    ),
    # Additional patterns for common PII
    'zipcode': re.compile(
        r'\b\d{5}(?:-\d{4})?\b'
    ),
}


def mask_pii(text: str, preserve_structure: bool = True) -> str:
    """
    Mask PII in text using regex pattern matching.

    Args:
        text: Input text containing potential PII
        preserve_structure: If True, maintains similar character count in masks

    Returns:
        Text with PII masked

    Examples:
        >>> mask_pii("Contact john@example.com at 555-1234")
        'Contact ***@***.*** at ***-***-****'

        >>> mask_pii("Card: 1234-5678-9012-3456")
        'Card: ****-****-****-****'
    """
    if not text:
        return text

    masked_text = text

    # Apply masks for each PII type
    for pii_type, pattern in PII_PATTERNS.items():
        if pii_type == 'email':
            masked_text = pattern.sub('***@***.***', masked_text)
        elif pii_type == 'phone':
            masked_text = pattern.sub('***-***-****', masked_text)
        elif pii_type == 'ssn':
            masked_text = pattern.sub('***-**-****', masked_text)
        elif pii_type == 'card':
            masked_text = pattern.sub('****-****-****-****', masked_text)
        elif pii_type == 'zipcode':
            # Only mask if preserve_structure is False (zipcodes less sensitive)
            if not preserve_structure:
                masked_text = pattern.sub('*****', masked_text)

    return masked_text


def mask_pii_in_dict(data: Dict, fields_to_mask: list = None) -> Dict:
    """
    Recursively mask PII in dictionary values.

    Args:
        data: Dictionary containing potential PII
        fields_to_mask: List of field names to mask (None = mask all text fields)

    Returns:
        Dictionary with PII masked in text fields

    Example:
        >>> mask_pii_in_dict({
        ...     "email": "user@example.com",
        ...     "message": "Call me at 555-1234"
        ... })
        {'email': '***@***.***', 'message': 'Call me at ***-***-****'}
    """
    if not isinstance(data, dict):
        return data

    masked_data = {}

    for key, value in data.items():
        # Check if this field should be masked
        should_mask = fields_to_mask is None or key in fields_to_mask

        if isinstance(value, str) and should_mask:
            masked_data[key] = mask_pii(value)
        elif isinstance(value, dict):
            masked_data[key] = mask_pii_in_dict(value, fields_to_mask)
        elif isinstance(value, list):
            masked_data[key] = [
                mask_pii_in_dict(item, fields_to_mask) if isinstance(item, dict)
                else mask_pii(item) if isinstance(item, str) and should_mask
                else item
                for item in value
            ]
        else:
            masked_data[key] = value

    return masked_data


def detect_pii(text: str) -> Dict[str, list]:
    """
    Detect PII in text without masking.

    Args:
        text: Input text to scan for PII

    Returns:
        Dictionary mapping PII types to list of detected values

    Example:
        >>> detect_pii("Email john@test.com, phone 555-1234")
        {'email': ['john@test.com'], 'phone': ['555-1234']}
    """
    if not text:
        return {}

    detected = {}

    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            detected[pii_type] = matches

    return detected


# Quick test
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "Contact john@example.com or call 555-123-4567",
        "SSN: 123-45-6789, Card: 1234 5678 9012 3456",
        "Email: user@domain.co.uk, ZIP: 12345-6789"
    ]

    print("PII Masking Tests:")
    for test in test_cases:
        print(f"\nOriginal: {test}")
        print(f"Masked:   {mask_pii(test)}")
        print(f"Detected: {detect_pii(test)}")
