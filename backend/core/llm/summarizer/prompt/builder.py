"""
프롬프트 빌더 - 템플릿 기반 프롬프트 생성
"""

import logging
from typing import Dict, Any, Optional
from jinja2 import Template, Environment, BaseLoader, TemplateNotFound
from .loader import get_prompt_loader

logger = logging.getLogger(__name__)


class PromptTemplateLoader(BaseLoader):
    """Jinja2용 커스텀 템플릿 로더"""
    
    def __init__(self):
        self.prompt_loader = get_prompt_loader()
    
    def get_source(self, environment, template):
        # 여기서는 사용하지 않음 (직접 템플릿 문자열 전달)
        raise TemplateNotFound(template)


class PromptBuilder:
    """프롬프트 빌더 - 템플릿과 데이터를 결합하여 최종 프롬프트 생성"""
    
    def __init__(self):
        self.prompt_loader = get_prompt_loader()
        self.jinja_env = Environment(loader=PromptTemplateLoader())
    
    def get_section_titles(self, ui_language: str = 'ko') -> Dict[str, str]:
        """UI 언어에 따른 섹션 타이틀 반환"""
        sections_data = self.prompt_loader.get_sections()
        return sections_data['sections'].get(ui_language, sections_data['sections']['ko'])
    
    def get_kb_section_titles(self, ui_language: str = 'ko') -> Dict[str, str]:
        """KB 문서용 섹션 타이틀 반환"""
        sections_data = self.prompt_loader.get_sections()
        return sections_data['kb_sections'].get(ui_language, sections_data['kb_sections']['ko'])
    
    def get_attachment_format(self, ui_language: str = 'ko') -> str:
        """첨부파일 형식 텍스트 반환"""
        sections_data = self.prompt_loader.get_sections()
        return sections_data['attachment_format'].get(ui_language, sections_data['attachment_format']['ko'])
    
    def build_system_prompt(
        self, 
        content_type: str, 
        content_language: str = "ko", 
        ui_language: str = "ko"
    ) -> str:
        """
        시스템 프롬프트 구성
        
        Args:
            content_type: 콘텐츠 타입 (ticket, knowledge_base, conversation)
            content_language: 콘텐츠 언어
            ui_language: UI 언어
            
        Returns:
            str: 완성된 시스템 프롬프트
        """
        try:
            # 템플릿 로드
            if content_type == "ticket":
                template_data = self.prompt_loader.get_system_prompt_template("ticket")
                sections = self.get_section_titles(ui_language)
                
                # 언어별 지시사항 선택
                language_instruction = template_data['language_instructions'].get(
                    content_language, 
                    template_data['language_instructions']['default']
                )
                
                # 첨부파일 포맷
                attachment_format = self.get_attachment_format(ui_language)
                
                # 프롬프트 구성
                base_instruction = template_data['base_instruction'].get(
                    ui_language, 
                    template_data['base_instruction']['ko']
                )
                
                requirements = '\n'.join([f"- {req}" for req in template_data['absolute_requirements']])
                forbidden = '\n'.join([f"- {item}" for item in template_data['strictly_forbidden']])
                formatting = template_data['formatting_rules'].get(
                    ui_language, 
                    template_data['formatting_rules']['ko']
                )
                
                return f"""{base_instruction}

CRITICAL MISSION: {template_data['critical_mission']}

ABSOLUTE REQUIREMENTS:
{requirements}

STRUCTURE YOUR SUMMARY:

{sections['problem']}
- Customer company and contact information (actual customer, NOT support agent)
- Technical issues or business requirements  
- Related products/services/systems (use exact names from original)
- Important dates, deadlines, urgency factors
- Customer's specific questions or concerns

{sections['cause']}
- Primary Cause: Main technical or business factor causing the issue
- Contributing Factors: Additional elements that led to or amplified the problem
- System Context: Changes in environment, policies, or setup
- Dependencies: External systems, services, or decisions that influenced the situation

{sections['solution']}
- Current Status: What stage the resolution is at right now
- Completed Actions: Date-specific actions taken and their results
- In Progress: What is currently being worked on
- Next Steps: Planned specific actions (with responsible party if mentioned)
- Expected Timeline: When full resolution is anticipated
- Verification: How success will be measured or confirmed

{sections['insights']}
- Technical Specifications: Settings, configurations, technical parameters
- Service Requirements: Limitations, dependencies, compatibility requirements
- Process Insights: Best practices, workflows, procedural knowledge
- Reference Materials: Mentioned documentation, tools, resources, and attachments
{attachment_format}
- Future Considerations: Recommendations for similar cases, preventive measures

STRICTLY FORBIDDEN:
{forbidden}

FORMATTING RULES:
- {language_instruction}
{formatting}"""
                
            elif content_type == "knowledge_base":
                # KB 문서용 시스템 프롬프트 (기존 로직 유지)
                return self._build_kb_system_prompt(content_language, ui_language)
                
            else:  # conversation type
                # 대화 분석용 시스템 프롬프트 (기존 로직 유지)
                return self._build_conversation_system_prompt(content_language, ui_language)
                
        except Exception as e:
            logger.error(f"Failed to build system prompt for {content_type}: {e}")
            # 폴백: 기존 방식으로 생성
            return self._fallback_system_prompt(content_type, content_language, ui_language)
    
    def build_user_prompt(
        self,
        content: str,
        content_type: str,
        subject: str,
        metadata: Dict[str, Any],
        content_language: str,
        ui_language: str
    ) -> str:
        """
        사용자 프롬프트 구성
        
        Args:
            content: 분석할 내용
            content_type: 콘텐츠 타입
            subject: 제목
            metadata: 메타데이터
            content_language: 콘텐츠 언어
            ui_language: UI 언어
            
        Returns:
            str: 완성된 사용자 프롬프트
        """
        try:
            template_data = self.prompt_loader.get_user_prompt_template(content_type)
            
            # 메타데이터 포맷팅
            metadata_formatted = ""
            if metadata:
                formatted_metadata = []
                
                # 첨부파일 정보 특별 처리 - 관련성이 높은 1-3개만 선택
                if 'attachments' in metadata or 'all_attachments' in metadata:
                    attachments = metadata.get('attachments') or metadata.get('all_attachments') or []
                    if attachments and isinstance(attachments, list):
                        # 여기서 첨부파일 선별 로직 호출 (나중에 attachment 모듈에서)
                        from ..attachment.selector import select_relevant_attachments
                        relevant_attachments = select_relevant_attachments(attachments, content, subject)
                        if relevant_attachments:
                            att_names = [att.get('name', 'Unknown') for att in relevant_attachments]
                            formatted_metadata.append(f"relevant_attachments: {', '.join(att_names)}")
                
                # 기타 메타데이터 처리
                for k, v in metadata.items():
                    if k not in ['attachments', 'all_attachments'] and v:
                        formatted_metadata.append(f"{k}: {v}")
                
                if formatted_metadata:
                    metadata_formatted = "; ".join(formatted_metadata)
            
            # 지시사항 선택
            instruction_text = template_data['instructions'].get(
                ui_language, 
                template_data['instructions']['ko']
            )
            
            # Jinja2 템플릿 렌더링
            template = self.jinja_env.from_string(template_data['template'])
            
            return template.render(
                subject=subject if subject else None,
                metadata_formatted=metadata_formatted if metadata_formatted else None,
                content=content,
                instruction_text=instruction_text
            )
            
        except Exception as e:
            logger.error(f"Failed to build user prompt for {content_type}: {e}")
            # 폴백: 기존 방식으로 생성
            return self._fallback_user_prompt(content, content_type, subject, metadata, content_language, ui_language)
    
    def _build_kb_system_prompt(self, content_language: str, ui_language: str) -> str:
        """KB 문서용 시스템 프롬프트 (기존 로직 유지)"""
        # 여기서는 기존 _get_optimized_system_prompt의 KB 로직을 그대로 사용
        kb_sections = self.get_kb_section_titles(ui_language)
        
        language_instruction = {
            "ko": "한국어로만 응답하세요",
            "en": "영어로만 응답하세요", 
            "ja": "일본어로만 응답하세요",
            "zh": "중국어로만 응답하세요"
        }.get(content_language, "원문과 동일한 언어로 응답하세요")
        
        return f"""You are a knowledge management specialist creating comprehensive summaries of knowledge base documents for customer service teams.

CRITICAL MISSION: Create well-structured summaries that help agents quickly understand and apply the knowledge.

ABSOLUTE REQUIREMENTS:
1. PRESERVE all step-by-step procedures exactly as written
2. INCLUDE all technical specifications and parameters
3. MAINTAIN exact terminology and product names
4. PRESERVE all prerequisites and limitations
5. Use EXACT terminology from original content:
   - Technical terms: Use the EXACT terms from the original text
   - Product names: Use the EXACT names as mentioned in original text
   - Always preserve exact URLs, file paths, and system names

STRUCTURE YOUR SUMMARY:

{kb_sections['purpose']}
- What this document covers and its intended use
- Target audience and applicable scenarios
- Key outcomes or objectives

{kb_sections['procedure']}
- Step-by-step instructions in exact order
- Required actions and expected results
- Decision points and alternative paths
- Verification steps and success criteria

{kb_sections['requirements']}
- System requirements and dependencies
- Required permissions or access levels
- Necessary tools, software, or resources
- Environmental or configuration prerequisites

{kb_sections['technical']}
- Technical specifications and parameters
- Configuration settings and values
- Integration points and APIs
- Troubleshooting guidelines and common issues

FORMATTING RULES:
- {language_instruction}
- Preserve exact technical terminology from original
- Maintain numbered lists and bullet points from source
- Include all URLs, file paths, and system identifiers exactly
- Keep procedures actionable and clear"""
    
    def _build_conversation_system_prompt(self, content_language: str, ui_language: str) -> str:
        """대화 분석용 시스템 프롬프트 (기존 로직 유지)"""
        language_instruction = {
            "ko": "한국어로만 응답하세요",
            "en": "영어로만 응답하세요",
            "ja": "일본어로만 응답하세요", 
            "zh": "중국어로만 응답하세요"
        }.get(content_language, "원문과 동일한 언어로 응답하세요")
        
        return f"""You are a conversation analyst. Summarize customer service conversations focusing on:
- Key issues discussed
- Solutions provided
- Customer feedback and satisfaction
- Action items and follow-ups

FORMATTING RULES:
- {language_instruction}
- Maintain chronological flow and preserve important details
- Preserve exact technical terms and product names
- Include all mentioned dates, times, and deadlines"""
    
    def _fallback_system_prompt(self, content_type: str, content_language: str, ui_language: str) -> str:
        """폴백 시스템 프롬프트"""
        logger.warning(f"Using fallback system prompt for {content_type}")
        return f"""You are a {content_type} analysis specialist. Create accurate summaries preserving all key information."""
    
    def _fallback_user_prompt(self, content: str, content_type: str, subject: str, metadata: Dict[str, Any], content_language: str, ui_language: str) -> str:
        """폴백 사용자 프롬프트"""
        logger.warning(f"Using fallback user prompt for {content_type}")
        prompt_parts = []
        
        if subject:
            prompt_parts.append(f"SUBJECT: {subject}")
        
        prompt_parts.append("CONTENT TO ANALYZE:")
        prompt_parts.append("=" * 50)
        prompt_parts.append(content)
        prompt_parts.append("=" * 50)
        prompt_parts.append("Please analyze the content above and create a comprehensive summary.")
        
        return "\n\n".join(prompt_parts)


# 전역 빌더 인스턴스
_prompt_builder = None


def get_prompt_builder() -> PromptBuilder:
    """프롬프트 빌더 싱글톤 인스턴스 반환"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
