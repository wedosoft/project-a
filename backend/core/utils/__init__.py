"""
Core utilities package

This package contains utility modules for the Freshdesk AI Assistant backend.
"""

# Make image_metadata_extractor functions available at package level
from .image_metadata_extractor import (
    extract_ticket_image_metadata,
    extract_article_image_metadata
)

__all__ = [
    'extract_ticket_image_metadata',
    'extract_article_image_metadata'
]