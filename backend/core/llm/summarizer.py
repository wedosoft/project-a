"""
LLM 요약 생성기

티켓과 KB 문서에 대한 상담원용 요약을 생성합니다.
"""

import logging
import re
from typing import Dict, Any, Optional
from .manager import LLMManager

logger = logging.getLogger(__name__)

# 전역 LLM 매니저 인스턴스
llm_manager = LLMManager()


def detect_content_language(content: str) -> str:
    """
    콘텐츠 언어 자동 감지 (더 정확한 감지 로직)
    
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
    
    # 디버깅 로그 추가
    logger.debug(f"언어 감지 - 총 문자수: {total_chars}, 한국어: {korean_ratio:.2f}, 영어: {english_ratio:.2f}, 일본어: {japanese_ratio:.2f}, 중국어: {chinese_ratio:.2f}")
    
    # 언어 결정 (더 엄격한 임계값)
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
        logger.debug(f"혼합 언어에서 최대 비율 언어: {max_lang}")
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


async def generate_summary(
    content: str,
    content_type: str = "ticket",
    subject: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    ui_language: str = "ko"  # UI 언어 (섹션 타이틀용)
) -> str:
    """
    콘텐츠에 대한 상담원용 요약을 생성합니다.
    
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
        # 원문 언어 자동 감지 (요약 본문용)
        content_language = detect_content_language(content)
        logger.debug(f"감지된 원문 언어: {content_language}")
        
        # 콘텐츠 타입별 프롬프트 생성
        prompt = _build_summary_prompt(
            content=content,
            content_type=content_type,
            subject=subject,
            metadata=metadata or {},
            content_language=content_language,
            ui_language=ui_language
        )
        
        # LLM 요청
        response = await llm_manager.generate(
            messages=[
                {"role": "system", "content": _get_system_prompt(content_type, content_language, ui_language)},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,  # 요약 토큰 수 증가 (한국어 기준 800-1600글자)
            temperature=0.3,  # 일관성 있는 요약
            model_preference=["gpt-4o-mini", "gpt-3.5-turbo"]  # 비용 효율적인 모델
        )
        
        if response and response.content:
            summary = response.content.strip()
            
            # 언어 일관성 검증
            detected_summary_lang = detect_content_language(summary)
            if content_language == "ko" and detected_summary_lang != "ko":
                logger.warning(f"언어 불일치 감지: 원문({content_language}) vs 요약({detected_summary_lang})")
                # 한국어로 다시 요청
                retry_prompt = f"{prompt}\n\n중요: 반드시 한국어로만 작성해주세요. 영어나 다른 언어는 절대 사용하지 마세요."
                retry_response = await llm_manager.generate(
                    messages=[
                        {"role": "system", "content": _get_system_prompt(content_type, content_language, ui_language)},
                        {"role": "user", "content": retry_prompt}
                    ],
                    max_tokens=800,
                    temperature=0.1,  # 더 엄격하게
                    model_preference=["gpt-4o-mini", "gpt-3.5-turbo"]
                )
                if retry_response and retry_response.content:
                    summary = retry_response.content.strip()
            
            # 주관적 표현 검증
            subjective_patterns = [
                r'일\s*것\s*입니다', r'일\s*것\s*이다', r'할\s*수\s*있습니다', 
                r'가능성이', r'추정됩니다', r'예상됩니다', r'것으로\s*보입니다',
                r'might\s+be', r'could\s+be', r'possibly', r'likely', r'probably'
            ]
            
            for pattern in subjective_patterns:
                if re.search(pattern, summary, re.IGNORECASE):
                    logger.warning(f"주관적 표현 감지: {pattern}")
                    break
            
            logger.debug(f"{content_type} 요약 생성 완료 (길이: {len(summary)})")
            return summary
        else:
            logger.warning(f"{content_type} 요약 생성 실패: 빈 응답")
            return f"[{content_type} 요약 생성 실패]"
            
    except Exception as e:
        logger.error(f"{content_type} 요약 생성 중 오류: {e}")
        return f"[요약 생성 오류: {str(e)}]"

def _get_system_prompt(content_type: str, content_language: str = "ko", ui_language: str = "ko") -> str:
    """
    콘텐츠 타입과 언어별 시스템 프롬프트 반환 (영어 프롬프트 사용)
    """
    
    if content_type == "ticket":
        return """You are an expert customer support analyst specializing in ticket summarization. Your role is to create precise, factual summaries that enable customer service agents to quickly understand and act on ticket content.

CORE PRINCIPLES:
- Extract only explicitly stated facts from the original content
- Never add interpretations, assumptions, or speculation
- Focus on actionable information for customer service agents
- Be thorough in capturing all mentioned actions and resolutions
- Distinguish clearly between what was done vs. what was planned
- Pay special attention to administrative actions (deletions, modifications, restorations)
- CRITICAL: Extract ALL completion statements and resolution confirmations

COMPLETION DETECTION (MOST IMPORTANT):
- Korean completion indicators: 처리했습니다, 해드렸습니다, 복구했습니다, 조치했습니다, 삭제했습니다, 완료했습니다, 수정했습니다
- English completion indicators: processed, completed, resolved, restored, deleted, modified, fixed, updated
- Customer satisfaction indicators: 잘확인했습니다, 감사드립니다, confirmed, satisfied, resolved
- Staff response patterns: "요청하신 [X]에 대해서 [처리/복구/삭제]했습니다"

RESPONSE LANGUAGE: Always respond in the same language as the original content. If original is Korean, respond in Korean. If English, respond in English, etc.

PROHIBITED BEHAVIORS:
- Missing completion statements (this is the most critical error)
- Adding information not present in the original text
- Using probabilistic language ("might", "could", "possibly")
- Making assumptions about unstated causes or solutions
- Generalizing specific incidents into broad advice"""

    elif content_type == "knowledge_base":
        return """You are a knowledge management specialist who analyzes KB documents to create structured summaries for customer service agents.

CORE PRINCIPLES:
- Focus on practical applicability for customer support scenarios
- Extract step-by-step procedures clearly
- Identify prerequisites and limitations
- Highlight critical precautions to prevent errors
- Organize information for quick reference during customer interactions

RESPONSE LANGUAGE: Always respond in the same language as the original content.

ANALYSIS FOCUS:
- When and how to use this knowledge
- Step-by-step implementation guidance
- Common pitfalls and how to avoid them
- Integration with customer service workflows"""

    elif content_type == "conversation":
        return """You are a conversation analysis expert who summarizes customer interactions to facilitate smooth handoffs between agents.

CORE PRINCIPLES:
- Track resolution status of each discussed issue
- Identify customer emotional journey and current state
- Highlight pending actions and follow-up requirements
- Provide context for next agent interaction
- Distinguish between resolved, in-progress, and unresolved items

RESPONSE LANGUAGE: Always respond in the same language as the original content.

ANALYSIS FOCUS:
- What was accomplished in this conversation
- What needs to happen next
- Customer's current satisfaction and understanding level
- Critical context for continuing the relationship"""

    return """You are a content analysis expert. Create a clear, factual summary focusing only on information explicitly stated in the original content.

RESPONSE LANGUAGE: Always respond in the same language as the original content."""
    
    if content_type == "ticket":
        # 섹션 타이틀 가져오기 (UI 언어 기반)
        titles = get_section_titles(ui_language)
        
        # 영어 프롬프트 사용 (더 정확한 이해를 위해)
        if content_language == "ko":
            content_instruction = "MUST respond in Korean only"
            base_instruction = """You are a customer support specialist. Analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**CRITICAL RULES - MUST FOLLOW EXACTLY**: 
1. ONLY describe facts that are explicitly stated in the original content
2. NEVER include speculation, assumptions, personal judgments, or predictions
3. PROHIBIT expressions like "might be", "could be", "possibly", "likely", "probably"
4. DO NOT add conclusions or interpretations not present in the original text
5. ONLY document what the customer actually said and actions actually taken by staff
6. If information is not explicitly stated in the original content, you MUST write "원문에 명시되지 않음" (Not specified in original)
7. Extract ALL action verbs like: processed, deleted, removed, modified, changed, completed, resolved, restored, updated, patched
8. Pay special attention to: data/document/file deletion, setting changes, account/permission actions, system resets, recovery operations"""
        elif content_language == "en":
            content_instruction = "MUST respond in English only"
            base_instruction = """You are a customer support specialist. Analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**CRITICAL RULES - MUST FOLLOW EXACTLY**: 
1. ONLY describe facts that are explicitly stated in the original content
2. NEVER include speculation, assumptions, personal judgments, or predictions
3. PROHIBIT expressions like "might be", "could be", "possibly", "likely", "probably"
4. DO NOT add conclusions or interpretations not present in the original text
5. ONLY document what the customer actually said and actions actually taken by staff
6. If information is not explicitly stated in the original content, you MUST write "Not specified in original text"
7. Extract ALL action verbs like: processed, deleted, removed, modified, changed, completed, resolved, restored, updated, patched
8. Pay special attention to: data/document/file deletion, setting changes, account/permission actions, system resets, recovery operations"""
        elif content_language == "ja":
            content_instruction = "MUST respond in Japanese only"
            base_instruction = """You are a customer support specialist. Analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**CRITICAL RULES - MUST FOLLOW EXACTLY**: 
1. ONLY describe facts that are explicitly stated in the original content
2. NEVER include speculation, assumptions, personal judgments, or predictions
3. PROHIBIT expressions like "might be", "could be", "possibly", "likely", "probably"
4. DO NOT add conclusions or interpretations not present in the original text
5. ONLY document what the customer actually said and actions actually taken by staff
6. If information is not explicitly stated in the original content, you MUST write "原文に明記されていません"
7. Extract ALL action verbs like: processed, deleted, removed, modified, changed, completed, resolved, restored, updated, patched
8. Pay special attention to: data/document/file deletion, setting changes, account/permission actions, system resets, recovery operations"""
        elif content_language == "zh":
            content_instruction = "MUST respond in Chinese only"
            base_instruction = """You are a customer support specialist. Analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**CRITICAL RULES - MUST FOLLOW EXACTLY**: 
1. ONLY describe facts that are explicitly stated in the original content
2. NEVER include speculation, assumptions, personal judgments, or predictions
3. PROHIBIT expressions like "might be", "could be", "possibly", "likely", "probably"
4. DO NOT add conclusions or interpretations not present in the original text
5. ONLY document what the customer actually said and actions actually taken by staff
6. If information is not explicitly stated in the original content, you MUST write "原文中未明确说明"
7. Extract ALL action verbs like: processed, deleted, removed, modified, changed, completed, resolved, restored, updated, patched
8. Pay special attention to: data/document/file deletion, setting changes, account/permission actions, system resets, recovery operations"""
        else:
            content_instruction = "MUST respond in the same language as the original content"
            base_instruction = """You are a customer support specialist. Analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**CRITICAL RULES - MUST FOLLOW EXACTLY**: 
1. ONLY describe facts that are explicitly stated in the original content
2. NEVER include speculation, assumptions, personal judgments, or predictions
3. PROHIBIT expressions like "might be", "could be", "possibly", "likely", "probably"
4. DO NOT add conclusions or interpretations not present in the original text
5. ONLY document what the customer actually said and actions actually taken by staff
6. If information is not explicitly stated in the original content, you MUST write "Not specified in original text"
7. Extract ALL action verbs like: processed, deleted, removed, modified, changed, completed, resolved, restored, updated, patched
8. Pay special attention to: data/document/file deletion, setting changes, account/permission actions, system resets, recovery operations"""

        return f"""{base_instruction}

Please create a practical summary for customer service agents using the following markdown structure (RESPOND IN KOREAN):

{titles['problem']}
[Extract ONLY the specific problems and symptoms that the customer "actually experienced and explicitly stated" in the original text. Do not speculate, use the exact expressions from the original text]

{titles['cause']}
[Extract ONLY the actual causes that were "confirmed", "found", or "identified" as explicitly stated in the original text. Exclude possibilities or assumptions. If not stated, write "원문에 명시되지 않음"]

{titles['solution']}
[CRITICAL: Extract ALL actual resolution methods and actions that staff explicitly stated they completed. Look for completion language like:
- "처리했습니다", "해드렸습니다", "복구했습니다", "조치했습니다"  
- "삭제했습니다", "수정했습니다", "변경했습니다", "완료했습니다"
- "restored", "processed", "completed", "resolved", "deleted", "modified"
Also extract:
- Data/document/file deletion or removal operations that were COMPLETED
- Configuration changes or modifications that were PERFORMED
- Account/permission actions that were TAKEN
- System resets, recovery operations that were EXECUTED
- Customer confirmations like "잘확인했습니다", "감사드립니다"
List everything step-by-step as mentioned. If no completed actions are stated, write "원문에 명시되지 않음"]

{titles['insights']}
[Include ONLY "confirmed facts", "learned lessons", "recorded precautions", "follow-up actions", "prevention methods" from the original text. Exclude general advice or recommendations. If not stated, write "원문에 명시되지 않음"]

**ABSOLUTE COMPLIANCE RULES:**
- NEVER miss completion statements like "복구처리 해드렸습니다" - these are critical facts
- Look specifically for past tense completion verbs in Korean and English
- Extract customer satisfaction confirmations if mentioned
- Pay extra attention to staff responses containing completed actions
- Prohibit expressions like "~will be", "~might be", "~could be"
- Do not include personal interpretations or judgments
- Document ALL actual customer statements and ALL actions taken by staff without omission
- {content_instruction}
- Write in the same language as the original content
- Distinguish between facts and speculation, include only facts
- Clearly record ALL work expressed as "completed", "processed", "deleted", "resolved" in the original text
- Be thorough and comprehensive in extracting information
"""

    elif content_type == "knowledge_base":
        if ui_language == "en":
            return """You are a knowledge management specialist and analyst. Please provide a structured analytical summary of the given KB document.

Please write an analytical summary using the following markdown structure:

## 📚 **Document Overview**
[Explain the document's purpose and core value in two to three sentences]

## 🎯 **Application Scenarios**
- **Target Customers**: [What customer problems/situations this applies to]
- **Usage Timing**: [When to utilize this document]
- **Application Scope**: [Range of problems that can be resolved]

## 🔧 **Core Resolution Methods**
### 1️⃣ **[Major Step 1]**
- [Specific methods or procedures]

### 2️⃣ **[Major Step 2]**
- [Specific methods or procedures]

### 3️⃣ **[Major Step 3]**
- [Specific methods or procedures]

## ⚠️ **Important Precautions**
- **Prerequisites**: [Things to check before using this method]
- **Limitations**: [Situations where it cannot be applied or constraints]
- **Risks**: [Side effects if misapplied]

## 🏷️ **Document Characteristics**
- **Complexity**: [Beginner/Intermediate/Advanced]
- **Document Type**: [Guide/FAQ/Policy/Procedure/Technical Document]
- **Update Status**: [Information about currency]

## 💡 **Agent Utilization Tips**
[How to effectively utilize this KB for customer support]

**Writing Guidelines:**
- Provide practical information that agents can immediately apply to customer problem resolution
- Write step-by-step methods to be specific and actionable
- Clearly mark precautions so agents avoid mistakes
- Structure with emojis and organization for quick scanning"""
        else:  # 기본값: 한국어
            return """당신은 지식 관리 전문 분석가입니다. 주어진 KB 문서를 분석적 관점에서 구조화된 요약을 제공해주세요.

다음과 같은 마크다운 구조로 분석적 요약을 작성해주세요:

## 📚 **문서 개요**
[문서의 목적과 핵심 가치를 두세 문장으로 설명]

## 🎯 **적용 상황**
- **대상 고객**: [어떤 고객 문제/상황에 적용되는지]
- **사용 시점**: [언제 이 문서를 활용해야 하는지]
- **적용 범위**: [해결 가능한 문제의 범위]

## 🔧 **핵심 해결 방법**
### 1️⃣ **[주요 단계 1]**
- [구체적인 방법이나 절차]

### 2️⃣ **[주요 단계 2]**
- [구체적인 방법이나 절차]

### 3️⃣ **[주요 단계 3]**
- [구체적인 방법이나 절차]

## ⚠️ **중요 주의사항**
- **전제조건**: [이 방법을 사용하기 전에 확인해야 할 것들]
- **제약사항**: [적용할 수 없는 상황이나 한계]
- **리스크**: [잘못 적용했을 때의 부작용]

## 🏷️ **문서 특성**
- **복잡도**: [초급/중급/고급]
- **문서 유형**: [가이드/FAQ/정책/절차/기술문서]
- **업데이트**: [최신성 관련 정보]

## 💡 **상담원 활용 팁**
[이 KB를 고객 응대에 효과적으로 활용하는 방법]

**작성 가이드라인:**
- 상담원이 고객 문제 해결에 즉시 적용할 수 있는 실용적 정보 제공
- 단계별 방법은 구체적이고 실행 가능하도록 작성
- 주의사항은 상담원이 실수하지 않도록 명확히 표시
- 이모지와 구조화를 통해 빠른 스캔 가능하도록 구성"""

    elif content_type == "conversation":
        if ui_language == "en":
            return """You are a customer conversation analysis expert. Please provide a structured analytical summary of the given conversation content.

Please write an analytical summary using the following markdown structure:

## 💬 **Conversation Flow Summary**
[Summarize the overall flow of conversation and major turning points chronologically]

## ✅ **Resolved Items**
- [Successfully resolved problems]
- [Solutions provided]
- [Areas where customer was satisfied]

## 🔄 **Items in Progress**
- [Currently ongoing issues]
- [Pending action items]
- [Items requiring additional confirmation]

## ⏳ **Unresolved Items**
- [Problems not yet resolved]
- [Customer's additional requirements]
- [Items requiring escalation]

## 📈 **Customer Status Analysis**
- **Satisfaction**: [High/Medium/Low/Dissatisfied]
- **Understanding**: [Sufficient/Medium/Insufficient]
- **Cooperation**: [Proactive/Medium/Passive]
- **Emotional Change**: [Improved/Maintained/Deteriorated]

## 🎯 **Key Focus for Next Consultation**
[Core information and considerations the next agent should know]

**Writing Guidelines:**
- Structure so agents can quickly understand conversation context
- Clearly categorize resolution status to provide direction for follow-up actions
- Analytically assess customer's emotional state and changes
- Provide practical information to enhance next consultation efficiency"""
        else:  # 기본값: 한국어
            return """당신은 고객 대화 분석 전문가입니다. 주어진 대화 내용을 분석적 관점에서 구조화된 요약을 제공해주세요.

다음과 같은 마크다운 구조로 분석적 요약을 작성해주세요:

## 💬 **대화 흐름 요약**
[대화의 전체적인 흐름과 주요 전환점을 시간순으로 요약]

## ✅ **해결된 사항**
- [성공적으로 해결된 문제들]
- [제공된 솔루션들]
- [고객이 만족한 부분]

## 🔄 **진행 중인 사항**
- [현재 진행 중인 이슈]
- [대기 중인 액션 아이템]
- [추가 확인이 필요한 사항]

## ⏳ **미해결 사항**
- [아직 해결되지 않은 문제]
- [고객의 추가 요구사항]
- [에스컬레이션이 필요한 항목]

## 📈 **고객 상태 분석**
- **만족도**: [높음/보통/낮음/불만]
- **이해도**: [충분/보통/부족]
- **협조도**: [적극적/보통/소극적]
- **감정 변화**: [개선/유지/악화]

## 🎯 **다음 상담 시 중점사항**
[다음 상담원이 알아야 할 핵심 정보와 고려사항]

**작성 가이드라인:**
- 상담원이 대화 맥락을 빠르게 이해할 수 있도록 구성
- 해결 상태를 명확히 분류하여 후속 조치 방향 제시
- 고객의 감정 상태와 변화를 분석적으로 파악
- 다음 상담의 효율성을 높이는 실용적 정보 제공"""

    # 처리할 content_type이 없는 경우 기본 프롬프트 반환
    return "Please provide a concise summary of the following content."


def _build_summary_prompt(
    content: str,
    content_type: str,
    subject: str = "",
    metadata: Dict[str, Any] = None,
    content_language: str = "ko",
    ui_language: str = "ko"
) -> str:
    """
    요약 프롬프트 구성
    
    Args:
        content: 요약할 내용
        content_type: 콘텐츠 타입
        subject: 제목
        metadata: 메타데이터
        content_language: 원문 언어 (자동 감지됨)
        ui_language: UI 언어 (섹션 타이틀용)
    """
    
    prompt_parts = []
    
    # 제목 정보 (원문 언어에 맞춰)
    if subject:
        if content_language in ["ko"]:
            prompt_parts.append(f"제목: {subject}")
        elif content_language == "ja":
            prompt_parts.append(f"件名: {subject}")
        elif content_language == "zh":
            prompt_parts.append(f"标题: {subject}")
        else:  # 영어 및 기타
            prompt_parts.append(f"Subject: {subject}")
    
    # 메타데이터 정보 (원문 언어에 맞춰)
    if metadata:
        meta_info = []
        if content_language in ["ko"]:
            if metadata.get('status'):
                meta_info.append(f"상태: {metadata['status']}")
            if metadata.get('priority'):
                meta_info.append(f"우선순위: {metadata['priority']}")
            if metadata.get('category_id'):
                meta_info.append(f"카테고리: {metadata['category_id']}")
            if meta_info:
                prompt_parts.append(f"메타정보: {', '.join(meta_info)}")
        elif content_language == "ja":
            if metadata.get('status'):
                meta_info.append(f"ステータス: {metadata['status']}")
            if metadata.get('priority'):
                meta_info.append(f"優先度: {metadata['priority']}")
            if metadata.get('category_id'):
                meta_info.append(f"カテゴリー: {metadata['category_id']}")
            if meta_info:
                prompt_parts.append(f"メタ情報: {', '.join(meta_info)}")
        elif content_language == "zh":
            if metadata.get('status'):
                meta_info.append(f"状态: {metadata['status']}")
            if metadata.get('priority'):
                meta_info.append(f"优先级: {metadata['priority']}")
            if metadata.get('category_id'):
                meta_info.append(f"分类: {metadata['category_id']}")
            if meta_info:
                prompt_parts.append(f"元信息: {', '.join(meta_info)}")
        else:  # 영어 및 기타
            if metadata.get('status'):
                meta_info.append(f"Status: {metadata['status']}")
            if metadata.get('priority'):
                meta_info.append(f"Priority: {metadata['priority']}")
            if metadata.get('category_id'):
                meta_info.append(f"Category: {metadata['category_id']}")
            if meta_info:
                prompt_parts.append(f"Metadata: {', '.join(meta_info)}")
    
    # 콘텐츠
    prompt_parts.append(f"내용:\n{content}" if content_language == "ko" 
                       else f"内容:\n{content}" if content_language == "zh"
                       else f"内容:\n{content}" if content_language == "ja"
                       else f"Content:\n{content}")
    
    # 요약 요청 (원문 언어에 맞춰)
    if content_language == "ko":
        prompt_parts.append("\n위 내용을 상담원용으로 요약해주세요:")
    elif content_language == "ja":
        prompt_parts.append("\n上記の内容をサポート担当者向けに要約してください:")
    elif content_language == "zh":
        prompt_parts.append("\n请为客服人员总结上述内容:")
    else:  # 영어 및 기타
        prompt_parts.append("\nPlease summarize the above content for customer service agents:")
    
    return "\n\n".join(prompt_parts)


def validate_summary(summary: str, min_length: int = 10, max_length: int = 500) -> bool:
    """요약 품질 검증"""
    if not summary or not summary.strip():
        return False
    
    summary = summary.strip()
    
    # 길이 검증
    if len(summary) < min_length or len(summary) > max_length:
        return False
    
    # 오류 메시지 검증
    error_indicators = ["[", "오류", "실패", "Error", "Failed"]
    if any(indicator in summary for indicator in error_indicators):
        return False
    
    return True


# 동기 버전 (필요시)
def generate_summary_sync(
    content: str,
    content_type: str = "ticket",
    subject: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    language: str = "ko"
) -> str:
    """동기 버전의 요약 생성"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 실행 중인 이벤트 루프에서는 새 태스크 생성
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_summary(content, content_type, subject, metadata, language)
                )
                return future.result()
        else:
            return asyncio.run(
                generate_summary(content, content_type, subject, metadata, language)
            )
    except Exception as e:
        logger.error(f"동기 요약 생성 중 오류: {e}")
        return f"[요약 생성 오류: {str(e)}]"


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
