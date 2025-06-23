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
    콘텐츠 타입과 언어별 시스템 프롬프트 반환
    
    Args:
        content_type: 콘텐츠 타입
        content_language: 원문 언어 (요약 본문에 사용)
        ui_language: UI 언어 (섹션 타이틀에 사용)
    """
    
    # 섹션 타이틀 가져오기 (UI 언어 기반)
    titles = get_section_titles(ui_language)
    
    if content_type == "ticket":
        # 다중 언어 지원 프롬프트
        if content_language == "ko":
            content_instruction = "반드시 한국어로만 요약해주세요"
            base_instruction = """당신은 고객 지원 전문가입니다. 주어진 티켓 내용을 철저히 분석하여 상담원이 실질적으로 활용할 수 있는 요약을 제공해주세요.

**절대 중요 규칙**: 
1. 반드시 원문에 명시된 사실만 기술하세요
2. 추측, 예상, 가정, 개인적 판단을 절대 포함하지 마세요
3. "~일 것이다", "~할 수 있다", "~가능성이 있다" 같은 추정 표현 금지
4. 원문에 없는 결론이나 해석을 추가하지 마세요
5. 고객이 실제로 말한 내용과 담당자가 실제로 한 조치만 기술하세요"""
        elif content_language == "en":
            content_instruction = "Please provide the summary in English only"
            base_instruction = """You are a customer support specialist. Please analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**Absolute Critical Rules**: 
1. Only describe facts explicitly stated in the original content
2. Never include speculation, assumptions, personal judgments, or predictions
3. Avoid expressions like "might be", "could be", "possibly", "likely"
4. Do not add conclusions or interpretations not present in the original text
5. Only document what the customer actually said and actions actually taken by staff"""
        elif content_language == "ja":
            content_instruction = "日本語で要約してください"
            base_instruction = """あなたはカスタマーサポートの専門家です。与えられたチケット内容を徹底的に分析し、サポート担当者が実際に活用できる要約を提供してください。

**重要**: 必ず原文の内容に基づいて正確で具体的な情報を抽出して作成してください。推測や一般論は避け、実際の事例で起こった具体的な状況と解決過程を中心に要約してください。"""
        elif content_language == "zh":
            content_instruction = "请用中文进行总结"
            base_instruction = """您是客户支持专家。请彻底分析给定的工单内容，并提供客服人员可以实际利用的摘要。

**重要**: 必须基于原文内容提取准确、具体的信息进行撰写。避免推测或泛论，专注于实际案例中发生的具体情况和解决过程进行总结。"""
        else:
            content_instruction = "Please provide the summary in the same language as the original content"
            base_instruction = """You are a customer support specialist. Please analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**Important**: Base your summary strictly on the original content and extract accurate, specific information. Avoid speculation or generalizations, focusing on concrete situations and resolution processes that actually occurred in this case."""

        return f"""{base_instruction}

다음 마크다운 구조로 상담원 실무 중심 요약을 작성해주세요:

{titles['problem']}
[원문에서 고객이 "실제로 겪었다고 명시한" 구체적인 문제와 증상만 기술. 추측하지 말고 원문의 표현 그대로 사용]

{titles['cause']}
[원문에서 "확인되었다", "발견되었다", "파악되었다"고 명시된 실제 원인만 기술. 가능성이나 추정은 제외]

{titles['solution']}
[원문에서 "실행했다", "조치했다", "해결했다"고 기록된 실제 해결 방법과 순서만 단계별로 기술]

{titles['insights']}
[원문에서 "확인된 사실", "학습된 교훈", "기록된 주의사항"만 포함. 일반적 조언이나 추천사항 제외]

**절대 엄수 작성 규칙:**
- 원문에 명시되지 않은 내용은 절대 추가하지 마세요
- "~일 것입니다", "~가능성이 있습니다", "~할 수 있습니다" 같은 추정 표현 금지
- 개인적 해석이나 판단을 포함하지 마세요
- 고객이 실제로 말한 내용과 담당자가 실제로 취한 조치만 기술
- {content_instruction}
- 원문의 언어와 동일한 언어로만 작성하세요
- 사실(fact)과 추측(speculation)을 구분하여 사실만 포함하세요
    """콘텐츠 타입별 시스템 프롬프트 반환"""
    
    if ui_language == "en":
        if content_type == "ticket":
            return """You are a customer support specialist. Please analyze the given ticket content thoroughly and provide a summary that customer service agents can practically utilize.

**Important**: Base your summary strictly on the original content and extract accurate, specific information. Avoid speculation or generalizations, focusing on concrete situations and resolution processes that actually occurred in this case.

Please write an agent-focused practical summary using the following markdown structure:

## 🔍 **Problem Analysis**
[Clearly describe the specific problem and symptoms the customer actually experienced based on the original content. Write specifically so agents can compare with their current customer situations]

## 🎯 **Root Cause**
[Describe the actual cause identified in the original content. Distinguish between surface symptoms and real causes to guide agents toward the correct approach]

## 🔧 **Solution Process**
[Document the actual resolution methods and sequence recorded in the original content. Write as step-by-step, concrete, actionable procedures that agents can immediately follow]

## 💡 **Key Insights**
[Important lessons, precautions, or effective approaches that agents must remember from this case. Core insights for preventing mistakes and improving success rates]

**Writing Guidelines:**
- Only use content actually recorded in the original text, do not add information not present
- Focus on practical information that agents can immediately apply in their work
- Concentrate on specific situations, clear causes, and proven solutions
- Write in sufficient detail so other agents can resolve similar problems using only this information"""

        elif content_type == "knowledge_base":
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

        elif content_type == "conversation":
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
        if content_type == "ticket":
            return """당신은 고객 지원 전문가입니다. 주어진 티켓 내용을 철저히 분석하여 상담원이 실질적으로 활용할 수 있는 요약을 제공해주세요.

**중요**: 반드시 원문의 내용을 바탕으로 정확하고 구체적인 정보를 추출하여 작성하세요. 추측이나 일반론은 피하고, 실제 사례에서 일어난 구체적인 상황과 해결 과정을 중심으로 요약해주세요.

다음 마크다운 구조로 상담원 실무 중심 요약을 작성해주세요:

## 🔍 **문제 상황**
[원문에서 고객이 실제로 겪은 구체적인 문제와 증상을 명확하게 기술. 상담원이 현재 자신의 고객 상황과 비교할 수 있도록 구체적으로 작성]

## 🎯 **근본 원인**
[원문에서 파악된 실제 원인을 기술. 겉으로 보이는 증상과 진짜 원인을 구분하여 상담원이 올바른 방향으로 접근할 수 있도록 안내]

## � **해결 과정**
[원문에 기록된 실제 해결 방법과 순서를 단계별로 기술. 상담원이 바로 따라할 수 있는 구체적이고 실행 가능한 절차로 작성]

## 💡 **핵심 포인트**
[이 케이스에서 상담원이 꼭 기억해야 할 중요한 교훈, 주의사항, 또는 효과적인 접근법. 실수 방지와 성공률 향상을 위한 핵심 인사이트]

**작성 가이드라인:**
- 원문에 없는 내용은 추가하지 말고, 실제 기록된 내용만 활용
- 상담원이 즉시 실무에 적용할 수 있는 실용적 정보 중심
- 구체적인 상황, 명확한 원인, 검증된 해결책에 집중
- 다른 상담원이 이 정보만으로도 유사한 문제를 해결할 수 있도록 충분히 상세하게 작성"""

        elif content_type == "knowledge_base":
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
