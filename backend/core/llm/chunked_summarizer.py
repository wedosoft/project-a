"""
Chunked Summarizer for handling very long content through multi-stage summarization.
"""
import logging
from typing import List, Dict, Optional
from .summarizer import LLMSummarizer

logger = logging.getLogger(__name__)

class ChunkedSummarizer:
    """Handles very long content by breaking it into chunks and summarizing in stages."""
    
    def __init__(self, base_summarizer: LLMSummarizer):
        self.base_summarizer = base_summarizer
        self.chunk_size = 15000  # Characters per chunk (leaving room for overlap)
        self.overlap_size = 1000  # Overlap between chunks to maintain context
        
    def summarize_long_content(self, content: str, content_type: str = "ticket") -> Optional[str]:
        """
        Summarize very long content using chunked approach.
        
        Args:
            content: The full content to summarize
            content_type: Type of content (ticket, conversation, etc.)
            
        Returns:
            Final summary or None if failed
        """
        try:
            # If content is short enough, use regular summarizer
            if len(content) <= 20000:
                return self.base_summarizer.generate_summary(content)
            
            logger.info(f"Content length {len(content)} exceeds limit, using chunked summarization")
            
            # Split into chunks
            chunks = self._split_into_chunks(content)
            logger.info(f"Split content into {len(chunks)} chunks")
            
            # Summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Summarizing chunk {i+1}/{len(chunks)} (length: {len(chunk)})")
                chunk_summary = self.base_summarizer.generate_summary(
                    chunk, 
                    f"Part {i+1} of {len(chunks)} of {content_type}"
                )
                if chunk_summary:
                    chunk_summaries.append(f"Part {i+1}: {chunk_summary}")
                else:
                    logger.warning(f"Failed to summarize chunk {i+1}")
            
            if not chunk_summaries:
                logger.error("Failed to summarize any chunks")
                return None
            
            # Combine chunk summaries into final summary
            combined_summary = "\n\n".join(chunk_summaries)
            
            # If combined summary is still too long, summarize it again
            if len(combined_summary) > 10000:
                logger.info("Combined summary too long, creating final summary")
                final_summary = self.base_summarizer.generate_summary(
                    combined_summary,
                    f"Final summary of {content_type} with {len(chunks)} parts"
                )
                return final_summary
            
            return combined_summary
            
        except Exception as e:
            logger.error(f"Error in chunked summarization: {e}")
            return None
    
    def _split_into_chunks(self, content: str) -> List[str]:
        """Split content into overlapping chunks."""
        chunks = []
        start = 0
        
        while start < len(content):
            # Calculate end position
            end = min(start + self.chunk_size, len(content))
            
            # If not the last chunk, try to find a good break point
            if end < len(content):
                # Look for sentence endings near the boundary
                search_start = max(end - 200, start + self.chunk_size // 2)
                search_end = min(end + 200, len(content))
                
                # Find the best break point (sentence end)
                break_points = []
                for i in range(search_start, search_end):
                    if content[i] in '.!?':
                        break_points.append(i + 1)
                    elif content[i] in '\n' and i < search_end - 1:
                        break_points.append(i + 1)
                
                if break_points:
                    # Choose break point closest to target end
                    end = min(break_points, key=lambda x: abs(x - end))
                
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = max(end - self.overlap_size, start + 1)
            
            # Safety check to prevent infinite loop
            if len(chunks) > 50:
                logger.warning("Too many chunks, truncating")
                break
        
        return chunks
    
    def analyze_conversation_structure(self, content: str) -> Dict[str, any]:
        """Analyze conversation structure to provide better context."""
        try:
            lines = content.split('\n')
            
            # Count different types of content
            email_headers = len([l for l in lines if l.startswith('From:') or l.startswith('Sent:')])
            conversation_parts = content.count('대화:')
            attachments = content.count('첨부파일:')
            
            # Estimate conversation length by participants
            participants = set()
            for line in lines:
                if 'From:' in line or '작성:' in line:
                    # Extract email or name
                    if '@' in line:
                        email_start = line.find('<')
                        email_end = line.find('>')
                        if email_start != -1 and email_end != -1:
                            participants.add(line[email_start+1:email_end])
            
            return {
                'total_length': len(content),
                'email_headers': email_headers,
                'conversation_parts': conversation_parts,
                'attachments': attachments,
                'estimated_participants': len(participants),
                'structure_type': 'email_thread' if email_headers > 0 else 'conversation'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing conversation structure: {e}")
            return {'total_length': len(content), 'structure_type': 'unknown'}
