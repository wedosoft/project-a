"""
프롬프트 템플릿 모듈 - Langchain PromptTemplate 기반

기존 llm_router_legacy.py의 프롬프트들을 langchain PromptTemplate으로 구조화
90%+ 기존 코드 재활용 원칙에 따라 기존 프롬프트 텍스트 보존
"""

from langchain_core.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from typing import Dict, Any, List

# 티켓 요약용 시스템 프롬프트 (기존 코드 재활용)
TICKET_SUMMARY_SYSTEM_PROMPT = """티켓 정보를 분석하여 간결한 마크다운 요약을 작성하세요. 최대 500자 이내로 작성해주세요:

## 📋 상황 요약
[핵심 문제와 현재 상태를 1-2줄로 요약]

## 🔍 주요 내용
- 문제: [구체적인 문제]
- 요청: [고객이 원하는 것]
- 조치: [필요한 조치]

## 💡 핵심 포인트
1. [가장 중요한 포인트]
2. [두 번째 중요한 포인트]

참고: 간결하고 명확하게 작성하되, 핵심 정보는 누락하지 마세요."""

# 티켓 요약용 휴먼 프롬프트 (기존 코드 재활용)
TICKET_SUMMARY_HUMAN_PROMPT = """다음 티켓 정보를 분석해주세요:

{prompt_context}"""

# Issue/Solution 분석용 시스템 프롬프트 (기존 코드 재활용)
ISSUE_SOLUTION_SYSTEM_PROMPT = """당신은 고객 지원 티켓을 분석하는 AI입니다. 
제공된 티켓 정보를 바탕으로 문제 상황(Issue)과 해결책(Solution)을 구분해서 분석해주세요. 
정확히 다음 JSON 형식으로만 응답하세요:

{{"issue": "구체적인 문제 상황", "solution": "해결책 또는 조치사항"}}

다른 설명이나 텍스트를 추가하지 말고 오직 위의 JSON 형식만 반환하세요."""

# Issue/Solution 분석용 휴먼 프롬프트 (기존 코드 재활용)
ISSUE_SOLUTION_HUMAN_PROMPT = """다음 티켓 정보를 분석하여 문제 상황(Issue)과 해결책(Solution)을 JSON 형식으로 제공해주세요:

제목: {subject}
설명: {description}
상태: {status}
우선순위: {priority}{conversation_text}"""

# 기본 시스템 프롬프트 (기존 코드 재활용)
DEFAULT_SYSTEM_PROMPT = "당신은 친절한 고객 지원 AI입니다."

class PromptTemplates:
    """프롬프트 템플릿 관리 클래스 - 기존 코드 90%+ 재활용"""
    
    def __init__(self):
        """기존 프롬프트들을 langchain 템플릿으로 초기화"""
        
        # 티켓 요약 프롬프트 템플릿
        self.ticket_summary_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(TICKET_SUMMARY_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(TICKET_SUMMARY_HUMAN_PROMPT)
        ])
        
        # Issue/Solution 분석 프롬프트 템플릿
        self.issue_solution_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(ISSUE_SOLUTION_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(ISSUE_SOLUTION_HUMAN_PROMPT)
        ])
        
        # 기본 프롬프트 템플릿
        self.default_prompt = PromptTemplate(
            input_variables=["user_input"],
            template="{user_input}"
        )
        
        # 시스템 프롬프트 템플릿
        self.system_prompt = PromptTemplate(
            input_variables=["system_message"],
            template="{system_message}"
        )
    
    def get_ticket_summary_prompt(self, prompt_context: str) -> ChatPromptTemplate:
        """
        티켓 요약 프롬프트 생성 (기존 generate_ticket_summary 로직 재활용)
        
        Args:
            prompt_context: 티켓 컨텍스트 (제목, 설명, 대화 등)
            
        Returns:
            ChatPromptTemplate: 포맷된 프롬프트 템플릿
        """
        return self.ticket_summary_prompt.format_messages(
            prompt_context=prompt_context
        )
    
    def get_issue_solution_prompt(
        self, 
        subject: str, 
        description: str, 
        status: str, 
        priority: str, 
        conversation_text: str = ""
    ) -> ChatPromptTemplate:
        """
        Issue/Solution 분석 프롬프트 생성 (기존 analyze_ticket_issue_solution 로직 재활용)
        
        Args:
            subject: 티켓 제목
            description: 티켓 설명
            status: 티켓 상태
            priority: 티켓 우선순위
            conversation_text: 대화 내용
            
        Returns:
            ChatPromptTemplate: 포맷된 프롬프트 템플릿
        """
        return self.issue_solution_prompt.format_messages(
            subject=subject,
            description=description,
            status=status,
            priority=priority,
            conversation_text=conversation_text
        )
    
    def get_default_prompt(self, user_input: str, system_message: str = None) -> List[Dict[str, str]]:
        """
        기본 프롬프트 생성 (기존 generate 메서드 호환)
        
        Args:
            user_input: 사용자 입력
            system_message: 시스템 메시지 (선택적)
            
        Returns:
            List[Dict[str, str]]: 메시지 리스트
        """
        messages = []
        
        # 시스템 메시지 추가
        if system_message:
            messages.append({"role": "system", "content": system_message})
        else:
            messages.append({"role": "system", "content": DEFAULT_SYSTEM_PROMPT})
        
        # 사용자 메시지 추가
        messages.append({"role": "user", "content": user_input})
        
        return messages

# 전역 프롬프트 템플릿 인스턴스
prompt_templates = PromptTemplates()
