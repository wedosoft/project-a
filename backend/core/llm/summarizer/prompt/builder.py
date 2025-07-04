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
                sections = self.get_section_titles(ui_language)  # 섹션 구조 추가
                
                # 일반 ticket 템플릿 처리 (구조화된 섹션 추가)
                language_instruction = template_data['language_instructions'].get(
                    content_language, 
                    template_data['language_instructions']['default']
                )
                
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
- 고객사 및 담당자 정보
- 기술적 문제 또는 비즈니스 요구사항
- 관련 제품/서비스/시스템 (원문의 정확한 명칭 사용)
- 중요한 날짜, 데드라인, 긴급도 요소

{sections['cause']}
- 주요 원인: 문제를 야기한 주된 기술적 또는 비즈니스 요인
- 기여 요소: 문제로 이어지거나 증폭시킨 추가 요소들

{sections['solution']}
- 현재 상태: 해결이 현재 어느 단계에 있는지
- 완료된 조치: 날짜별 구체적 조치와 그 결과
- 다음 단계: 계획된 구체적 조치

{sections['insights']}
- 기술적 사양: 설정, 구성, 기술적 매개변수
- 프로세스 인사이트: 모범 사례, 워크플로우, 절차적 지식

STRICTLY FORBIDDEN:
{forbidden}

FORMATTING RULES:
- {language_instruction}
{formatting}"""
                
            elif content_type == "ticket_view":
                template_data = self.prompt_loader.get_system_prompt_template("ticket_view")
                sections = self.get_section_titles(ui_language)
                
                # 언어별 지시사항 선택 (UI 언어에 따라 결정)
                language_instruction = template_data['language_instructions'].get(
                    ui_language, 
                    template_data['language_instructions']['default']
                )
                
                # 첨부파일 포맷 (UI 언어에 따라 선택)
                attachment_format = self.get_attachment_format(ui_language)
                
                # 프롬프트 구성 (UI 언어에 따라 선택 - 언어 일관성 보장)
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
                
                # 언어별 서브타이틀 정의
                if ui_language == 'ko':
                    problem_subtitles = """- 고객사 및 담당자 정보 (실제 고객, 지원 담당자 아님)
- 기술적 문제 또는 비즈니스 요구사항
- 관련 제품/서비스/시스템 (원문의 정확한 명칭 사용)
- 중요한 날짜, 데드라인, 긴급도 요소
- 고객의 구체적인 질문이나 우려사항"""

                    cause_subtitles = """- 주요 원인: 문제를 야기한 주된 기술적 또는 비즈니스 요인
- 기여 요소: 문제로 이어지거나 증폭시킨 추가 요소들
- 시스템 상황: 환경, 정책, 설정의 변화
- 의존성: 상황에 영향을 준 외부 시스템, 서비스, 결정"""

                    solution_subtitles = """- 현재 상태: 해결이 현재 어느 단계에 있는지
- 완료된 조치: 날짜별 구체적 조치와 그 결과
- 진행 중: 현재 작업 중인 내용
- 다음 단계: 계획된 구체적 조치 (담당자 언급 시 포함)
- 예상 일정: 완전한 해결이 예상되는 시기
- 검증: 성공을 측정하거나 확인하는 방법"""

                    insights_subtitles = """- 기술 사양: 설정, 구성, 기술적 매개변수
- 서비스 요구사항: 제한사항, 의존성, 호환성 요구사항
- 프로세스 인사이트: 모범 사례, 워크플로우, 절차적 지식
- 향후 고려사항: 유사 케이스 권장사항, 예방 조치"""
                else:
                    problem_subtitles = """- Customer company and contact information (actual customer, NOT support agent)
- Technical issues or business requirements  
- Related products/services/systems (use exact names from original)
- Important dates, deadlines, urgency factors
- Customer's specific questions or concerns"""

                    cause_subtitles = """- Primary Cause: Main technical or business factor causing the issue
- Contributing Factors: Additional elements that led to or amplified the problem
- System Context: Changes in environment, policies, or setup
- Dependencies: External systems, services, or decisions that influenced the situation"""

                    solution_subtitles = """- Current Status: What stage the resolution is at right now
- Completed Actions: Date-specific actions taken and their results
- In Progress: What is currently being worked on
- Next Steps: Planned specific actions (with responsible party if mentioned)
- Expected Timeline: When full resolution is anticipated
- Verification: How success will be measured or confirmed"""

                    insights_subtitles = """- Technical Specifications: Settings, configurations, technical parameters
- Service Requirements: Limitations, dependencies, compatibility requirements
- Process Insights: Best practices, workflows, procedural knowledge
- Future Considerations: Recommendations for similar cases, preventive measures"""

                return f"""{base_instruction}

CRITICAL MISSION: {template_data['critical_mission']}

ABSOLUTE REQUIREMENTS:
{requirements}

STRUCTURE YOUR SUMMARY:

{sections['problem']}
{problem_subtitles}

{sections['cause']}
{cause_subtitles}

{sections['solution']}
{solution_subtitles}

{sections['insights']}
{insights_subtitles}

STRICTLY FORBIDDEN:
{forbidden}

FORMATTING RULES:
- {language_instruction}
{formatting}"""
                
            # knowledge_base 템플릿 사용 제거됨 - 아티클은 요약하지 않음
            # elif content_type == "knowledge_base":
            #     # KB 문서용 시스템 프롬프트 (기존 로직 유지)
            #     return self._build_kb_system_prompt(content_language, ui_language)
                
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
            
            # 메타데이터 포맷팅 (확장된 필드 활용)
            metadata_formatted = ""
            if metadata:
                formatted_metadata = []
                
                # 핵심 비즈니스 정보 우선 표시
                if metadata.get('company_name'):
                    formatted_metadata.append(f"고객사: {metadata['company_name']}")
                
                if metadata.get('customer_email'):
                    formatted_metadata.append(f"고객 연락처: {metadata['customer_email']}")
                
                if metadata.get('agent_name'):
                    formatted_metadata.append(f"담당자: {metadata['agent_name']}")
                
                if metadata.get('department'):
                    formatted_metadata.append(f"부서: {metadata['department']}")
                
                if metadata.get('ticket_category'):
                    formatted_metadata.append(f"카테고리: {metadata['ticket_category']}")
                
                if metadata.get('complexity_level'):
                    formatted_metadata.append(f"복잡도: {metadata['complexity_level']}")
                
                if metadata.get('product_version'):
                    formatted_metadata.append(f"제품 버전: {metadata['product_version']}")
                
                # 첨부파일 정보는 메타데이터에서 제외 (참고 자료 섹션에서 처리됨)
                # if 'attachments' in metadata or 'all_attachments' in metadata:
                #     ... (첨부파일 처리 로직 제거 - 참고 자료 섹션에서만 처리)
                
                
                # 기타 중요 메타데이터 처리 (첨부파일 관련 필드 제외)
                for k, v in metadata.items():
                    if k not in ['attachments', 'all_attachments', 'company_name', 'customer_email', 
                               'agent_name', 'department', 'ticket_category', 'complexity_level', 
                               'product_version', 'attachment_types', 'has_attachments', 
                               'has_image_attachments', 'has_document_attachments', 'large_attachments'] and v:
                        if k in ['priority', 'status', 'created_at', 'escalation_count']:
                            formatted_metadata.append(f"{k}: {v}")
                
                if formatted_metadata:
                    metadata_formatted = "; ".join(formatted_metadata)
            
            # 지시사항 선택 (모든 요약을 UI 언어로 통일)
            instruction_text = template_data['instructions'].get(
                ui_language, 
                template_data['instructions']['ko']
            )
            
            # 첨부파일 정보 생성 (LLM 선별된 첨부파일 우선 사용)
            attachment_summary = ""
            if metadata:
                # 1순위: LLM 선별된 첨부파일 (relevant_attachments)
                relevant_attachments = metadata.get('relevant_attachments', [])
                if relevant_attachments:
                    attachment_list = []
                    for attachment in relevant_attachments:
                        if isinstance(attachment, dict):
                            name = attachment.get("name", "unknown")
                            size = attachment.get("size", 0)
                            content_type = attachment.get("content_type", "")
                            
                            # 파일 타입별 이모지 선택
                            emoji = self._get_file_emoji(name, content_type)
                            
                            if size > 0:
                                size_mb = round(size / (1024*1024), 2)
                                attachment_list.append(f"{emoji} {name} ({size_mb}MB)")
                            else:
                                attachment_list.append(f"{emoji} {name}")
                    
                    if attachment_list:
                        # 각 파일을 한 줄씩 표시 (이쁜 형태로)
                        formatted_attachments = [f"- {attachment}" for attachment in attachment_list]
                        attachment_summary = "\n".join(formatted_attachments)
                        logger.debug(f"LLM 선별된 첨부파일 사용: {len(attachment_list)}개")
                
                # 2순위: 기존 attachment_summary (폴백)
                if not attachment_summary and metadata.get('attachment_summary'):
                    attachment_summary = metadata['attachment_summary']
                    logger.debug("기존 attachment_summary 사용")
            
            # Jinja2 템플릿 렌더링
            template = self.jinja_env.from_string(template_data['template'])
            
            # content 검증 및 기본값 설정
            safe_content = content if content and content.strip() else "티켓 내용을 찾을 수 없습니다."
            safe_subject = subject if subject and subject.strip() else "제목 없음"
            safe_metadata = metadata_formatted if metadata_formatted and metadata_formatted.strip() else "메타데이터 없음"
            safe_attachment_summary = attachment_summary if attachment_summary and attachment_summary.strip() else ""
            
            user_prompt = template.render(
                subject=safe_subject,
                metadata_formatted=safe_metadata,
                content=safe_content,
                instruction_text=instruction_text,
                attachment_summary=safe_attachment_summary
            )
            
            # 생성된 프롬프트 검증
            if not user_prompt or user_prompt.strip() == "":
                logger.error(f"Generated empty user prompt for content_type: {content_type}")
                raise ValueError(f"Empty user prompt generated for {content_type}")
                
            return user_prompt
            
        except Exception as e:
            logger.error(f"Failed to build user prompt for {content_type}: {e}")
            # 폴백: 기존 방식으로 생성
            return self._fallback_user_prompt(content, content_type, subject, metadata, content_language, ui_language)
    
    def _get_file_emoji(self, filename: str, content_type: str = "") -> str:
        """파일 타입별 이모지 반환"""
        filename_lower = filename.lower()
        
        # 이미지 파일
        if any(ext in filename_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']):
            return '🖼️'
        # 문서 파일
        elif any(ext in filename_lower for ext in ['.pdf', '.doc', '.docx']):
            return '📄'
        # 스프레드시트
        elif any(ext in filename_lower for ext in ['.xlsx', '.xls', '.csv']):
            return '📊'
        # 텍스트 파일
        elif any(ext in filename_lower for ext in ['.txt', '.log', '.md']):
            return '📋'
        # 압축 파일
        elif any(ext in filename_lower for ext in ['.zip', '.rar', '.7z', '.tar']):
            return '🗂️'
        # 기타
        else:
            return '📎'
    
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

    def build_enhanced_system_prompt(
        self, 
        content_type: str, 
        content_language: str = "ko", 
        ui_language: str = "ko"
    ) -> str:
        """
        품질 향상을 위한 강화된 시스템 프롬프트 구성
        
        Args:
            content_type: 콘텐츠 타입 (ticket, knowledge_base, conversation)
            content_language: 콘텐츠 언어
            ui_language: UI 언어
            
        Returns:
            str: 강화된 시스템 프롬프트
        """
        try:
            # 기본 시스템 프롬프트에 품질 강화 요소 추가
            base_prompt = self.build_system_prompt(content_type, content_language, ui_language)
            
            quality_enhancement = """

품질 강화 지침:
- 원문의 모든 핵심 정보 포함 필수
- 구체적이고 실행 가능한 내용으로 작성
- 추상적이거나 모호한 표현 금지
- 5개 섹션 구조 엄격히 준수
- 첨부파일 정보 정확히 반영"""
            
            if ui_language == "en":
                quality_enhancement = """

Quality Enhancement Guidelines:
- Include ALL key information from original text
- Write specific and actionable content
- Avoid abstract or vague expressions
- Strictly follow 5-section structure
- Accurately reflect attachment information"""
            
            return base_prompt + quality_enhancement
            
        except Exception as e:
            logger.warning(f"Enhanced system prompt 생성 실패, 기본 프롬프트 사용: {e}")
            return self.build_system_prompt(content_type, content_language, ui_language)


# 전역 빌더 인스턴스
_prompt_builder = None


def get_prompt_builder() -> PromptBuilder:
    """프롬프트 빌더 싱글톤 인스턴스 반환"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
