"""
LLM 요약 생성기

티켓과 KB 문서에 대한 상담원용 요약을 생성합니다.
"""

import logging
from typing import Dict, Any, Optional
from .manager import LLMManager

logger = logging.getLogger(__name__)

# 전역 LLM 매니저 인스턴스
llm_manager = LLMManager()


async def generate_summary(
    content: str,
    content_type: str = "ticket",
    subject: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    language: str = "ko"
) -> str:
    """
    콘텐츠에 대한 상담원용 요약을 생성합니다.
    
    Args:
        content: 요약할 내용
        content_type: 콘텐츠 타입 ("ticket", "knowledge_base", "conversation")
        subject: 제목 (티켓 subject, KB title 등)
        metadata: 추가 메타데이터 (상태, 우선순위 등)
        language: 요약 언어 (기본값: "ko")
        
    Returns:
        str: 생성된 요약
    """
    if not content or not content.strip():
        return "요약할 내용이 없습니다."
    
    try:
        # 콘텐츠 타입별 프롬프트 생성
        prompt = _build_summary_prompt(
            content=content,
            content_type=content_type,
            subject=subject,
            metadata=metadata or {},
            language=language
        )
        
        # LLM 요청
        response = await llm_manager.generate(
            messages=[
                {"role": "system", "content": _get_system_prompt(content_type, language)},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,  # 요약 토큰 수 증가 (한국어 기준 800-1600글자)
            temperature=0.3,  # 일관성 있는 요약
            model_preference=["gpt-4o-mini", "gpt-3.5-turbo"]  # 비용 효율적인 모델
        )
        
        if response and response.content:
            summary = response.content.strip()
            logger.debug(f"{content_type} 요약 생성 완료 (길이: {len(summary)})")
            return summary
        else:
            logger.warning(f"{content_type} 요약 생성 실패: 빈 응답")
            return f"[{content_type} 요약 생성 실패]"
            
    except Exception as e:
        logger.error(f"{content_type} 요약 생성 중 오류: {e}")
        return f"[요약 생성 오류: {str(e)}]"


def _get_system_prompt(content_type: str, language: str = "ko") -> str:
    """콘텐츠 타입별 시스템 프롬프트 반환"""
    
    if language == "ko":
        if content_type == "ticket":
            return """당신은 고객 지원 전문 분석가입니다. 주어진 티켓 내용을 분석적인 관점에서 구조화된 요약을 제공해주세요.

다음과 같은 마크다운 구조로 분석적 요약을 작성해주세요:

## 🎯 **핵심 상황**
[고객의 문제 상황을 두세 문장으로 명확하게 요약]

## 🔍 **문제 분석**
- **원인**: [근본적인 문제 원인 분석]
- **증상**: [고객이 경험하는 구체적 증상들]
- **영향도**: [비즈니스/고객에게 미치는 영향 수준]

## ⚡ **즉시 조치사항**
1. [우선순위 1 - 가장 긴급한 조치]
2. [우선순위 2 - 후속 조치]  
3. [우선순위 3 - 예방 조치]

## 📊 **상황 지표**
- **심각도**: [긴급/높음/보통/낮음]
- **복잡도**: [단순/보통/복합]
- **고객 감정**: [만족/중립/불만/분노]
- **예상 해결시간**: [즉시/하루이내/일주일이내/장기]

## 💡 **상담원 참고사항**
[상담원이 응대 시 알아야 할 중요한 배경지식이나 주의사항]

**작성 가이드라인:**
- 상담원이 15초 내에 전체 상황을 파악할 수 있도록 구성
- 이모지와 볼드체를 활용하여 시각적 구분 강화
- 분석적 사고에 기반한 구조화된 정보 제공
- 고객 감정과 비즈니스 임팩트를 함께 고려한 우선순위 제시"""

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

    else:  # English
        if content_type == "ticket":
            return """You are a customer support specialist and analyst. Please provide a structured analytical summary of the given ticket content.

Please write an analytical summary using the following markdown structure:

## 🎯 **Core Situation**
[Clearly summarize the customer's problem situation in two to three sentences]

## 🔍 **Problem Analysis**
- **Root Cause**: [Analysis of the fundamental problem cause]
- **Symptoms**: [Specific symptoms the customer is experiencing]
- **Impact Level**: [Impact level on business/customer]

## ⚡ **Immediate Action Items**
1. [Priority 1 - Most urgent action]
2. [Priority 2 - Follow-up action]
3. [Priority 3 - Preventive measures]

## 📊 **Situation Indicators**
- **Severity**: [Critical/High/Medium/Low]
- **Complexity**: [Simple/Medium/Complex]
- **Customer Sentiment**: [Satisfied/Neutral/Frustrated/Angry]
- **Expected Resolution Time**: [Immediate/Within 1 day/Within 1 week/Long-term]

## 💡 **Agent Notes**
[Important background knowledge or considerations for agents during response]

**Writing Guidelines:**
- Structure so agents can understand the entire situation within 15 seconds
- Use emojis and bold text to enhance visual distinction
- Provide structured information based on analytical thinking
- Present priorities considering both customer emotions and business impact"""

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

    return "Please provide a concise summary of the following content."


def _build_summary_prompt(
    content: str,
    content_type: str,
    subject: str = "",
    metadata: Dict[str, Any] = None,
    language: str = "ko"
) -> str:
    """요약 프롬프트 구성"""
    
    prompt_parts = []
    
    # 제목 정보
    if subject:
        if language == "ko":
            prompt_parts.append(f"제목: {subject}")
        else:
            prompt_parts.append(f"Subject: {subject}")
    
    # 메타데이터 정보
    if metadata:
        if language == "ko":
            meta_info = []
            if metadata.get('status'):
                meta_info.append(f"상태: {metadata['status']}")
            if metadata.get('priority'):
                meta_info.append(f"우선순위: {metadata['priority']}")
            if metadata.get('category_id'):
                meta_info.append(f"카테고리: {metadata['category_id']}")
            if meta_info:
                prompt_parts.append(f"메타정보: {', '.join(meta_info)}")
        else:
            meta_info = []
            if metadata.get('status'):
                meta_info.append(f"Status: {metadata['status']}")
            if metadata.get('priority'):
                meta_info.append(f"Priority: {metadata['priority']}")
            if metadata.get('category_id'):
                meta_info.append(f"Category: {metadata['category_id']}")
            if meta_info:
                prompt_parts.append(f"Metadata: {', '.join(meta_info)}")
    
    # 콘텐츠
    if language == "ko":
        prompt_parts.append(f"내용:\n{content}")
        prompt_parts.append("\n위 내용을 상담원용으로 요약해주세요:")
    else:
        prompt_parts.append(f"Content:\n{content}")
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
