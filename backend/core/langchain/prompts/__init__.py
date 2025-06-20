"""
프롬프트 모듈 - Langchain PromptTemplate 기반

기존 llm_router.py의 프롬프트들을 langchain 구조로 분리
"""

from .ticket_prompts import (
    PromptTemplates,
    prompt_templates,
    TICKET_SUMMARY_SYSTEM_PROMPT,
    TICKET_SUMMARY_HUMAN_PROMPT,
    ISSUE_SOLUTION_SYSTEM_PROMPT,
    ISSUE_SOLUTION_HUMAN_PROMPT,
    DEFAULT_SYSTEM_PROMPT
)

__all__ = [
    "PromptTemplates",
    "prompt_templates",
    "TICKET_SUMMARY_SYSTEM_PROMPT", 
    "TICKET_SUMMARY_HUMAN_PROMPT",
    "ISSUE_SOLUTION_SYSTEM_PROMPT",
    "ISSUE_SOLUTION_HUMAN_PROMPT",
    "DEFAULT_SYSTEM_PROMPT"
]
