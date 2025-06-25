"""
Context optimization module for managing content size and relevance
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of context optimization"""
    optimized_content: str
    original_length: int
    optimized_length: int
    compression_ratio: float
    sections_removed: List[str]
    optimization_applied: List[str]


class ContextOptimizer:
    """
    Optimizes content context for better LLM processing
    """
    
    def __init__(self):
        self.max_content_length = 8000  # Target maximum content length
        self.critical_content_patterns = [
            r'error|오류|에러',
            r'fail|실패|장애',
            r'urgent|긴급|중요',
            r'critical|중대|심각'
        ]
    
    def optimize_content_context(
        self,
        content: str,
        content_type: str = "ticket",
        preserve_sections: Optional[List[str]] = None
    ) -> OptimizationResult:
        """
        Optimize content context while preserving key information
        
        Args:
            content: Original content to optimize
            content_type: Type of content being optimized
            preserve_sections: Sections that must be preserved
            
        Returns:
            OptimizationResult with optimized content and metadata
        """
        try:
            if not content or len(content) <= self.max_content_length:
                return OptimizationResult(
                    optimized_content=content,
                    original_length=len(content) if content else 0,
                    optimized_length=len(content) if content else 0,
                    compression_ratio=1.0,
                    sections_removed=[],
                    optimization_applied=[]
                )
            
            logger.info(f"Optimizing content context - Original length: {len(content)}")
            
            original_length = len(content)
            optimized_content = content
            sections_removed = []
            optimization_applied = []
            
            # 1. Remove excessive whitespace and empty lines
            optimized_content = self._normalize_whitespace(optimized_content)
            if len(optimized_content) < original_length * 0.95:
                optimization_applied.append("whitespace_normalization")
            
            # 2. Extract and prioritize sections
            sections = self._extract_sections(optimized_content)
            prioritized_sections = self._prioritize_sections(sections, preserve_sections)
            
            # 3. Reconstruct content with priority order
            if len(optimized_content) > self.max_content_length:
                optimized_content, removed = self._reconstruct_prioritized_content(
                    prioritized_sections, self.max_content_length
                )
                sections_removed.extend(removed)
                optimization_applied.append("section_prioritization")
            
            # 4. Apply content-specific optimizations
            if content_type == "ticket":
                optimized_content = self._optimize_ticket_content(optimized_content)
                optimization_applied.append("ticket_optimization")
            elif content_type == "email":
                optimized_content = self._optimize_email_content(optimized_content)
                optimization_applied.append("email_optimization")
            
            # 5. Final length check and truncation if needed
            if len(optimized_content) > self.max_content_length:
                optimized_content = self._smart_truncate(optimized_content, self.max_content_length)
                optimization_applied.append("smart_truncation")
            
            optimized_length = len(optimized_content)
            compression_ratio = optimized_length / original_length if original_length > 0 else 1.0
            
            logger.info(f"Context optimization completed - Final length: {optimized_length}, Ratio: {compression_ratio:.2f}")
            
            return OptimizationResult(
                optimized_content=optimized_content,
                original_length=original_length,
                optimized_length=optimized_length,
                compression_ratio=compression_ratio,
                sections_removed=sections_removed,
                optimization_applied=optimization_applied
            )
            
        except Exception as e:
            logger.error(f"Context optimization failed: {e}")
            # Return original content on failure
            return OptimizationResult(
                optimized_content=content,
                original_length=len(content) if content else 0,
                optimized_length=len(content) if content else 0,
                compression_ratio=1.0,
                sections_removed=[],
                optimization_applied=["error_fallback"]
            )
    
    def _normalize_whitespace(self, content: str) -> str:
        """Normalize excessive whitespace"""
        # Remove multiple consecutive empty lines
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        # Remove trailing whitespace
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
        # Normalize spaces
        content = re.sub(r'[ \t]+', ' ', content)
        return content.strip()
    
    def _extract_sections(self, content: str) -> List[Dict[str, Any]]:
        """Extract logical sections from content"""
        sections = []
        
        # Split by common section patterns
        section_patterns = [
            r'^#+\s+(.+)$',  # Markdown headers
            r'^(.+):$',      # Colon-terminated headers
            r'^[-=]+$',      # Line separators
            r'^\d+\.\s+(.+)', # Numbered lists
            r'^[•*-]\s+(.+)'  # Bullet points
        ]
        
        lines = content.split('\n')
        current_section = {'title': 'Content', 'content': '', 'priority': 5, 'line_start': 0}
        
        for i, line in enumerate(lines):
            is_header = False
            
            for pattern in section_patterns:
                if re.match(pattern, line.strip(), re.MULTILINE):
                    # Save current section
                    if current_section['content'].strip():
                        sections.append(current_section)
                    
                    # Start new section
                    current_section = {
                        'title': line.strip(),
                        'content': '',
                        'priority': self._calculate_section_priority(line),
                        'line_start': i
                    }
                    is_header = True
                    break
            
            if not is_header:
                current_section['content'] += line + '\n'
        
        # Add final section
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections
    
    def _calculate_section_priority(self, section_title: str) -> int:
        """Calculate section priority (1=highest, 10=lowest)"""
        title_lower = section_title.lower()
        
        # Critical sections (priority 1-2)
        for pattern in self.critical_content_patterns:
            if re.search(pattern, title_lower):
                return 1
        
        # Important sections (priority 3-4)
        important_keywords = ['summary', '요약', 'problem', '문제', 'solution', '해결', 'result', '결과']
        for keyword in important_keywords:
            if keyword in title_lower:
                return 3
        
        # Standard sections (priority 5-6)
        standard_keywords = ['description', '설명', 'details', '상세', 'steps', '단계']
        for keyword in standard_keywords:
            if keyword in title_lower:
                return 5
        
        # Lower priority sections (priority 7-10)
        return 7
    
    def _prioritize_sections(self, sections: List[Dict[str, Any]], preserve_sections: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Prioritize sections for optimization"""
        if preserve_sections:
            for section in sections:
                for preserve in preserve_sections:
                    if preserve.lower() in section['title'].lower():
                        section['priority'] = 1  # Highest priority
        
        # Sort by priority
        return sorted(sections, key=lambda x: x['priority'])
    
    def _reconstruct_prioritized_content(self, sections: List[Dict[str, Any]], max_length: int) -> Tuple[str, List[str]]:
        """Reconstruct content with priority-based inclusion"""
        reconstructed = ""
        sections_removed = []
        
        for section in sections:
            section_content = f"{section['title']}\n{section['content']}\n"
            
            if len(reconstructed) + len(section_content) <= max_length:
                reconstructed += section_content
            else:
                # Try to fit partial content for important sections
                if section['priority'] <= 3:
                    remaining_space = max_length - len(reconstructed)
                    if remaining_space > 100:  # Minimum meaningful content
                        partial_content = section_content[:remaining_space-50] + "...\n"
                        reconstructed += partial_content
                        sections_removed.append(f"{section['title']} (partially)")
                else:
                    sections_removed.append(section['title'])
        
        return reconstructed.strip(), sections_removed
    
    def _optimize_ticket_content(self, content: str) -> str:
        """Apply ticket-specific optimizations"""
        # Remove common ticket system metadata
        content = re.sub(r'Ticket ID:.*?\n', '', content, flags=re.IGNORECASE)
        content = re.sub(r'Created:.*?\n', '', content, flags=re.IGNORECASE)
        content = re.sub(r'Updated:.*?\n', '', content, flags=re.IGNORECASE)
        content = re.sub(r'Priority:.*?\n', '', content, flags=re.IGNORECASE)
        
        # Condense repetitive status updates
        content = re.sub(r'(Status updated to .+?\n){2,}', 'Status updated multiple times\n', content)
        
        return content
    
    def _optimize_email_content(self, content: str) -> str:
        """Apply email-specific optimizations"""
        # Remove email headers
        content = re.sub(r'^From:.*?\n', '', content, flags=re.MULTILINE | re.IGNORECASE)
        content = re.sub(r'^To:.*?\n', '', content, flags=re.MULTILINE | re.IGNORECASE)
        content = re.sub(r'^Subject:.*?\n', '', content, flags=re.MULTILINE | re.IGNORECASE)
        content = re.sub(r'^Date:.*?\n', '', content, flags=re.MULTILINE | re.IGNORECASE)
        
        # Remove email signatures
        content = re.sub(r'\n--\s*\n.*$', '', content, flags=re.DOTALL)
        content = re.sub(r'\n___+\n.*$', '', content, flags=re.DOTALL)
        
        # Remove quoted text (replies)
        content = re.sub(r'\n>.*$', '', content, flags=re.MULTILINE)
        
        return content
    
    def _smart_truncate(self, content: str, max_length: int) -> str:
        """Intelligently truncate content while preserving structure"""
        if len(content) <= max_length:
            return content
        
        # Try to truncate at sentence boundaries
        sentences = content.split('.')
        truncated = ""
        
        for sentence in sentences:
            if len(truncated) + len(sentence) + 1 <= max_length - 20:  # Leave space for ellipsis
                truncated += sentence + '.'
            else:
                break
        
        if truncated:
            return truncated + "..."
        else:
            # Fallback: simple truncation
            return content[:max_length-3] + "..."
    
    def get_optimization_stats(self, result: OptimizationResult) -> Dict[str, Any]:
        """Get detailed optimization statistics"""
        return {
            'original_length': result.original_length,
            'optimized_length': result.optimized_length,
            'bytes_saved': result.original_length - result.optimized_length,
            'compression_ratio': result.compression_ratio,
            'compression_percentage': round((1 - result.compression_ratio) * 100, 1),
            'sections_removed_count': len(result.sections_removed),
            'sections_removed': result.sections_removed,
            'optimizations_applied': result.optimization_applied,
            'is_within_limits': result.optimized_length <= self.max_content_length
        }
