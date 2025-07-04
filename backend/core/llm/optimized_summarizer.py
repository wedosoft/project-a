"""
LEGACY MODULE - DEPRECATED

This module is being phased out in favor of the new modular summarizer system.

NEW SYSTEM LOCATION: backend.core.llm.summarizer

MIGRATION GUIDE:
- Old: from backend.core.llm.optimized_summarizer import generate_optimized_summary
- New: from backend.core.llm.summarizer import generate_optimized_summary

MODULAR COMPONENTS:
- CoreSummarizer: Main summarization logic
- PromptBuilder: Template-based prompt generation  
- AttachmentSelector: LLM-based attachment selection
- QualityValidator: Multi-dimensional quality assessment
- ContextOptimizer: Content size optimization
- EmailProcessor: Email-specific processing
- HybridSummarizer: Large content adaptive strategies
- LanguageDetector: Advanced language detection

For new development, use the modular system directly.
This file provides backward compatibility wrappers only.

Last updated: 2025-06-25
"""

import logging
import re
import hashlib
import warnings
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Set, List, Union
from .manager import LLMManager
from .models.base import LLMProvider

logger = logging.getLogger(__name__)

# Issue deprecation warning when module is imported
warnings.warn(
    "optimized_summarizer module is deprecated. Use 'backend.core.llm.summarizer' instead.",
    DeprecationWarning,
    stacklevel=2
)

# 전역 LLM 매니저 인스턴스
llm_manager = LLMManager()


def detect_content_language(content: str) -> str:
    """
    DEPRECATED - Use LanguageDetector from summarizer.utils instead
    
    This function is maintained for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "detect_content_language is deprecated. Use LanguageDetector from summarizer.utils instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from .summarizer.utils import detect_content_language as new_detect_language
    return new_detect_language(content)
    if not content or len(content.strip()) < 10:
        return 'ko'  # 기본값
    
    # 문자 개수 계산 (공백, 줄바꿈, 특수문자 등 제외)
    content_clean = re.sub(r'[^\w\s가-힣ひらがなカタカナぁ-ゖァ-ヶ一-龯a-zA-Z]', '', content)
    total_chars = len(content_clean.replace(' ', '').replace('\n', ''))
    if total_chars == 0:
        return 'ko'
    
    korean_chars = len(re.findall(r'[가-힣]', content))
    japanese_chars = len(re.findall(r'[ひらがなカタカナ]', content)) + len(re.findall(r'[ぁ-ゖ]', content)) + len(re.findall(r'[ァ-ヶ]', content))
    chinese_chars = len(re.findall(r'[一-龯]', content))
    english_chars = len(re.findall(r'[a-zA-Z]', content))
    
    # 비율 계산
    korean_ratio = korean_chars / total_chars
    japanese_ratio = japanese_chars / total_chars
    chinese_ratio = chinese_chars / total_chars
    english_ratio = english_chars / total_chars
    
    # 언어 결정
    if korean_ratio > 0.1:  # 10% 이상이면 한국어
        return 'ko'
    elif japanese_ratio > 0.1:
        return 'ja'  
    elif chinese_ratio > 0.1:
        return 'zh'
    elif english_ratio > 0.5:  # 영어는 50% 이상이어야 인정
        return 'en'
    else:
        # 혼합 언어의 경우 가장 높은 비율로 결정하되, 한국어 우선
        ratios = {
            'ko': korean_ratio,
            'ja': japanese_ratio, 
            'zh': chinese_ratio,
            'en': english_ratio
        }
        max_lang = max(ratios, key=ratios.get)
        return max_lang if max_lang != 'en' or ratios['en'] > 0.3 else 'ko'


def get_section_titles(ui_language: str = 'ko') -> Dict[str, str]:
    """
    LEGACY WRAPPER - Redirects to new utils system
    
    Get section titles for specified language.
    Use summarizer.utils.get_section_titles directly for new code.
    """
    from .summarizer.utils import get_section_titles as new_get_section_titles
    return new_get_section_titles(ui_language)
    """
    UI 언어에 따른 섹션 타이틀 반환
    
    Args:
        ui_language: UI 언어 ('ko' 또는 'en')
        
    Returns:
        Dict[str, str]: 섹션 타이틀 매핑
    """
    if ui_language == 'en':
        return {
            'problem': '🔍 **Problem Analysis**',
            'cause': '🎯 **Root Cause**', 
            'solution': '🔧 **Solution Process**',
            'insights': '💡 **Key Insights**'
        }
    else:  # 기본값: 한국어
        return {
            'problem': '🔍 **문제 상황**',
            'cause': '🎯 **근본 원인**',
            'solution': '🔧 **해결 과정**', 
            'insights': '💡 **핵심 포인트**'
        }


def get_subsection_titles(ui_language: str = 'ko') -> Dict[str, Dict[str, str]]:
    """
    LEGACY WRAPPER - Redirects to new utils system
    
    This function maintains backward compatibility.
    Use get_section_titles from summarizer.utils instead.
    """
    from .summarizer.utils import get_section_titles
    
    # Convert new format to legacy format
    section_titles = get_section_titles(ui_language)
    
    # Legacy format expected by old code
    return {
        'problem': section_titles['problem'],
        'cause': section_titles['cause'], 
        'solution': section_titles['solution'],
        'insights': section_titles['insights']
    }
    """
    UI 언어에 따른 서브섹션 타이틀 반환
    
    Args:
        ui_language: UI 언어 ('ko' 또는 'en')
        
    Returns:
        Dict[str, Dict[str, str]]: 서브섹션 타이틀 매핑
    """
    if ui_language == 'en':
        return {
            'cause': {
                'primary': '**Primary Cause**',
                'contributing': '**Contributing Factors**',
                'context': '**System Context**',
                'dependencies': '**Dependencies**'
            },
            'solution': {
                'status': '**Current Status**',
                'completed': '**Actions Completed**',
                'progress': '**In Progress**',
                'next': '**Next Steps**',
                'timeline': '**Expected Timeline**',
                'verification': '**Verification**'
            },
            'insights': {
                'technical': '**Technical Specifications**',
                'service': '**Service Requirements**',
                'process': '**Process Insights**',
                'reference': '**Reference Materials**',
                'future': '**Future Considerations**'
            }
        }
    else:  # 기본값: 한국어
        return {
            'cause': {
                'primary': '**주요 원인**',
                'contributing': '**기여 요인**',
                'context': '**시스템 환경**',
                'dependencies': '**종속성**'
            },
            'solution': {
                'status': '**현재 상태**',
                'completed': '**완료된 작업**',
                'progress': '**진행 중**',
                'next': '**다음 단계**',
                'timeline': '**예상 일정**',
                'verification': '**검증 방법**'
            },
            'insights': {
                'technical': '**기술 사양**',
                'service': '**서비스 요구사항**',
                'process': '**프로세스 인사이트**',
                'reference': '**참고 자료**',
                'future': '**향후 고려사항**'
            }
        }


async def generate_optimized_summary(
    content: str,
    content_type: str = "ticket",
    subject: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    ui_language: str = "ko"
) -> str:
    """
    LEGACY WRAPPER - Redirects to new modular summarizer system
    
    This function maintains backward compatibility while using the new modular system.
    All new development should use the modular system directly.
    """
    # Import the new modular system
    from .summarizer import generate_optimized_summary as new_generate_summary
    
    # Delegate to new system
    return await new_generate_summary(
        content=content,
        content_type=content_type,
        subject=subject,
        metadata=metadata,
        ui_language=ui_language
    )
    """
    최적화된 프롬프트로 콘텐츠 요약을 생성합니다.
    
    Args:
        content: 요약할 내용
        content_type: 콘텐츠 타입 ("ticket", "knowledge_base", "conversation")
        subject: 제목 (티켓 subject, KB title 등)
        metadata: 추가 메타데이터 (상태, 우선순위 등)
        ui_language: UI 언어 (기본값: "ko")
        
    Returns:
        str: 생성된 요약
    """
    if not content or not content.strip():
        return "요약할 내용이 없습니다."
    
    try:
        # 원문 언어 자동 감지
        content_language = detect_content_language(content)
        logger.info(f"📝 일반 요약 시작 - 원본 크기: {len(content):,}자, 언어: {content_language}")
        
        # 최적화된 프롬프트 생성
        system_prompt = _get_optimized_system_prompt(content_type, content_language, ui_language)
        user_prompt = _build_optimized_user_prompt(
            content=content,
            content_type=content_type,
            subject=subject,
            metadata=metadata or {},
            content_language=content_language,
            ui_language=ui_language
        )
        
        # LLM 요청 - 설정 기반 자동 모델 선택 (LangChain 장점 활용!)
        response = await llm_manager.generate_for_use_case(
            use_case="batch",  # 배치 처리용 모델 자동 선택 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1200,  # 상세한 요약을 위해 토큰 수 증가
            temperature=0.1   # 매우 일관성 있는 요약
        )
        
        if response and response.content:
            summary = response.content.strip()
            
            # 품질 검증
            quality_score = _validate_summary_quality(summary, content, content_language)
            logger.info(f"요약 품질 점수: {quality_score:.2f}")
            
            if quality_score < 0.7:  # 품질이 낮으면 재시도
                logger.warning("요약 품질이 낮아 재시도합니다.")
                retry_prompt = f"{user_prompt}\n\nIMPORTANT: The previous summary was inadequate. Please provide a more detailed and accurate summary that strictly follows the original content."
                retry_response = await llm_manager.generate_for_use_case(
                    use_case="batch",  # 배치 처리용 모델 자동 선택 (재시도도 동일)
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": retry_prompt}
                    ],
                    max_tokens=1200,
                    temperature=0.05  # 재시도 시 더욱 정확한 결과를 위해 낮게 설정
                )
                if retry_response and retry_response.content:
                    summary = retry_response.content.strip()
            
            logger.debug(f"{content_type} 최적화된 요약 생성 완료 (길이: {len(summary)})")
            return summary
        else:
            logger.warning(f"{content_type} 요약 생성 실패: 빈 응답")
            return f"[{content_type} 요약 생성 실패]"
            
    except Exception as e:
        logger.error(f"{content_type} 요약 생성 중 오류: {e}")
        return f"[요약 생성 오류: {str(e)}]"


def _get_optimized_system_prompt(content_type: str, content_language: str = "ko", ui_language: str = "ko") -> str:
    """
    DEPRECATED - Use PromptBuilder from summarizer.prompt instead
    
    This function is maintained for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "_get_optimized_system_prompt is deprecated. Use PromptBuilder from summarizer.prompt instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from .summarizer.prompt import PromptBuilder
    builder = PromptBuilder()
    return builder.build_system_prompt(content_type, content_language, ui_language)
    """
    최적화된 시스템 프롬프트 반환 - 언어 일관성을 위해 한국어 기반으로 변경
    """
    
    if content_type == "ticket":
        # 섹션 타이틀 가져오기
        titles = get_section_titles(ui_language)
        subtitles = get_subsection_titles(ui_language)
        
        # 언어별 지시사항
        if content_language == "ko":
            language_instruction = "한국어로만 응답하세요"
        elif content_language == "en":
            language_instruction = "영어로만 응답하세요"
        elif content_language == "ja":
            language_instruction = "일본어로만 응답하세요"
        elif content_language == "zh":
            language_instruction = "중국어로만 응답하세요"
        else:
            language_instruction = "원문과 동일한 언어로 응답하세요"

        # 첨부파일 포맷 문자열 정의 (f-string 내에서 줄바꿈 문제 해결)
        attachment_format = "첨부파일이 있는 경우 다음과 같이 표시하세요:\\n- **참고 자료**:\\n  - 📎 파일명1\\n  - 📎 파일명2\\n  - 📎 파일명3\\n관련 첨부파일이 없으면 대화에서 언급된 중요한 문서나 자료를 기재하세요."
        
        attachment_format_en = "If relevant attachments exist, display them as follows:\\n- **Reference Materials**:\\n  - 📎 filename1\\n  - 📎 filename2\\n  - 📎 filename3\\nIf no relevant attachments exist, mention key documentation or resources referenced in the conversation."

        return f"""당신은 현장 실무진을 위한 정확한 티켓 요약을 작성하는 고객 지원 분석 전문가입니다.

CRITICAL MISSION: Create summaries that preserve ALL essential business and technical information while remaining readable and actionable.

ABSOLUTE REQUIREMENTS:
1. NEVER omit proper nouns (company names, person names, product names, service names)
2. NEVER omit technical terms (MX records, DNS, domain names, etc.)
3. NEVER omit dates, times, or deadlines
4. NEVER generalize specific technical details
5. NEVER change or approximate numerical values, dates, or names
6. Include ALL customer questions and concerns explicitly stated
7. **CRITICAL: Distinguish between CUSTOMER and SUPPORT AGENT**:
   - CUSTOMER: The actual person/company who submitted the ticket and needs help
   - SUPPORT AGENT: The person providing assistance (usually from the support organization)
   - Look for email patterns: customer emails are usually from external domains
   - Support agent emails often contain internal company domain or signature references
   - In email conversations, identify who is ASKING for help vs. who is PROVIDING help
   - Customer company is usually mentioned in the initial ticket request or problem description
   - ALWAYS identify the ACTUAL CUSTOMER COMPANY, not the support agent's company
   - **EXAMPLES OF CORRECT IDENTIFICATION**:
     * ✅ CUSTOMER: Email from "john@company.com" asking for help → Customer: company.com
     * ❌ WRONG: Support agent from "support@serviceprovider.com" → NOT the customer
   - **IDENTIFICATION PRIORITY**: Initial problem reporter > Email domain > Company mentioned in problem description
8. **CRITICAL: Use EXACT terminology from original content**:
   - Company names: Use the EXACT name as it appears in the original (do not create bilingual formats)
   - Technical terms: Use the EXACT terms from the original text
   - Product/service names: Use the EXACT names as mentioned in original text
   - Always preserve exact domain names and URLs as they appear
   - Include all mentioned support company names exactly as written
   - NEVER add parenthetical translations or explanations not in original
   - NEVER create formats like "Company (회사명)" unless it appears exactly that way in original

STRICTLY FORBIDDEN:
- Adding fallback phrases like "원문에서 충분한 정보가 제공되지 않아"
- Adding disclaimers like "추가 정보 제공 시 보다 정확한 해결 방안을 제시할 수 있습니다"
- Adding phrases like "해결 과정이 아직 시작되지 않았습니다"
- Creating bilingual parenthetical formats not in original text
- Making assumptions or speculating about missing information
- Adding your own interpretations or explanations beyond what's stated
- Using generic or vague language when specific details are available

STRUCTURE YOUR SUMMARY:

{titles['problem']}
- **{'고객 회사 및 담당자' if ui_language == 'ko' else 'Customer Company and Contact'}**: ACTUAL customer company and customer contact (NOT support agent company/name)
  * Look for: "from:" email headers, signatures, company domains in email addresses
  * AVOID: Support agent names, internal support company references, agent signatures
  * Format: "Customer Company Name - Customer Contact Person (Role if mentioned)"
- Exact technical issue or business need described
- Specific products/services/systems involved (use exact names from original)
- Key dates, deadlines, or urgency factors mentioned
- Customer's specific questions or points of confusion

{titles['cause']}
Provide structured root cause analysis:
- {subtitles['cause']['primary']}: Main technical or business factor causing the issue
- {subtitles['cause']['contributing']}: Additional elements that led to or amplified the problem
- {subtitles['cause']['context']}: What changed in the environment, policies, or setup
- {subtitles['cause']['dependencies']}: External systems, services, or decisions that influenced the situation

{titles['solution']}
Structure the solution process systematically:
- {subtitles['solution']['status']}: What stage the resolution is at right now
- {subtitles['solution']['completed']}: 
  - YYYY-MM-DD: [Specific action] → [Result/Outcome]
  - YYYY-MM-DD: [Specific action] → [Result/Outcome]
- {subtitles['solution']['progress']}: What is currently being worked on
- {subtitles['solution']['next']}: Specific actions planned with responsible party if mentioned
- {subtitles['solution']['timeline']}: When full resolution is anticipated
- {subtitles['solution']['verification']}: How success will be measured or confirmed

{titles['insights']}
Key technical and procedural insights (EXCLUDE all customer contact information):
- {subtitles['insights']['technical']}: Settings, configurations, and technical parameters
- {subtitles['insights']['service']}: Limitations, dependencies, and compatibility needs
- {subtitles['insights']['process']}: Best practices, workflows, and procedural knowledge
- {subtitles['insights']['reference']}: {attachment_format if ui_language == 'ko' else attachment_format_en}
- {subtitles['insights']['future']}: Recommendations for similar cases or preventive measures
- **IMPORTANT**: Never include customer names, phone numbers, emails, or personal identifiers

STRICT PROHIBITIONS:
- NEVER use fallback phrases like "원문에서 충분한 정보가 제공되지 않아", "해결 과정이 아직 시작되지 않았습니다", "추가 정보 제공 시 보다 정확한 해결 방안을 제시할 수 있습니다"
- NEVER use vague phrases like "insufficient information provided", "not enough information", "more information needed"  
- NEVER apologize for lack of information - work with what is provided
- NEVER include placeholder text or template-like endings
- NEVER create bilingual company names or technical terms unless they appear that way in the original
- If information is truly missing, simply state the facts that ARE available
- NEVER add explanatory text about information limitations

CUSTOMER IDENTIFICATION RULES:
- **PRIMARY RULE**: The customer is the person/company who ORIGINALLY SUBMITTED the ticket and needs help
- Read email headers carefully: "From:", "발신자:", sender information
- Customer emails are typically from external company domains (not support company domains)
- Look for company names mentioned in the initial problem description or ticket submission
- Support agents often have internal company emails or standardized signatures
- **CRITICAL DISTINCTION**:
  * CUSTOMER = The person/company with the PROBLEM who needs HELP
  * SUPPORT AGENT = The person PROVIDING assistance and solutions
- **VERIFICATION STEPS**:
  1. Find the INITIAL ticket submission - who reported the problem?
  2. Check email domains - external domains are usually customers
  3. Look for company names in problem descriptions (not in agent responses)
  4. Identify who is ASKING questions vs. who is ANSWERING questions
- **COMMON MISTAKES TO AVOID**:
  * ❌ Listing support agent names as customer companies
  * ❌ Using agent company names instead of actual customer company
  * ❌ Confusing the person helping with the person being helped

FORMATTING RULES:
- {language_instruction}
- Write concisely but preserve ALL critical details
- Use exact names, terms, and values from original text
- If original mentions specific technical terms, include them exactly
- Keep each section focused but comprehensive
- ALWAYS provide substantive content in each section based on available information
- NEVER end with disclaimers about information sufficiency
- NEVER suggest that more information is needed
- Focus only on what IS provided in the original content"""

    elif content_type == "knowledge_base":
        # 섹션 타이틀 가져오기 (KB용)
        if ui_language == 'ko':
            kb_sections = {
                'purpose': '📋 **문서 목적**',
                'procedure': '📝 **처리 절차**',
                'requirements': '⚙️ **사전 요구사항**',
                'technical': '🔧 **기술 세부사항**'
            }
        else:
            kb_sections = {
                'purpose': '📋 **Document Purpose**',
                'procedure': '📝 **Procedures**', 
                'requirements': '⚙️ **Prerequisites**',
                'technical': '🔧 **Technical Details**'
            }
        
        # 언어별 지시사항
        if content_language == "ko":
            language_instruction = "Respond in Korean only"
        elif content_language == "en":
            language_instruction = "Respond in English only"
        elif content_language == "ja":
            language_instruction = "Respond in Japanese only"
        elif content_language == "zh":
            language_instruction = "Respond in Chinese only"
        else:
            language_instruction = "Respond in the same language as the original content"

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

    else:  # conversation type
        # 언어별 지시사항
        if content_language == "ko":
            language_instruction = "Respond in Korean only"
        elif content_language == "en":
            language_instruction = "Respond in English only"
        elif content_language == "ja":
            language_instruction = "Respond in Japanese only"
        elif content_language == "zh":
            language_instruction = "Respond in Chinese only"
        else:
            language_instruction = "Respond in the same language as the original content"

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


def _select_relevant_attachments(attachments: List[Dict[str, Any]], content: str, subject: str = "") -> List[Dict[str, Any]]:
    """
    DEPRECATED - Use AttachmentSelector from summarizer.attachment instead
    
    This function is maintained for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "_select_relevant_attachments is deprecated. Use AttachmentSelector from summarizer.attachment instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from .summarizer.attachment import AttachmentSelector
    selector = AttachmentSelector()
    return selector.select_relevant_attachments(attachments, content, subject)
    if not attachments:
        return []
    
    scored_attachments = []
    content_text = (content or "").lower()
    subject_text = (subject or "").lower()
    combined_text = f"{subject_text} {content_text}"
    
    # 키워드 기반 관련성 점수 계산
    for att in attachments:
        if not isinstance(att, dict):
            continue
            
        score = 0
        att_name = att.get('name', '').lower()
        att_type = att.get('content_type', '').lower()
        
        # 1. 파일명이 티켓에서 직접 언급되었는지 확인 (최고 점수)
        if att_name in combined_text or any(word in combined_text for word in att_name.split('.')):
            score += 10
            
        # 2. 파일 확장자별 중요도
        if att_name.endswith(('.log', '.txt')):
            score += 5  # 로그 파일 - 문제 해결에 중요
        elif att_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            score += 4  # 스크린샷 - 문제 상황 설명에 중요
        elif att_name.endswith(('.pdf', '.doc', '.docx')):
            score += 3  # 문서 파일 - 가이드나 정책
        elif att_name.endswith(('.json', '.xml', '.yaml', '.yml', '.csv')):
            score += 4  # 설정/데이터 파일 - 기술적 문제 해결에 중요
        else:
            score += 1  # 기타 파일
            
        # 3. 콘텐츠 타입별 가중치
        if 'image' in att_type:
            score += 2  # 이미지는 문제 상황 설명에 유용
        elif 'text' in att_type or 'application/json' in att_type:
            score += 3  # 텍스트/설정 파일은 기술적 분석에 중요
            
        # 4. 파일 크기 고려 (적절한 크기의 파일 선호)
        file_size = att.get('size', 0) or 0
        if 1024 <= file_size <= 5 * 1024 * 1024:  # 1KB ~ 5MB
            score += 1
        elif file_size > 20 * 1024 * 1024:  # 20MB 초과시 감점
            score -= 1
            
        # 5. 중요 키워드가 파일명에 포함되어 있는지
        important_keywords = ['error', 'log', 'config', 'setting', 'screenshot', 
                             '에러', '로그', '설정', '스크린샷', '캡처', '오류', '문제']
        for keyword in important_keywords:
            if keyword in att_name:
                score += 2
                break
        
        scored_attachments.append((score, att))
    
    # 점수 기준으로 정렬
    scored_attachments.sort(key=lambda x: x[0], reverse=True)
    
    # 더 엄격한 기준 적용 - 실제 관련성이 있는 파일만 선택
    relevant_attachments = []
    
    # 전체 점수가 매우 낮으면 관련성 없다고 판단
    if not scored_attachments or scored_attachments[0][0] < 3:
        return []
    
    # 최고 점수 파일이 10점 이상 (직접 언급)인 경우만 선택
    if scored_attachments[0][0] >= 10:
        relevant_attachments.append(scored_attachments[0][1])
        
        # 추가 파일들도 매우 높은 기준 적용
        for score, att in scored_attachments[1:3]:
            if score >= 10:  # 직접 언급된 파일만
                relevant_attachments.append(att)
    
    # 최고 점수가 7-9점 (높은 관련성)인 경우
    elif scored_attachments[0][0] >= 7:
        # 첫 번째 파일의 타입이 이미지이고, 내용에 관련 키워드가 있는 경우만
        first_att = scored_attachments[0][1]
        if (first_att.get('content_type', '').startswith('image/') or 
            first_att.get('name', '').endswith(('.log', '.yml', '.yaml', '.json'))):
            relevant_attachments.append(first_att)
    
    # 5-6점 (중간 관련성)인 경우는 매우 제한적으로만 허용
    elif scored_attachments[0][0] >= 5:
        first_att = scored_attachments[0][1]
        # 파일명에 중요한 키워드가 포함되어 있고, 로그나 설정 파일인 경우만
        att_name = first_att.get('name', '').lower()
        if any(keyword in att_name for keyword in ['error', 'log', 'config', 'screenshot', '에러', '로그', '설정', '스크린샷']):
            # 추가로 티켓 내용과 최소한의 연관성이 있는지 확인
            content_keywords = ['오류', '에러', '문제', '설정', '로그', 'error', 'problem', 'issue', 'config', 'log']
            if any(keyword in combined_text for keyword in content_keywords):
                relevant_attachments.append(first_att)
    
    return relevant_attachments


def _build_optimized_user_prompt(
    content: str,
    content_type: str,
    subject: str,
    metadata: Dict[str, Any],
    content_language: str,
    ui_language: str
) -> str:
    """
    DEPRECATED - Use PromptBuilder from summarizer.prompt instead
    
    This function is maintained for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "_build_optimized_user_prompt is deprecated. Use PromptBuilder from summarizer.prompt instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from .summarizer.prompt import PromptBuilder
    builder = PromptBuilder()
    return builder.build_user_prompt(content, content_type, subject, metadata, content_language, ui_language)
    
    prompt_parts = []
    
    # 제목 포함 (있는 경우)
    if subject:
        prompt_parts.append(f"TICKET SUBJECT: {subject}")
    
    # 메타데이터 포함 (있는 경우)
    if metadata:
        formatted_metadata = []
        
        # 첨부파일 정보 특별 처리 - 관련성이 높은 1-3개만 선택
        if 'attachments' in metadata or 'all_attachments' in metadata:
            attachments = metadata.get('attachments') or metadata.get('all_attachments') or []
            if attachments and isinstance(attachments, list):
                # 첨부파일 관련성 점수 계산 및 선택
                relevant_attachments = _select_relevant_attachments(attachments, content, subject)
                
                if relevant_attachments:
                    # 사용자에게 보여질 깔끔한 파일명만 추출
                    attachment_names = []
                    for att in relevant_attachments:
                        if isinstance(att, dict):
                            att_name = att.get('name', 'Unknown file')
                            # 파일명만 깔끔하게 표시 (메타데이터는 숨김)
                            attachment_names.append(att_name)
                    
                    if attachment_names:
                        formatted_metadata.append(f"relevant_attachments: {', '.join(attachment_names)}")
        
        # 기타 메타데이터 처리
        for k, v in metadata.items():
            if k not in ['attachments', 'all_attachments'] and v:
                formatted_metadata.append(f"{k}: {v}")
        
        if formatted_metadata:
            prompt_parts.append(f"METADATA: {'; '.join(formatted_metadata)}")
    
    # 메인 콘텐츠
    prompt_parts.append("ORIGINAL CONTENT TO ANALYZE:")
    prompt_parts.append("=" * 50)
    prompt_parts.append(content)
    prompt_parts.append("=" * 50)
    
    # 분석 지시사항 - UI 언어에 맞는 지시사항
    if ui_language == 'ko':
        instruction = """위 내용을 분석하여 현장 직원이 즉시 활용할 수 있는 실용적 요약을 작성하세요.

절대 누락하지 말 것:
- 모든 회사명, 담당자명, 연락처 정보
- 모든 기술적 용어 (MX records, DNS, Postini, Google Apps 등)
- 모든 날짜와 시간 (정확한 연도 포함)
- 모든 도메인명, URL, 이메일 주소
- 고객의 모든 질문과 우려사항
- 서비스명과 제품명 (정확한 용어 유지)

엄격히 금지:
- "원문에서 충분한 정보가 제공되지 않아" 같은 fallback 문구 추가
- "추가 정보 제공 시" 같은 면책 문구 추가
- "해결 과정이 아직 시작되지 않았습니다" 같은 추측 문구 추가
- 원문에 없는 괄호 설명 추가

용어 사용 규칙:
- 회사명: 원문에 나타난 정확한 이름 사용
- 기술 용어: 원문의 표현 그대로 보존
- 제품/서비스명: 원문에 언급된 정확한 이름 사용
- 도메인명과 URL: 원문에 나타난 그대로 보존
- 지원 회사명: 언급된 모든 지원 회사를 원문 그대로 포함

작성 원칙:
- 간결하되 중요 정보는 절대 누락하지 말 것
- 가능한 한 원문 용어 보존
- 추측이나 해석 금지
- 사실만 정확히 기록
- 원문에 명시적으로 언급되지 않은 내용 추가 금지
- 원문과 동일한 언어로 응답 (한국어 원문은 한국어로, 영어 원문은 영어로)

첨부파일 처리:
- METADATA에 relevant_attachments가 제공된 경우, "참고 자료" 섹션에 다음 형식으로 표시:
  - 📎 파일명1
  - 📎 파일명2  
  - 📎 파일명3
- 최대 3개까지만 포함하며, 주요 문제나 해결책과 직접 관련된 파일만 선택
- 관련 첨부파일이 없는 경우, 대화에서 언급된 다른 자료나 문서 기재"""
    else:
        instruction = """Analyze the content above and create a practical summary that field staff can use immediately.

NEVER OMIT:
- All company names, contact persons, contact details
- All technical terms (MX records, DNS, Postini, Google Apps, etc.)
- All dates and times (include exact years)  
- All domain names, URLs, email addresses
- All customer questions and concerns
- Service names and product names (preserve exact terminology)

STRICTLY FORBIDDEN:
- Adding fallback phrases like "insufficient information provided"
- Adding disclaimers like "more information needed"
- Adding speculative phrases like "resolution process not yet started"
- Adding parenthetical explanations not in original text

TERMINOLOGY RULES:
- Company names: Use EXACT names as they appear in original text
- Technical terms: Preserve original expressions exactly
- Product/service names: Use exact names mentioned in original
- Domain names and URLs: Preserve exactly as they appear
- Support company names: Include all mentioned support companies exactly as written

WRITING PRINCIPLES:
- Be concise but NEVER omit important information  
- Preserve original terminology as much as possible
- No speculation or interpretation
- Record facts accurately only
- Never add content not explicitly stated in original
- Respond in the same language as the original content

ATTACHMENT HANDLING:
- If relevant_attachments are provided in METADATA, display them in the "Reference Materials" section as:
  - 📎 filename1
  - 📎 filename2
  - 📎 filename3
- Include maximum 3 files, only those directly related to the main issue or solution
- If no relevant attachments are provided, mention other resources or documentation referenced in the conversation"""
    
    prompt_parts.append(instruction)
    
    return "\n\n".join(prompt_parts)


def _validate_summary_quality(summary: str, original_content: str, content_language: str) -> float:
    """
    DEPRECATED - Use QualityValidator from summarizer.quality instead
    
    This function is maintained for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "_validate_summary_quality is deprecated. Use QualityValidator from summarizer.quality instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from .summarizer.quality import QualityValidator
    validator = QualityValidator()
    result = validator.validate_summary_quality(summary, original_content, content_language)
    return result['quality_score']
    if not summary or len(summary.strip()) < 50:
        return 0.0
    
    quality_score = 0.0
    total_checks = 0
    
    # 1. 구조 섹션 존재 확인
    required_sections = ['🔍', '🎯', '🔧', '💡']
    section_count = sum(1 for section in required_sections if section in summary)
    quality_score += (section_count / len(required_sections)) * 0.4
    total_checks += 0.4
    
    # 2. 추측 표현 확인 (한국어)
    if content_language == "ko":
        speculation_patterns = [
            r'일\s*것\s*입니다', r'일\s*것\s*이다', r'할\s*수\s*있습니다', 
            r'가능성이', r'추정됩니다', r'예상됩니다', r'것으로\s*보입니다'
        ]
        speculation_count = sum(1 for pattern in speculation_patterns if re.search(pattern, summary))
        quality_score += max(0, (1 - speculation_count * 0.2)) * 0.3
    else:
        speculation_patterns = [
            r'might\s+be', r'could\s+be', r'possibly', r'likely', r'probably'
        ]
        speculation_count = sum(1 for pattern in speculation_patterns if re.search(pattern, summary, re.IGNORECASE))
        quality_score += max(0, (1 - speculation_count * 0.2)) * 0.3
    total_checks += 0.3
    
    # 3. 길이 적절성 확인
    if 200 <= len(summary) <= 2000:
        quality_score += 0.3
    elif len(summary) < 200:
        quality_score += 0.1
    else:
        quality_score += 0.2
    total_checks += 0.3
    
    return quality_score / total_checks if total_checks > 0 else 0.0


class AdaptiveContextManager:
    """
    DEPRECATED - Use ContextOptimizer from summarizer.context instead
    
    This class is maintained for backward compatibility only.
    """
    
    def __init__(self):
        import warnings
        warnings.warn(
            "AdaptiveContextManager is deprecated. Use ContextOptimizer from summarizer.context instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.max_tokens_per_request = 6000  # Conservative limit for quality
        self.min_tokens_per_doc = 200
        self.quality_threshold = 0.8
        self.context_compression_ratio = 0.7  # 대용량 시 컨텍스트 압축 비율
        
    def optimize_context_for_scale(
        self, 
        context: str, 
        dataset_size: int,
        query: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """데이터셋 크기에 따른 적응형 컨텍스트 최적화"""
        
        optimization_metadata = {
            "original_length": len(context),
            "dataset_size": dataset_size,
            "optimization_applied": "none"
        }
        
        # 대용량 데이터셋인 경우 (1000건 이상)
        if dataset_size >= 1000:
            logger.info(f"대용량 데이터셋 감지 ({dataset_size}건), 컨텍스트 최적화 적용")
            
            # 1. 컨텍스트 압축
            compressed_context = self._compress_context_semantically(context, query)
            optimization_metadata["optimization_applied"] = "compression"
            optimization_metadata["compression_ratio"] = len(compressed_context) / len(context)
            
            # 2. 핵심 정보 추출
            if len(compressed_context) > self.max_tokens_per_request * 4:  # 대략적 문자 수 계산
                core_context = self._extract_core_information(compressed_context, query)
                optimization_metadata["optimization_applied"] = "core_extraction"
                optimization_metadata["final_length"] = len(core_context)
                return core_context, optimization_metadata
            
            return compressed_context, optimization_metadata
        
        # 소규모 데이터셋은 기존 로직 유지
        return context, optimization_metadata
    
    def _compress_context_semantically(self, context: str, query: Optional[str] = None) -> str:
        """의미적 컨텍스트 압축"""
        
        if not context:
            return ""
        
        # 문장 단위로 분할
        sentences = context.split('\n\n')
        
        # 각 문장의 중요도 점수 계산
        scored_sentences = []
        query_words = set(query.lower().split()) if query else set()
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            importance_score = self._calculate_sentence_importance(sentence, query_words)
            scored_sentences.append({
                'text': sentence,
                'score': importance_score,
                'length': len(sentence)
            })
        
        # 점수 기준으로 정렬
        scored_sentences.sort(key=lambda x: x['score'], reverse=True)
        
        # 목표 길이에 맞춰 선택
        target_length = int(len(context) * self.context_compression_ratio)
        selected_sentences = []
        current_length = 0
        
        for sentence_info in scored_sentences:
            if current_length + sentence_info['length'] <= target_length:
                selected_sentences.append(sentence_info['text'])
                current_length += sentence_info['length']
            elif not selected_sentences:  # 최소한 하나는 포함
                # 문장을 적절히 잘라서 포함
                remaining_length = target_length
                words = sentence_info['text'].split()
                target_words = int(len(words) * remaining_length / sentence_info['length'])
                truncated = ' '.join(words[:max(50, target_words)])  # 최소 50단어
                selected_sentences.append(truncated)
                break
            else:
                break
        
        # 원래 순서 복원을 위해 위치 기반 정렬
        original_order_sentences = []
        for sentence in sentences:
            if sentence in selected_sentences:
                original_order_sentences.append(sentence)
        
        return '\n\n'.join(original_order_sentences)
    
    def _extract_core_information(self, context: str, query: Optional[str] = None) -> str:
        """핵심 정보 추출 (최종 단계)"""
        
        # 핵심 키워드 패턴
        core_patterns = [
            r'문제.*?해결',
            r'원인.*?분석',
            r'처리.*?완료',
            r'해결.*?방법',
            r'결과.*?확인',
            r'조치.*?사항'
        ]
        
        # 패턴 매칭으로 핵심 문장 추출
        import re
        core_sentences = []
        
        for sentence in context.split('\n\n'):
            if not sentence.strip():
                continue
                
            # 핵심 패턴 매칭
            for pattern in core_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    core_sentences.append(sentence)
                    break
            
            # 쿼리 관련성 검사
            if query:
                query_words = set(query.lower().split())
                sentence_words = set(sentence.lower().split())
                if query_words.intersection(sentence_words):
                    if sentence not in core_sentences:
                        core_sentences.append(sentence)
        
        # 길이 제한 적용
        result = '\n\n'.join(core_sentences)
        if len(result) > self.max_tokens_per_request * 4:
            # 다시 한 번 압축
            result = result[:self.max_tokens_per_request * 4]
            # 마지막 완전한 문장까지만 포함
            last_period = result.rfind('.')
            if last_period > len(result) * 0.8:  # 80% 이상 지점에서 발견된 경우
                result = result[:last_period + 1]
        
        return result
    
    def _calculate_sentence_importance(self, sentence: str, query_words: Set[str]) -> float:
        """문장 중요도 계산"""
        score = 0.0
        
        # 1. 쿼리 관련성 점수
        if query_words:
            sentence_words = set(sentence.lower().split())
            common_words = query_words.intersection(sentence_words)
            if common_words:
                score += len(common_words) / len(query_words) * 2.0
        
        # 2. 핵심 키워드 점수
        important_keywords = [
            '해결', '완료', '처리', '조치', '확인', '분석', '원인', '결과',
            'resolved', 'completed', 'processed', 'confirmed', 'analyzed'
        ]
        
        for keyword in important_keywords:
            if keyword in sentence.lower():
                score += 0.5
        
        # 3. 문장 길이 점수 (너무 짧거나 길지 않은 적절한 길이 선호)
        length_score = 1.0
        if len(sentence) < 50:
            length_score = 0.5
        elif len(sentence) > 500:
            length_score = 0.7
        
        score *= length_score
        
        # 4. 구조적 중요도 (마크다운 헤더, 강조 등)
        if sentence.strip().startswith('#') or '**' in sentence:
            score += 0.3
        
        return score


class QualityGuard:
    """
    DEPRECATED - Use QualityValidator from summarizer.quality instead
    
    This class is maintained for backward compatibility only.
    """
    
    def __init__(self):
        import warnings
        warnings.warn(
            "QualityGuard is deprecated. Use QualityValidator from summarizer.quality instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.min_quality_threshold = 0.85
        self.critical_elements = [
            "문제 상황", "근본 원인", "해결 과정", "핵심 포인트"
        ]
    
    def validate_large_scale_summary(self, summary: str, context: str) -> Dict[str, Any]:
        """대용량 처리 시 요약 품질 검증"""
        
        validation_result = {
            "is_valid": True,
            "quality_score": 0.0,
            "issues": [],
            "recommendations": []
        }
        
        # 1. 구조 검증
        structure_score = self._validate_structure(summary)
        
        # 2. 내용 완성도 검증
        completeness_score = self._validate_completeness(summary, context)
        
        # 3. 언어 품질 검증
        language_score = self._validate_language_quality(summary)
        
        # 4. 길이 적정성 검증
        length_score = self._validate_length(summary)
        
        # 종합 점수 계산
        overall_score = (
            structure_score * 0.3 +
            completeness_score * 0.3 +
            language_score * 0.2 +
            length_score * 0.2
        )
        
        validation_result["quality_score"] = overall_score
        validation_result["is_valid"] = overall_score >= self.min_quality_threshold
        
        # 문제점 및 권장사항 생성
        if structure_score < 0.8:
            validation_result["issues"].append("구조적 완성도 부족")
            validation_result["recommendations"].append("4개 섹션 모두 포함 필요")
        
        if completeness_score < 0.8:
            validation_result["issues"].append("내용 완성도 부족")
            validation_result["recommendations"].append("핵심 정보 추가 추출 필요")
        
        return validation_result
    
    def _validate_structure(self, summary: str) -> float:
        """구조 검증"""
        found_elements = sum(1 for element in self.critical_elements 
                           if any(keyword in summary for keyword in [element]))
        return found_elements / len(self.critical_elements)
    
    def _validate_completeness(self, summary: str, context: str) -> float:
        """내용 완성도 검증"""
        # 간단한 키워드 기반 완성도 측정
        context_keywords = set(context.lower().split())
        summary_keywords = set(summary.lower().split())
        
        if not context_keywords:
            return 1.0
        
        overlap = len(context_keywords.intersection(summary_keywords))
        return min(overlap / len(context_keywords) * 3, 1.0)  # 최대 1.0
    
    def _validate_language_quality(self, summary: str) -> float:
        """언어 품질 검증"""
        score = 1.0
        
        # 에러 메시지 확인
        if any(error in summary.lower() for error in ['error', '오류', 'failed', '실패']):
            score -= 0.3
        
        # 불완전한 마크다운 확인
        if summary.count('**') % 2 != 0:
            score -= 0.2
        
        # 최소 길이 확인
        if len(summary.strip()) < 100:
            score -= 0.3
        
        return max(score, 0.0)
    
    def _validate_length(self, summary: str) -> float:
        """길이 적정성 검증"""
        length = len(summary.strip())
        
        if 200 <= length <= 1500:
            return 1.0
        elif length < 200:
            return length / 200
        else:
            return max(1.0 - (length - 1500) / 1000, 0.5)


class OptimizedSummarizer:
    """
    DEPRECATED - Use CoreSummarizer from summarizer.core instead
    
    This class is maintained for backward compatibility only.
    For new code, use the modular summarizer system.
    """

    def __init__(self):
        import warnings
        warnings.warn(
            "OptimizedSummarizer is deprecated. Use CoreSummarizer from summarizer.core instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.adaptive_context_manager = AdaptiveContextManager()
        self.quality_guard = QualityGuard()
        self.large_scale_mode = False
        self.current_dataset_size = 0
        self.llm_manager = llm_manager  # 전역 LLM 매니저 사용

    def enable_large_scale_mode(self, dataset_size: int):
        """대용량 처리 모드 활성화"""
        self.large_scale_mode = True
        self.current_dataset_size = dataset_size
        logger.info(f"대용량 처리 모드 활성화: {dataset_size}건 데이터셋")

    async def generate_summary(
        self,
        content: str,
        content_type: str = "ticket",
        subject: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        ui_language: str = "ko",
        context: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        최적화된 요약 생성 (대용량 처리 지원)
        """
        try:
            # 대용량 모드에서 컨텍스트 최적화
            optimized_context = context or ""
            optimization_metadata = {}
            
            if self.large_scale_mode and context:
                optimized_context, optimization_metadata = \
                    self.adaptive_context_manager.optimize_context_for_scale(
                        context, self.current_dataset_size, subject
                    )
                
                logger.debug(f"컨텍스트 최적화 완료: {optimization_metadata}")

            # 기존 요약 생성 로직 실행
            summary = await self._generate_core_summary(
                content, content_type, subject, metadata, ui_language, optimized_context
            )

            # 대용량 모드에서 품질 검증
            if self.large_scale_mode:
                validation_result = self.quality_guard.validate_large_scale_summary(
                    summary, optimized_context
                )
                
                if not validation_result["is_valid"]:
                    logger.warning(f"품질 검증 실패: {validation_result['issues']}")
                    
                    # 품질 개선 시도
                    if validation_result["quality_score"] < 0.7:
                        logger.info("품질 개선을 위한 재생성 시도")
                        summary = await self._regenerate_with_quality_focus(
                            content, content_type, subject, metadata, ui_language, optimized_context
                        )

            return summary

        except Exception as e:
            logger.error(f"요약 생성 실패: {e}")
            return self._create_fallback_summary(content, content_type, ui_language)

    async def _regenerate_with_quality_focus(
        self,
        content: str,
        content_type: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
        ui_language: str,
        context: str
    ) -> str:
        """품질 중심 재생성"""
        
        # 더 엄격한 프롬프트로 재생성
        enhanced_system_prompt = self._get_enhanced_system_prompt()
        enhanced_user_prompt = self._get_enhanced_user_prompt(
            content, content_type, subject, context, ui_language
        )
        
        try:
            response = await self.llm_manager.generate_for_use_case(
                system_prompt=enhanced_system_prompt,
                user_prompt=enhanced_user_prompt,
                use_case="summarization",  # Config-driven provider selection
                max_tokens=1500,  # 더 긴 응답 허용
                temperature=0.1   # 더 보수적인 생성
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"품질 중심 재생성 실패: {e}")
            return self._create_fallback_summary(content, content_type, ui_language)

    def _get_enhanced_system_prompt(self) -> str:
        """강화된 시스템 프롬프트"""
        return """You are an expert technical support summary specialist with exceptional accuracy and attention to detail.

CRITICAL REQUIREMENTS:
1. ALWAYS generate summaries in exactly 4 sections with specified headings
2. PRESERVE all technical details, error codes, specific steps, and factual information
3. NEVER omit critical information about problem resolution
4. Use natural bilingual presentation (Korean with English terms in parentheses when first mentioned)

QUALITY STANDARDS:
- Technical accuracy: 100%
- Structural completeness: 100%
- Information preservation: 95%+
- Language clarity: Professional level

You will be evaluated on factual accuracy and completeness. Missing critical information results in failure."""

    def _get_enhanced_user_prompt(
        self,
        content: str,
        content_type: str,
        subject: str,
        context: str,
        ui_language: str
    ) -> str:
        """강화된 사용자 프롬프트"""
        
        sections_ko = {
            "situation": "🔍 **문제 상황**",
            "cause": "🎯 **근본 원인**", 
            "solution": "🔧 **해결 과정**",
            "insights": "💡 **핵심 포인트**"
        }
        
        return f"""Analyze this technical support content and create a comprehensive summary with ALL critical information preserved.

SUBJECT: {subject}

CONTENT TO ANALYZE:
{content}

ADDITIONAL CONTEXT:
{context}

REQUIRED OUTPUT FORMAT (Korean):
{sections_ko["situation"]}
[Detailed problem description with specific symptoms, error messages, and technical details]

{sections_ko["cause"]}
[Root cause analysis with technical explanations and contributing factors]

{sections_ko["solution"]}
[Complete step-by-step resolution process with specific actions taken]

{sections_ko["insights"]}
[Key technical insights, preventive measures, and important notes for future reference]

CRITICAL: Include ALL technical details, error codes, specific configurations, and resolution steps. Use natural bilingual presentation for technical terms."""

    def _create_fallback_summary(self, content: str, content_type: str, ui_language: str) -> str:
        """품질 보장 폴백 요약"""
        
        if ui_language == "ko":
            return """🔍 **문제 상황**
요약 생성 중 오류가 발생하여 원본 내용을 기반으로 기본 요약을 제공합니다.

🎯 **근본 원인**
시스템 처리 한계로 인한 요약 생성 실패입니다.

🔧 **해결 과정**
원본 내용을 직접 검토하여 세부사항을 확인해주시기 바랍니다.

💡 **핵심 포인트**
- 원본 데이터 검토 필요
- 수동 분석 권장
- 기술 지원팀 문의 고려"""
        else:
            return """🔍 **Problem Situation**
An error occurred during summary generation. Providing basic summary based on original content.

🎯 **Root Cause**
Summary generation failed due to system processing limitations.

🔧 **Resolution Process**
Please review the original content directly for detailed information.

💡 **Key Insights**
- Original data review required
- Manual analysis recommended
- Consider contacting technical support team"""

    async def _generate_core_summary(
        self,
        content: str,
        content_type: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
        ui_language: str,
        context: str
    ) -> str:
        """핵심 요약 생성 메서드"""
        return await generate_optimized_summary(
            content=content,
            content_type=content_type,
            subject=subject,
            metadata=metadata,
            ui_language=ui_language
        )


# ==========================================
# 이메일 체인 중복 제거 및 하이브리드 요약 기능
# ==========================================


def preprocess_email_chain(content: str) -> str:
    """
    DEPRECATED - Use EmailProcessor from summarizer.email instead
    
    This function is maintained for backward compatibility only.
    """
    import warnings
    warnings.warn(
        "preprocess_email_chain is deprecated. Use EmailProcessor from summarizer.email instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    try:
        # For backward compatibility, provide basic email preprocessing
        from .summarizer.email import EmailProcessor
        processor = EmailProcessor()
        processed = processor.process_email_content(content, preserve_thread=True)
        return processed.content
    except ImportError:
        # Fallback if email processor not available
        return content
    try:
        logger.info(f"📧 이메일 체인 전처리 시작 - 원본 크기: {len(content):,}자")
        
        # 1. 이메일 구조 파싱
        messages = _parse_email_chain(content)
        logger.info(f"📊 파싱된 메시지 수: {len(messages)}개")
        
        # 2. 중복 제거
        unique_messages = _remove_email_duplicates(messages)
        logger.info(f"🔄 중복 제거 후: {len(unique_messages)}개 (제거율: {(1-len(unique_messages)/max(1,len(messages)))*100:.1f}%)")
        
        # 3. 클린 콘텐츠 재구성
        cleaned_content = _reconstruct_clean_content(unique_messages)
        
        reduction_rate = (1 - len(cleaned_content) / max(1, len(content))) * 100
        logger.info(f"✨ 전체 압축률: {reduction_rate:.1f}% ({len(content):,} → {len(cleaned_content):,}자)")
        
        return cleaned_content
        
    except Exception as e:
        logger.warning(f"⚠️ 이메일 체인 전처리 실패, 원본 반환: {e}")
        return content


def _parse_email_chain(content: str) -> List[Dict]:
    """이메일 체인을 개별 메시지로 분리"""
    
    # Freshdesk/이메일 구분자들
    email_separators = [
        r'From:.*?<.*?>.*?\n',
        r'Date:.*?\n',
        r'Subject: Re:.*?\n',
        r'-------- Original Message --------',
        r'---------- Forwarded message ----------',
        r'On \d{4}-\d{2}-\d{2}.*?wrote:',
        r'답변.*?작성함:',
        r'보낸.*?날짜:',
        r'From: .*?@.*?\n',
        r'To: .*?@.*?\n'
    ]
    
    messages = []
    current_message = ""
    
    lines = content.split('\n')
    for line in lines:
        # 이메일 헤더 감지
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in email_separators):
            if current_message.strip():
                messages.append({
                    'content': current_message.strip(),
                    'timestamp': _extract_timestamp(current_message),
                    'sender': _extract_sender(current_message),
                    'hash': _get_content_hash(current_message)
                })
            current_message = line + '\n'
        else:
            current_message += line + '\n'
    
    # 마지막 메시지 추가
    if current_message.strip():
        messages.append({
            'content': current_message.strip(),
            'timestamp': _extract_timestamp(current_message),
            'sender': _extract_sender(current_message),
            'hash': _get_content_hash(current_message)
        })
    
    return messages


def _remove_email_duplicates(messages: List[Dict]) -> List[Dict]:
    """이메일 체인에서 중복 내용 제거"""
    
    cleaned_messages = []
    seen_content_hashes = set()
    
    # 최신순으로 정렬 (중복 제거 시 최신 버전 우선)
    messages.sort(key=lambda x: x['timestamp'], reverse=True)
    
    for msg in messages:
        # 이메일 헤더/서명 제거
        clean_content = _remove_email_headers(msg['content'])
        clean_content = _remove_signatures(clean_content)
        
        # 의미 있는 길이 체크
        if len(clean_content.strip()) < 20:  # 너무 짧으면 스킵
            continue
            
        # 내용 해시 생성 (유사도 90% 이상이면 중복으로 판단)
        content_hash = _get_content_hash(clean_content)
        
        # 중복 체크 (첫 100자 기반)
        content_signature = clean_content[:100].strip()
        is_duplicate = any(
            _calculate_similarity(content_signature, seen_sig) > 0.85 
            for seen_sig in [msg['content'][:100].strip() for msg in cleaned_messages]
        )
        
        if not is_duplicate:
            msg['content'] = clean_content
            cleaned_messages.append(msg)
            seen_content_hashes.add(content_hash)
        else:
            logger.debug(f"중복 제거: {msg['sender']} - {len(clean_content)}자")
    
    return cleaned_messages


def _remove_email_headers(content: str) -> str:
    """이메일 헤더 및 메타데이터 제거"""
    
    header_patterns = [
        r'From:.*?\n',
        r'To:.*?\n', 
        r'Cc:.*?\n',
        r'Subject:.*?\n',
        r'Date:.*?\n',
        r'Sent:.*?\n',
        r'보낸 사람:.*?\n',
        r'받는 사람:.*?\n',
        r'제목:.*?\n',
        r'날짜:.*?\n',
        # Freshdesk 특화 헤더
        r'Ticket #\d+.*?\n',
        r'Priority:.*?\n',
        r'Status:.*?\n',
        r'Agent:.*?\n',
        # 이메일 클라이언트 헤더
        r'Message-ID:.*?\n',
        r'MIME-Version:.*?\n',
        r'Content-Type:.*?\n'
    ]
    
    for pattern in header_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
    
    return content.strip()


def _remove_signatures(content: str) -> str:
    """이메일 서명 제거"""
    
    signature_patterns = [
        r'Best regards.*?$',
        r'Kind regards.*?$', 
        r'Sincerely.*?$',
        r'Thanks.*?$',
        r'감사합니다.*?$',
        r'수고하세요.*?$',
        r'--\s*\n.*?$',  # 표준 이메일 서명 구분자
        r'________________________________.*?$',  # Outlook 서명 구분자
        r'Best Regards,.*?\n.*?@.*?\n.*?$',  # 상세 서명
        r'문의 내용.*?https?://.*?$',  # 지원팀 서명
    ]
    
    for pattern in signature_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    return content.strip()


def _extract_timestamp(content: str) -> datetime:
    """메시지에서 타임스탬프 추출"""
    
    # 다양한 날짜 형식 패턴
    date_patterns = [
        r'Date: (.*?)\n',
        r'날짜: (.*?)\n',
        r'Sent: (.*?)\n',
        r'On (.*?) at',
        r'(\d{4}-\d{2}-\d{2})',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            try:
                # 간단한 날짜 파싱 (더 정교한 파싱 필요시 dateutil 사용)
                date_str = match.group(1).strip()
                if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                    return datetime.strptime(date_str[:10], '%Y-%m-%d')
            except:
                pass
    
    # 기본값: 현재 시간
    return datetime.now()


def _extract_sender(content: str) -> str:
    """메시지에서 발신자 추출"""
    
    sender_patterns = [
        r'From: (.*?) <',
        r'From: (.*?)\n',
        r'보낸 사람: (.*?)\n',
        r'(.*?) 작성함:',
    ]
    
    for pattern in sender_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return "Unknown"


def _get_content_hash(content: str) -> str:
    """내용의 해시값 생성"""
    
    # 공백과 특수문자 제거 후 해시
    clean_content = re.sub(r'\s+', ' ', content.lower().strip())
    return hashlib.md5(clean_content.encode()).hexdigest()[:16]


def _calculate_similarity(text1: str, text2: str) -> float:
    """두 텍스트 간 유사도 계산 (간단한 Jaccard 유사도)"""
    
    if not text1 or not text2:
        return 0.0
    
    # 단어 기반 Jaccard 유사도
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0


def _reconstruct_clean_content(messages: List[Dict]) -> str:
    """정리된 메시지들을 읽기 좋은 형태로 재구성"""
    
    if not messages:
        return ""
    
    content_parts = []
    
    # 시간순으로 정렬
    messages.sort(key=lambda x: x['timestamp'])
    
    for i, msg in enumerate(messages):
        # 발신자와 순서 정보 포함
        header = f"\n--- 메시지 {i+1}: {msg['sender']} ---\n"
        content_parts.append(header + msg['content'])
    
    return "\n".join(content_parts)


async def generate_hybrid_summary(
    content: str,
    content_type: str = "ticket",
    subject: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    ui_language: str = "ko"
) -> str:
    """
    LEGACY WRAPPER - Redirects to new hybrid summarizer system
    
    This function maintains backward compatibility while using the new modular system.
    Use HybridSummarizer directly for new code.
    """
    from .summarizer.hybrid import HybridSummarizer
    
    hybrid_summarizer = HybridSummarizer()
    return await hybrid_summarizer.generate_hybrid_summary(
        content=content,
        content_type=content_type,
        subject=subject,
        metadata=metadata,
        ui_language=ui_language
    )


async def _generate_large_chunk_summary(
    content: str,
    content_type: str,
    subject: str,
    metadata: Optional[Dict[str, Any]],
    ui_language: str
) -> str:
    """큰 청크 기반 요약 (20K 단위)"""
    
    chunk_size = 20000
    chunks = _split_content_smart(content, chunk_size)
    
    if len(chunks) <= 2:
        # 2개 이하: 각각 요약 후 통합
        summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"📝 큰 청크 {i+1}/{len(chunks)} 요약 중...")
            summary = await generate_optimized_summary(
                content=chunk,
                content_type=content_type,
                subject=f"{subject} (Part {i+1})",
                metadata=metadata,
                ui_language=ui_language
            )
            summaries.append(summary)
        
        # 통합 요약
        combined = "\n\n".join(summaries)
        return await _generate_final_integration(combined, content_type, ui_language)
    
    else:
        # 3개 이상: 롤링 요약으로 전환
        return await _generate_rolling_summary(content, content_type, subject, metadata, ui_language)


async def _generate_rolling_summary(
    content: str,
    content_type: str,
    subject: str,
    metadata: Optional[Dict[str, Any]],
    ui_language: str
) -> str:
    """롤링 요약 방식 - 맥락을 유지하면서 순차적 요약"""
    
    chunk_size = 12000  # 롤링에서는 적당한 크기 사용
    chunks = _split_content_smart(content, chunk_size)
    
    logger.info(f"🔄 롤링 요약 시작 - {len(chunks)}개 청크")
    
    current_summary = ""
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            # 첫 번째 청크: 일반 요약
            logger.info(f"📝 롤링 {i+1}/{len(chunks)}: 초기 요약 생성")
            current_summary = await generate_optimized_summary(
                content=chunk,
                content_type=content_type,
                subject=subject,
                metadata=metadata,
                ui_language=ui_language
            )
        else:
            # 이후 청크들: 이전 요약과 함께 처리
            logger.info(f"🔄 롤링 {i+1}/{len(chunks)}: 누적 요약 업데이트")
            combined_content = _create_rolling_prompt(current_summary, chunk, ui_language)
            current_summary = await generate_optimized_summary(
                content=combined_content,
                content_type="rolling_update",
                subject=f"{subject} (Rolling Update {i+1})",
                metadata=metadata,
                ui_language=ui_language
            )
    
    logger.info("✅ 롤링 요약 완료")
    return current_summary


def _split_content_smart(content: str, chunk_size: int) -> List[str]:
    """스마트 청크 분할 - 문장 단위로 자연스럽게 분할"""
    
    chunks = []
    current_chunk = ""
    
    # 문단 단위로 분할
    paragraphs = content.split('\n\n')
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) <= chunk_size:
            current_chunk += paragraph + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + '\n\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def _create_rolling_prompt(previous_summary: str, new_chunk: str, ui_language: str) -> str:
    """롤링 요약을 위한 최적화된 프롬프트 생성 - 구조화된 템플릿 유지 (영어 프롬프트)"""
    
    # 섹션 타이틀 가져오기
    titles = get_section_titles(ui_language)
    
    # 모든 언어에 대해 영어 프롬프트 사용 (AI 이해도 향상)
    return f"""You have an existing cumulative summary of a ticket and new content to integrate. 
Please create an integrated summary maintaining the existing 4-section structure.

=== EXISTING CUMULATIVE SUMMARY ===
{previous_summary}

=== NEW CONTENT ===
{new_chunk}

=== REQUIRED OUTPUT ===
Analyze the content above and create an integrated summary with the following 4 sections:

{titles['problem']}
- Integrate problem situation from existing summary with new content
- Customer company and contact information (actual customer, NOT support agent)
- Technical issues or business requirements
- Related products/services/systems (use exact names from original)
- Important dates, deadlines, urgency factors
- Customer's specific questions or concerns

{titles['cause']}
- Primary Cause: Main technical or business factor causing the issue
- Contributing Factors: Additional elements that led to or amplified the problem
- System Context: Changes in environment, policies, or setup
- Dependencies: External systems, services, or decisions that influenced the situation

{titles['solution']}
- Current Status: What stage the resolution is at right now
- Completed Actions: Date-specific actions taken and their results
- In Progress: What is currently being worked on
- Next Steps: Planned specific actions (with responsible party if mentioned)
- Expected Timeline: When full resolution is anticipated
- Verification: How success will be measured or confirmed

{titles['insights']}
- Technical Specifications: Settings, configurations, and technical parameters

- Service Requirements: Limitations, dependencies, and compatibility needs
- Process Insights: Best practices, workflows, and procedural knowledge
- Reference Materials: Mentioned documentation, tools, resources, and attachments
  - For file attachments: Include filename, type, and reference as "📎 [filename] (Type: [type])" 
  - For documents: Include document names and relevant URLs if mentioned
  - For tools/systems: Include names and key configuration details
- Future Considerations: Recommendations for similar cases or preventive measures

STRICTLY FORBIDDEN:
- Adding fallback phrases like "insufficient information provided" or "원문에서 충분한 정보가 제공되지 않아"
- Adding disclaimers like "more information needed" or "추가 정보 제공 시"
- Adding speculative phrases like "resolution process not yet started" or "해결 과정이 아직 시작되지 않았습니다"
- Adding parenthetical explanations not in original text

INTEGRATION PRINCIPLES:
- Preserve key information from existing summary while integrating new information
- Naturally merge overlapping content
- Clearly express chronological order and causal relationships
- Be concise but NEVER omit important information
- Preserve original expressions as much as possible
- Record only facts accurately
- Respond in the appropriate language based on content (Korean for Korean content, English for English content)"""


async def _generate_final_integration(combined_summaries: str, content_type: str, ui_language: str) -> str:
    """여러 요약을 하나의 통합 요약으로 재구성 - 구조화된 템플릿 유지 (영어 프롬프트)"""
    
    # 섹션 타이틀 가져오기
    titles = get_section_titles(ui_language)
    
    # 모든 언어에 대해 영어 프롬프트 사용 (AI 이해도 향상)
    integration_prompt = f"""The following are summaries of different parts of a long ticket.
Please integrate them into one coherent final summary maintaining the 4-section structure.

=== DIVIDED SUMMARIES ===
{combined_summaries}

=== REQUIRED OUTPUT ===
Analyze the divided summaries and create an integrated summary with the following 4 sections:

{titles['problem']}
- Integrate problem situations from all divided summaries
- Customer company and contact information (actual customer, NOT support agent)
- Overall technical issues or business requirements
- All related products/services/systems (use exact terminology from original)
- All important dates, deadlines, urgency factors
- All customer questions and concerns

{titles['cause']}
- Primary Cause: Integrated root cause analysis
- Contributing Factors: All contributing elements
- System Context: Overall environmental/policy changes
- Dependencies: All related dependencies

{titles['solution']}
- Current Status: Overall current stage of resolution process
- Actions Completed: All date-specific actions and results integrated
- In Progress: All currently ongoing work
- Next Steps: All planned actions
- Expected Timeline: Overall completion timeline
- Verification: Integrated success measurement methods

{titles['insights']}
- Technical Specifications: All technical settings and configurations
- Service Requirements: All limitations and requirements
- Process Insights: Integrated best practices and procedures
- Reference Materials: All related documentation, resources, and attachments
  - For file attachments: Include filename, type, and reference as "📎 [filename] (Type: [type])"
  - For documents: Include document names and relevant URLs if mentioned  
  - For tools/systems: Include names and key configuration details
- Future Considerations: Comprehensive recommendations and preventive measures

STRICTLY FORBIDDEN:
- Adding fallback phrases like "insufficient information provided" or "원문에서 충분한 정보가 제공되지 않아"
- Adding disclaimers like "more information needed" or "추가 정보 제공 시"
- Adding speculative phrases like "resolution process not yet started" or "해결 과정이 아직 시작되지 않았습니다"
- Adding parenthetical explanations not in original text

INTEGRATION PRINCIPLES:
- Naturally merge overlapping content
- Clarify overall chronological order and causal relationships
- Integrate all important information (never omit)
- Preserve original terminology as much as possible
- Record facts accurately only
- Respond in the appropriate language based on content (Korean for Korean content, English for English content)"""
    
    return await generate_optimized_summary(
        content=integration_prompt,
        content_type="integration",
        subject="통합 요약",
        metadata={"summary_type": "integration"},
        ui_language=ui_language
    )
# ==========================================
# MIGRATION GUIDE AND CLEANUP STATUS
# ==========================================

"""
LEGACY FILE CLEANUP STATUS:

✅ MIGRATED TO NEW SYSTEM:
- generate_optimized_summary() → summarizer.core.summarizer
- get_section_titles() → summarizer.utils.language  
- get_subsection_titles() → summarizer.utils.language
- _get_optimized_system_prompt() → summarizer.prompt.builder
- _build_optimized_user_prompt() → summarizer.prompt.builder
- _select_relevant_attachments() → summarizer.attachment.selector
- _validate_summary_quality() → summarizer.quality.validator
- detect_content_language() → summarizer.utils.language
- preprocess_email_chain() → summarizer.email.processor
- generate_hybrid_summary() → summarizer.hybrid.summarizer
- AdaptiveContextManager → summarizer.context.optimizer
- QualityGuard → summarizer.quality.validator
- OptimizedSummarizer → summarizer.core.summarizer

🔄 CURRENT STATUS:
- All public functions now redirect to new modular system
- Backward compatibility maintained via wrapper functions
- Deprecation warnings issued for all legacy usage
- Internal helper functions marked as deprecated

📋 TODO FOR COMPLETE CLEANUP:
1. Monitor usage patterns to ensure no critical dependencies
2. Remove internal helper functions after 1-2 releases
3. Eventually remove this entire file
4. Update all imports across codebase to use new system

🚀 NEW SYSTEM BENEFITS:
- Modular architecture for better maintainability
- YAML-based prompt templates for easy management
- LLM-based attachment selection (1-3 relevant only)
- Advanced quality validation with regeneration
- Adaptive strategies for large content
- Comprehensive test coverage
- Clear separation of concerns

📖 MIGRATION EXAMPLES:

OLD WAY:
    from backend.core.llm.optimized_summarizer import generate_optimized_summary
    summary = await generate_optimized_summary(content, "ticket", ui_language="ko")

NEW WAY:
    from backend.core.llm.summarizer import generate_optimized_summary
    summary = await generate_optimized_summary(content, "ticket", ui_language="ko")

ADVANCED USAGE:
    from backend.core.llm.summarizer import CoreSummarizer, HybridSummarizer
    
    # For standard summarization
    core = CoreSummarizer()
    summary = await core.generate_summary(content, metadata=metadata)
    
    # For large content with adaptive strategies
    hybrid = HybridSummarizer()
    summary = await hybrid.generate_hybrid_summary(large_content)

DIRECT COMPONENT USAGE:
    from backend.core.llm.summarizer import PromptBuilder, AttachmentSelector
    
    # Custom prompt building
    builder = PromptBuilder()
    prompt = builder.build_system_prompt("knowledge_base", "ko", "ko")
    
    # Smart attachment selection
    selector = AttachmentSelector()
    relevant = selector.select_relevant_attachments(attachments, content, subject)

This file will be removed in a future release once migration is complete.
"""
