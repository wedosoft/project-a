"""
Agent-related utility functions for summarization
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def determine_agent_ui_language(
    agent_profile: Optional[Dict[str, Any]] = None, 
    company_settings: Optional[Dict[str, Any]] = None
) -> str:
    """
    에이전트 UI 언어 결정 우선순위:
    1. 에이전트 개인 설정 (agent.profile.language)
    2. 회사 기본 언어 (company.default_language) 
    3. 시스템 기본값 ('ko')
    
    Args:
        agent_profile: 에이전트 프로필 정보
        company_settings: 회사 설정 정보
        
    Returns:
        str: 결정된 UI 언어 ('ko' 또는 'en')
    """
    supported_languages = ['ko', 'en']
    
    # 1순위: 에이전트 개인 설정
    if agent_profile and isinstance(agent_profile, dict):
        agent_lang = agent_profile.get('language') or agent_profile.get('ui_language')
        if agent_lang in supported_languages:
            logger.debug(f"에이전트 개인 언어 설정 사용: {agent_lang}")
            return agent_lang
    
    # 2순위: 회사 기본 언어
    if company_settings and isinstance(company_settings, dict):
        company_lang = company_settings.get('default_language') or company_settings.get('ui_language')
        if company_lang in supported_languages:
            logger.debug(f"회사 기본 언어 설정 사용: {company_lang}")
            return company_lang
    
    # 3순위: 시스템 기본값
    logger.debug("시스템 기본 언어 사용: ko")
    return 'ko'


def translate_section_titles(summary_markdown: str, target_ui_language: str) -> str:
    """
    기존 요약의 섹션 타이틀을 대상 UI 언어로 실시간 변환
    
    Args:
        summary_markdown: 원본 마크다운 요약
        target_ui_language: 대상 UI 언어 ('ko' 또는 'en')
        
    Returns:
        str: 섹션 타이틀이 번역된 요약
    """
    if not summary_markdown or not summary_markdown.strip():
        return summary_markdown
    
    # 번역 매핑 테이블
    translations = {
        'ko_to_en': {
            '🔍 **문제 상황**': '🔍 **Problem Analysis**',
            '🎯 **근본 원인**': '🎯 **Root Cause**',
            '🔧 **해결 과정**': '🔧 **Solution Process**',
            '💡 **핵심 포인트**': '💡 **Key Insights**',
            # KB 문서용 섹션 타이틀
            '📚 **문서 개요**': '📚 **Document Overview**',
            '🎯 **적용 시나리오**': '🎯 **Application Scenarios**',
            '🔧 **핵심 해결 방법**': '🔧 **Core Resolution Methods**',
            '⚠️ **주의사항**': '⚠️ **Important Precautions**',
            '🏷️ **문서 특성**': '🏷️ **Document Characteristics**',
            '💡 **상담원 활용 팁**': '💡 **Agent Utilization Tips**',
            # 대화 분석용 섹션 타이틀
            '💬 **대화 흐름 요약**': '💬 **Conversation Flow Summary**',
            '✅ **해결된 사항**': '✅ **Resolved Items**',
            '❓ **미해결 사항**': '❓ **Pending Issues**',
            '🔄 **후속 조치**': '🔄 **Follow-up Actions**',
            '📋 **상담원 체크리스트**': '📋 **Agent Checklist**'
        },
        'en_to_ko': {
            '🔍 **Problem Analysis**': '🔍 **문제 상황**',
            '🎯 **Root Cause**': '🎯 **근본 원인**',
            '🔧 **Solution Process**': '🔧 **해결 과정**',
            '💡 **Key Insights**': '💡 **핵심 포인트**',
            # KB 문서용 섹션 타이틀 (영어→한국어)
            '📚 **Document Overview**': '📚 **문서 개요**',
            '🎯 **Application Scenarios**': '🎯 **적용 시나리오**',
            '🔧 **Core Resolution Methods**': '🔧 **핵심 해결 방법**',
            '⚠️ **Important Precautions**': '⚠️ **주의사항**',
            '🏷️ **Document Characteristics**': '🏷️ **문서 특성**',
            '💡 **Agent Utilization Tips**': '💡 **상담원 활용 팁**',
            # 대화 분석용 섹션 타이틀 (영어→한국어)
            '💬 **Conversation Flow Summary**': '💬 **대화 흐름 요약**',
            '✅ **Resolved Items**': '✅ **해결된 사항**',
            '❓ **Pending Issues**': '❓ **미해결 사항**',
            '🔄 **Follow-up Actions**': '🔄 **후속 조치**',
            '📋 **Agent Checklist**': '📋 **상담원 체크리스트**'
        }
    }
    
    result_markdown = summary_markdown
    
    # 패턴 매칭으로 실시간 변환
    if target_ui_language == 'en':
        # 한국어 → 영어 변환
        for ko_title, en_title in translations['ko_to_en'].items():
            result_markdown = result_markdown.replace(ko_title, en_title)
    elif target_ui_language == 'ko':
        # 영어 → 한국어 변환  
        for en_title, ko_title in translations['en_to_ko'].items():
            result_markdown = result_markdown.replace(en_title, ko_title)
    
    return result_markdown


async def get_agent_localized_summary(
    ticket_id: str,
    original_summary: str,
    agent_profile: Optional[Dict[str, Any]] = None,
    company_settings: Optional[Dict[str, Any]] = None
) -> str:
    """
    에이전트 UI 언어에 맞춰 현지화된 요약 반환
    
    Args:
        ticket_id: 티켓 ID (캐싱용)
        original_summary: 원본 요약 마크다운
        agent_profile: 에이전트 프로필 정보
        company_settings: 회사 설정 정보
        
    Returns:
        str: 현지화된 요약
    """
    try:
        # 에이전트 UI 언어 결정
        agent_ui_language = determine_agent_ui_language(agent_profile, company_settings)
        
        # 원본이 이미 해당 언어인 경우 그대로 반환
        if agent_ui_language == 'ko' and '**문제 상황**' in original_summary:
            return original_summary
        elif agent_ui_language == 'en' and '**Problem Analysis**' in original_summary:
            return original_summary
        
        # 섹션 타이틀 번역
        localized_summary = translate_section_titles(original_summary, agent_ui_language)
        
        logger.debug(f"티켓 {ticket_id} 요약 현지화 완료 (언어: {agent_ui_language})")
        return localized_summary
        
    except Exception as e:
        logger.error(f"요약 현지화 중 오류 (ticket_id: {ticket_id}): {e}")
        return original_summary  # 실패 시 원본 반환
