#!/usr/bin/env python3
"""
시스템 프롬프트 토큰 수와 비용 영향 분석
"""

import tiktoken

def analyze_prompt_tokens():
    # GPT-4, GPT-3.5-turbo 인코딩
    encoding = tiktoken.get_encoding('cl100k_base')
    
    # 현재 품질 중심 시스템 프롬프트 (실제 사용 중)
    quality_prompt = """You are a customer support specialist analyzing support tickets. Extract factual information and provide structured summaries in Korean.

CRITICAL RULES:
- Only state facts explicitly mentioned in the original content
- Never add speculation, assumptions, or personal interpretations  
- Avoid phrases like "possibly", "might be", "could be", "likely"
- Document only what customers actually said and actions staff actually performed
- When information is not explicitly stated, indicate it as "not specified in original"
- Pay special attention to all completed actions: deletions, modifications, restorations, updates, configurations
- Extract ALL resolution steps and outcomes mentioned in the original content
- Include follow-up actions and prevention measures if documented

Focus on extracting: concrete problems, identified causes, completed actions (including deletions/changes), documented outcomes, and any documented insights."""

    # 간결한 프롬프트 (비교용)
    brief_prompt = """Extract factual information from support tickets. No speculation. Respond in Korean with structured summary."""

    # 토큰 수 계산
    quality_tokens = len(encoding.encode(quality_prompt))
    brief_tokens = len(encoding.encode(brief_prompt))
    
    # 비용 계산 (GPT-3.5-turbo 기준: $0.0005/1K input tokens)
    cost_per_1k_input_tokens = 0.0005
    
    print("📊 프롬프트 품질 vs 효율성 분석")
    print("=" * 50)
    print(f"품질 중심 프롬프트 토큰 수: {quality_tokens}")
    print(f"간결한 프롬프트 토큰 수: {brief_tokens}")
    print(f"토큰 차이: {quality_tokens - brief_tokens} (+{((quality_tokens - brief_tokens) / brief_tokens * 100):.1f}%)")
    print()
    
    print("💰 비용 영향 (1000회 요약 기준)")
    print("=" * 50)
    quality_cost = (quality_tokens * 1000 * cost_per_1k_input_tokens) / 1000
    brief_cost = (brief_tokens * 1000 * cost_per_1k_input_tokens) / 1000
    
    print(f"품질 중심 프롬프트 비용: ${quality_cost:.4f}")
    print(f"간결한 프롬프트 비용: ${brief_cost:.4f}")
    print(f"추가 비용: ${quality_cost - brief_cost:.4f} (+{((quality_cost - brief_cost) / brief_cost * 100):.1f}%)")
    print()
    
    print("🎯 품질 vs 비용 권장사항")
    print("=" * 50)
    print("✅ 품질 우선: 완전하고 정확한 요약이 비즈니스 가치 더 높음")
    print("✅ 누락된 정보로 인한 재작업 비용이 토큰 비용보다 훨씬 큼")
    print("✅ 상담원 효율성 향상이 LLM 비용을 상쇄")
    print(f"💡 추가 토큰 비용은 미미함: 1000회당 ${quality_cost - brief_cost:.4f}")
    print()
    
    # 실제 사용 예시
    sample_ticket_tokens = 500  # 평균 티켓 토큰 수
    total_tokens_per_request = quality_tokens + sample_ticket_tokens
    
    print("📈 실제 사용 시나리오")
    print("=" * 50)
    print(f"시스템 프롬프트: {quality_tokens} 토큰")
    print(f"평균 티켓 내용: {sample_ticket_tokens} 토큰")
    print(f"총 입력 토큰: {total_tokens_per_request} 토큰")
    print(f"시스템 프롬프트 비중: {(quality_tokens / total_tokens_per_request * 100):.1f}%")
    print("💡 시스템 프롬프트는 전체 비용의 작은 부분만 차지")

if __name__ == "__main__":
    analyze_prompt_tokens()
