"""
최적화된 LLM 요약 생성기 - 영어 프롬프트 기반

티켓과 KB 문서에 대한 정확하고 상세한 요약을 생성합니다.
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple, Set
from .manager import LLMManager
from .models.base import LLMProvider

logger = logging.getLogger(__name__)

# 전역 LLM 매니저 인스턴스
llm_manager = LLMManager()


def detect_content_language(content: str) -> str:
    """
    콘텐츠 언어 자동 감지
    
    Args:
        content: 분석할 텍스트
        
    Returns:
        str: 감지된 언어 코드 ('ko', 'en', 'ja', 'zh', 'other')
    """
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
        logger.debug(f"감지된 원문 언어: {content_language}")
        
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
        
        # LLM 요청 - OpenAI 모델 강제 사용 (일관성 확보)
        response = await llm_manager.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1200,  # 상세한 요약을 위해 토큰 수 증가
            temperature=0.1,   # 매우 일관성 있는 요약 (더 낮게 조정)
            model_preference=["gpt-4o-mini"],  # OpenAI 단일 모델 강제 사용
            provider=LLMProvider.OPENAI  # LLMProvider enum 사용
        )
        
        if response and response.content:
            summary = response.content.strip()
            
            # 품질 검증
            quality_score = _validate_summary_quality(summary, content, content_language)
            logger.info(f"요약 품질 점수: {quality_score:.2f}")
            
            if quality_score < 0.7:  # 품질이 낮으면 재시도
                logger.warning("요약 품질이 낮아 재시도합니다.")
                retry_prompt = f"{user_prompt}\n\nIMPORTANT: The previous summary was inadequate. Please provide a more detailed and accurate summary that strictly follows the original content."
                retry_response = await llm_manager.generate(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": retry_prompt}
                    ],
                    max_tokens=1200,
                    temperature=0.05,  # 재시도 시 더욱 정확한 결과를 위해 낮게 설정
                    model_preference=["gpt-4o-mini"],  # OpenAI 단일 모델 강제 사용
                    provider=LLMProvider.OPENAI  # LLMProvider enum 사용
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
    최적화된 시스템 프롬프트 반환 - 영어 기반으로 정확성 향상
    """
    
    if content_type == "ticket":
        # 섹션 타이틀 가져오기
        titles = get_section_titles(ui_language)
        subtitles = get_subsection_titles(ui_language)
        
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

        return f"""You are an expert customer support analyst creating precise ticket summaries for field agents.

CRITICAL MISSION: Create summaries that preserve ALL essential business and technical information while remaining readable and actionable.

ABSOLUTE REQUIREMENTS:
1. NEVER omit proper nouns (company names, person names, product names, service names)
2. NEVER omit technical terms (MX records, DNS, domain names, etc.)
3. NEVER omit dates, times, or deadlines
4. NEVER generalize specific technical details
5. NEVER change or approximate numerical values, dates, or names
6. Include ALL customer questions and concerns explicitly stated
7. For Korean content: Include both English and Korean versions of key terms
   - Company names: Use format "English Name (한글명)" when both versions appear
   - Technical terms: Use format "English Term (한글용어)" for important technical concepts
   - Product/service names: Include both language versions when mentioned in original text
   - Always preserve exact domain names and URLs as they appear
   - Include all mentioned support company names exactly as written

STRUCTURE YOUR SUMMARY:

{titles['problem']}
- Customer company name and key contact person with role
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
- If truly no causes can be determined: "원문에서 충분한 정보가 제공되지 않아 원인 분석이 제한적입니다" + explain what additional info is needed

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
- If no resolution started: "해결 과정이 아직 시작되지 않았습니다" + list required first steps

{titles['insights']}
Key technical and procedural insights (EXCLUDE all customer contact information):
- {subtitles['insights']['technical']}: Settings, configurations, and technical parameters
- {subtitles['insights']['service']}: Limitations, dependencies, and compatibility needs
- {subtitles['insights']['process']}: Best practices, workflows, and procedural knowledge
- {subtitles['insights']['reference']}: Documentation, tools, and resources mentioned
- {subtitles['insights']['future']}: Recommendations for similar cases or preventive measures
- **IMPORTANT**: Never include customer names, phone numbers, emails, or personal identifiers

FORMATTING RULES:
- {language_instruction}
- Write concisely but preserve ALL critical details
- Use exact names, terms, and values from original text
- If original mentions specific technical terms, include them exactly
- Keep each section focused but comprehensive"""

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
5. For Korean content: Include both English and Korean versions of technical terms
   - Technical terms: Use format "English Term (한글용어)" for important concepts
   - Product names: Include both language versions when mentioned
   - Always preserve exact URLs, file names, and system names

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


def _build_optimized_user_prompt(
    content: str,
    content_type: str,
    subject: str,
    metadata: Dict[str, Any],
    content_language: str,
    ui_language: str
) -> str:
    """
    최적화된 사용자 프롬프트 구성
    """
    
    prompt_parts = []
    
    # 제목 포함 (있는 경우)
    if subject:
        prompt_parts.append(f"TICKET SUBJECT: {subject}")
    
    # 메타데이터 포함 (있는 경우)
    if metadata:
        metadata_str = ", ".join([f"{k}: {v}" for k, v in metadata.items() if v])
        if metadata_str:
            prompt_parts.append(f"METADATA: {metadata_str}")
    
    # 메인 콘텐츠
    prompt_parts.append("ORIGINAL CONTENT TO ANALYZE:")
    prompt_parts.append("=" * 50)
    prompt_parts.append(content)
    prompt_parts.append("=" * 50)
    
    # 분석 지시사항
    if content_language == "ko":
        instruction = """위 내용을 분석하여 실무진이 바로 활용할 수 있는 요약을 작성하세요.

절대 누락 금지 항목:
✅ 모든 회사명, 담당자명, 연락처 정보
✅ 모든 기술 용어 (MX레코드, DNS, Postini, Google Apps 등)  
✅ 모든 날짜와 시간 (정확한 연도 포함)
✅ 모든 도메인명, URL, 이메일 주소
✅ 고객의 모든 질문과 우려사항
✅ 서비스명과 제품명 (정확한 명칭 유지)

한영 병기 원칙:
- 회사명: 원문에 영문과 한글이 모두 나오면 "영문명 (한글명)" 형태로 표기
- 기술용어: 중요한 기술개념은 "English Term (한글용어)" 형태로 표기  
- 제품/서비스명: 원문에 언급된 경우 양쪽 언어 버전 모두 포함
- 도메인명과 URL: 원문에 나타난 그대로 정확히 보존
- 지원업체명: 언급된 모든 지원업체명을 원문 그대로 포함

작성 원칙:
- 간결하되 중요 정보는 절대 생략 금지
- 원문의 표현을 최대한 보존
- 추측이나 해석 절대 금지
- 사실만 정확히 기록"""
    else:
        instruction = """Analyze the content and create a summary that field staff can use immediately.

NEVER OMIT:
✅ All company names, contact persons, contact details
✅ All technical terms (MX records, DNS, Postini, Google Apps, etc.)
✅ All dates and times (include exact years)  
✅ All domain names, URLs, email addresses
✅ All customer questions and concerns
✅ Service names and product names (preserve exact terminology)

Writing principles:
- Be concise but NEVER omit important information
- Preserve original terminology as much as possible
- No speculation or interpretation
- Record facts accurately only"""
    
    prompt_parts.append(instruction)
    
    return "\n\n".join(prompt_parts)


def _validate_summary_quality(summary: str, original_content: str, content_language: str) -> float:
    """
    요약 품질 검증
    
    Returns:
        float: 품질 점수 (0.0 ~ 1.0)
    """
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
    """대용량 처리를 위한 적응형 컨텍스트 관리자"""
    
    def __init__(self):
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
    """대용량 처리 시 품질 보장"""
    
    def __init__(self):
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


# 기존 OptimizedSummarizer 클래스에 추가
class OptimizedSummarizer:
    # ...existing code...

    def __init__(self):
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
            response = await self.llm_manager.generate_response(
                system_prompt=enhanced_system_prompt,
                user_prompt=enhanced_user_prompt,
                provider=LLMProvider.OPENAI,  # 강제로 OpenAI 사용
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
