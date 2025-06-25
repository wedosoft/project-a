"""
Email processing module for handling email-specific content
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EmailMetadata:
    """Extracted email metadata"""
    sender: str
    recipient: str
    subject: str
    date: Optional[datetime]
    thread_position: int
    is_reply: bool
    has_attachments: bool


@dataclass
class ProcessedEmail:
    """Processed email content"""
    content: str
    metadata: EmailMetadata
    conversation_context: List[str]
    key_points: List[str]
    action_items: List[str]


class EmailProcessor:
    """
    Specialized processor for email content
    """
    
    def __init__(self):
        self.signature_patterns = [
            r'\n--\s*\n.*$',
            r'\n___+\n.*$',
            r'\n\s*Best regards?.*$',
            r'\n\s*Sincerely.*$',
            r'\n\s*Thanks?.*$',
            r'\n\s*감사합니다.*$',
            r'\n\s*안녕히.*$'
        ]
        
        self.quoted_text_patterns = [
            r'\n>.*$',
            r'\nOn .* wrote:.*$',
            r'\n.*님이 작성:.*$',
            r'\n-{5,}.*?-{5,}.*$'
        ]
    
    def process_email_content(
        self,
        content: str,
        preserve_thread: bool = True,
        extract_actions: bool = True
    ) -> ProcessedEmail:
        """
        Process email content with specialized handling
        
        Args:
            content: Raw email content
            preserve_thread: Whether to preserve conversation thread context
            extract_actions: Whether to extract action items
            
        Returns:
            ProcessedEmail with cleaned content and metadata
        """
        try:
            # Extract metadata
            metadata = self._extract_email_metadata(content)
            
            # Clean content
            cleaned_content = self._clean_email_content(content, preserve_thread)
            
            # Extract conversation context
            conversation_context = []
            if preserve_thread and metadata.is_reply:
                conversation_context = self._extract_conversation_context(content)
            
            # Extract key points
            key_points = self._extract_key_points(cleaned_content)
            
            # Extract action items
            action_items = []
            if extract_actions:
                action_items = self._extract_action_items(cleaned_content)
            
            logger.info(f"Email processed - Key points: {len(key_points)}, Actions: {len(action_items)}")
            
            return ProcessedEmail(
                content=cleaned_content,
                metadata=metadata,
                conversation_context=conversation_context,
                key_points=key_points,
                action_items=action_items
            )
            
        except Exception as e:
            logger.error(f"Email processing failed: {e}")
            # Return minimal processed result
            return ProcessedEmail(
                content=content,
                metadata=EmailMetadata(
                    sender="Unknown",
                    recipient="Unknown", 
                    subject="",
                    date=None,
                    thread_position=1,
                    is_reply=False,
                    has_attachments=False
                ),
                conversation_context=[],
                key_points=[],
                action_items=[]
            )
    
    def _extract_email_metadata(self, content: str) -> EmailMetadata:
        """Extract email metadata from content"""
        sender = "Unknown"
        recipient = "Unknown"
        subject = ""
        date = None
        is_reply = False
        has_attachments = False
        
        # Extract sender
        sender_match = re.search(r'^From:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if sender_match:
            sender = sender_match.group(1).strip()
        
        # Extract recipient
        to_match = re.search(r'^To:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if to_match:
            recipient = to_match.group(1).strip()
        
        # Extract subject
        subject_match = re.search(r'^Subject:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if subject_match:
            subject = subject_match.group(1).strip()
            is_reply = subject.lower().startswith(('re:', 'fw:', 'fwd:', '답장:', '전달:'))
        
        # Check for attachments
        has_attachments = bool(re.search(r'attachment|첨부|파일', content, re.IGNORECASE))
        
        # Determine thread position
        thread_position = 1
        if is_reply:
            # Count reply indicators
            reply_count = len(re.findall(r'(?:^>|On .* wrote:|님이 작성:)', content, re.MULTILINE))
            thread_position = max(1, reply_count + 1)
        
        return EmailMetadata(
            sender=sender,
            recipient=recipient,
            subject=subject,
            date=date,
            thread_position=thread_position,
            is_reply=is_reply,
            has_attachments=has_attachments
        )
    
    def _clean_email_content(self, content: str, preserve_thread: bool = True) -> str:
        """Clean email content by removing headers, signatures, etc."""
        cleaned = content
        
        # Remove standard email headers
        header_patterns = [
            r'^From:.*?\n',
            r'^To:.*?\n', 
            r'^Cc:.*?\n',
            r'^Bcc:.*?\n',
            r'^Subject:.*?\n',
            r'^Date:.*?\n',
            r'^Reply-To:.*?\n',
            r'^Message-ID:.*?\n'
        ]
        
        for pattern in header_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.IGNORECASE)
        
        # Remove signatures
        for pattern in self.signature_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        # Handle quoted text
        if not preserve_thread:
            for pattern in self.quoted_text_patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.DOTALL)
        
        # Normalize whitespace
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        
        return cleaned.strip()
    
    def _extract_conversation_context(self, content: str) -> List[str]:
        """Extract conversation thread context"""
        context_items = []
        
        # Find quoted sections
        quoted_sections = re.findall(r'\n>(.*?)(?=\n[^>]|\Z)', content, re.DOTALL)
        
        for section in quoted_sections:
            if section.strip() and len(section.strip()) > 20:
                # Clean up quoted text
                cleaned = re.sub(r'^>\s*', '', section, flags=re.MULTILINE)
                cleaned = cleaned.strip()
                if cleaned:
                    context_items.append(cleaned)
        
        return context_items[:3]  # Limit to 3 most recent contexts
    
    def _extract_key_points(self, content: str) -> List[str]:
        """Extract key points from email content"""
        key_points = []
        
        # Look for numbered lists
        numbered_items = re.findall(r'^\d+\.\s*(.+)$', content, re.MULTILINE)
        key_points.extend(numbered_items)
        
        # Look for bullet points
        bullet_items = re.findall(r'^[•*-]\s*(.+)$', content, re.MULTILINE)
        key_points.extend(bullet_items)
        
        # Look for emphasized text (bold, caps)
        emphasized = re.findall(r'\*\*(.+?)\*\*', content)
        key_points.extend(emphasized)
        
        # Look for sentences with important keywords
        important_sentences = re.findall(
            r'[^.!?]*(?:important|urgent|critical|key|main|primary|중요|긴급|핵심|주요)[^.!?]*[.!?]',
            content, re.IGNORECASE
        )
        key_points.extend([s.strip() for s in important_sentences])
        
        # Remove duplicates and filter
        unique_points = []
        for point in key_points:
            cleaned = point.strip()
            if cleaned and len(cleaned) > 10 and cleaned not in unique_points:
                unique_points.append(cleaned)
        
        return unique_points[:5]  # Top 5 key points
    
    def _extract_action_items(self, content: str) -> List[str]:
        """Extract action items from email content"""
        action_items = []
        
        # Action verbs and patterns
        action_patterns = [
            r'(?:please|could you|can you|need to|should|must|will|shall)\s+([^.!?]+[.!?])',
            r'(?:부탁|요청|필요|해야|할것|예정)[^.!?]*[.!?]',
            r'(?:todo|action|task|follow up):\s*([^.!?]+)',
            r'(?:할일|액션|작업|후속조치):\s*([^.!?]+)'
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                cleaned = match.strip()
                if cleaned and len(cleaned) > 5:
                    action_items.append(cleaned)
        
        # Look for sentences ending with question marks (potential requests)
        questions = re.findall(r'[^.!?]*\?', content)
        for question in questions:
            cleaned = question.strip()
            if any(word in cleaned.lower() for word in ['can', 'could', 'would', 'will', '할 수', '가능한', '부탁']):
                action_items.append(cleaned)
        
        # Remove duplicates
        unique_actions = []
        for action in action_items:
            if action not in unique_actions and len(action) > 10:
                unique_actions.append(action)
        
        return unique_actions[:3]  # Top 3 action items
    
    def format_email_summary_context(self, processed_email: ProcessedEmail) -> Dict[str, Any]:
        """Format processed email for summary generation"""
        return {
            'content_type': 'email',
            'sender': processed_email.metadata.sender,
            'subject': processed_email.metadata.subject,
            'is_reply': processed_email.metadata.is_reply,
            'thread_position': processed_email.metadata.thread_position,
            'key_points': processed_email.key_points,
            'action_items': processed_email.action_items,
            'conversation_context': processed_email.conversation_context,
            'has_attachments': processed_email.metadata.has_attachments
        }
