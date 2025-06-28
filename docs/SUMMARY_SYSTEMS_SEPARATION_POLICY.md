# 요약 시스템 분리 관리 정책

## 📋 개요

본 프로젝트는 3가지 독립적인 요약 시스템을 운영하며, 각각 다른 목적과 품질 기준을 갖습니다.

## 🎯 요약 시스템 분류

### 1. 실시간 티켓 요약 (Premium Quality)
- **목적**: 상담원이 티켓을 열 때 즉시 제공되는 최고 품질 요약
- **엔드포인트**: `/init/{ticket_id}`
- **프롬프트**: `core/llm/integrations/langchain/prompts/realtime_*.yaml` (독립적)
- **코드**: `chains/summarization.py` + `RealtimeTicketPromptLoader`
- **품질 레벨**: `premium` (유사티켓 대비 최고 품질)

### 2. 유사티켓 요약 (Standard Quality)
- **목적**: 관련 티켓 검색 시 제공되는 표준 품질 요약
- **프롬프트**: `core/llm/summarizer/prompt/templates/*/ticket.yaml` (기존 유지)
- **코드**: 기존 CoreSummarizer 체계
- **품질 레벨**: `standard`

### 3. 지식베이스 요약 (Technical Focus)
- **목적**: KB 문서의 기술적 절차와 정보 보존
- **프롬프트**: `core/llm/summarizer/prompt/templates/*/knowledge_base.yaml` (기존 유지)
- **코드**: 기존 CoreSummarizer 체계
- **품질 레벨**: `technical`

## 🔄 분리 관리 원칙

### 핵심 원칙
1. **목적별 최적화**: 각 시스템은 고유 목적에 최적화된 프롬프트 사용
2. **품질 차별화**: 실시간 요약은 최고 품질, 유사티켓은 표준, KB는 기술 특화
3. **독립적 개발**: 각 시스템의 프롬프트와 코드는 독립적으로 관리
4. **혼용 금지**: 서로 다른 시스템의 프롬프트 교차 사용 절대 금지

### 프롬프트 분리 구조
```
backend/
├── core/llm/summarizer/prompt/templates/         # 기존 유사티켓/KB 요약용
│   ├── system/
│   │   ├── ticket.yaml          # 유사티켓 요약 전용 (기존 유지)
│   │   └── knowledge_base.yaml  # KB 요약 전용 (기존 유지)
│   └── user/
│       ├── ticket.yaml          # 유사티켓 요약 전용 (기존 유지)  
│       └── knowledge_base.yaml  # KB 요약 전용 (기존 유지)
└── core/llm/integrations/langchain/prompts/     # 실시간 요약 전용 (신규)
    ├── realtime_ticket_system.yaml             # 실시간 요약 시스템 프롬프트
    ├── realtime_ticket_user.yaml               # 실시간 요약 사용자 프롬프트
    └── realtime_prompt_loader.py               # 실시간 요약 전용 로더
```

## 📊 품질 기준 비교

| 요소 | 실시간 요약 | 유사티켓 요약 | 지식베이스 요약 |
|------|-------------|---------------|-----------------|
| **품질 레벨** | Premium | Standard | Technical |
| **응답 속도** | 즉시 (5초 내) | 빠름 | 정확성 우선 |
| **상세도** | 최고 상세 | 중간 | 기술적 완전성 |
| **첨부파일** | 제외 | 포함 | 포함 |
| **에스컬레이션** | 완벽 준비 | 기본 정보 | 기술 지원 |
| **비즈니스 맥락** | 완전 포함 | 요약 포함 | 제한적 |

## 🚨 실시간 요약 프리미엄 요구사항

### 독점 기능
- **REAL-TIME ACCURACY**: 모든 기술적 세부사항을 완벽한 정밀도로 보존
- **SUPERIOR DETAIL**: 유사티켓 요약보다 더 많은 맥락과 구체성 포함
- **IMMEDIATE ACTIONABILITY**: 즉시 상담원 이해를 위한 정보 구조화
- **COMPLETE TRACEABILITY**: 모든 대화 흐름과 결정점 포함
- **ESCALATION READINESS**: 즉시 에스컬레이션을 위한 모든 정보 제공

### 기술적 특화
- OpenAI 모델 강제 사용 (최고 품질 보장)
- 품질 검증 점수 0.7 미만 시 재시도
- 첨부파일 처리 제외 (실시간 속도 최적화)
- 4섹션 구조 (문제/원인/해결/인사이트)

## 🛡️ 분리 보장 메커니즘

### 코드 레벨 분리
```python
# ✅ 올바른 사용 (실시간 요약 - 독립적)
from core.llm.integrations.langchain.prompts.realtime_prompt_loader import RealtimeTicketPromptLoader
realtime_loader = RealtimeTicketPromptLoader()
system_prompt = realtime_loader.build_system_prompt(language="ko")
user_prompt = realtime_loader.build_user_prompt(subject="...", content="...")

# ✅ 올바른 사용 (유사티켓/KB 요약 - 기존 유지)
from core.llm.summarizer.prompt.builder import PromptBuilder
prompt_builder = PromptBuilder()
system_prompt = prompt_builder.build_system_prompt(content_type="ticket")  # 유사티켓
system_prompt = prompt_builder.build_system_prompt(content_type="knowledge_base")  # KB

# ❌ 금지된 혼용
# 실시간 요약에서 기존 PromptBuilder 사용 금지
# 유사티켓/KB 요약에서 RealtimeTicketPromptLoader 사용 금지
```

### 템플릿 검증
- 각 YAML 파일은 `content_type` 필드로 용도 명시
- `quality_level` 필드로 품질 기준 명시
- 버전 관리를 통한 변경 추적

## 📈 품질 모니터링

### 지속적 검증 체계
1. **품질 점수 모니터링**: 실시간 요약의 품질 점수가 유사티켓보다 높은지 주기적 확인
2. **프롬프트 감사**: 월 1회 각 시스템의 프롬프트가 목적에 맞게 최적화되어 있는지 검토
3. **성능 비교**: 응답 시간, 정확도, 사용자 만족도 지표 비교
4. **분리 준수 검증**: 코드 리뷰 시 혼용 사례 체크

### 경고 신호
- 실시간 요약 품질 점수가 0.7 미만으로 지속적 측정
- 유사티켓과 실시간 요약의 품질 차이가 줄어드는 경우
- 프롬프트 간 내용 중복이 증가하는 경우
- 응답 시간이 목표치를 초과하는 경우

## 🔧 유지보수 가이드

### 실시간 요약 개선 시
1. `core/llm/integrations/langchain/prompts/realtime_*.yaml` 수정
2. `RealtimeTicketPromptLoader` 업데이트 (필요시)
3. 품질 검증 실행 (0.75 이상 목표)
4. 유사티켓 대비 성능 비교
5. A/B 테스트 후 배포

### 유사티켓/KB 요약 개선 시  
1. `core/llm/summarizer/prompt/templates/` 하위 해당 YAML 수정
2. 기존 `PromptBuilder` 체계 사용
3. 실시간 요약과 독립적으로 테스트
4. 품질 검증 후 배포

### 새 요약 시스템 추가 시
1. 독립적인 프롬프트 디렉터리 생성
2. 전용 프롬프트 로더 개발  
3. 독립적 품질 기준 설정
4. 분리 정책 업데이트

## 🎯 향후 개선 계획

### 단기 (1개월)
- [ ] 유사티켓 요약 시스템의 독립적 프롬프트 개발
- [ ] 실시간 요약 품질 자동 모니터링 시스템 구축
- [ ] 프롬프트 버전 관리 체계 강화

### 중기 (3개월)
- [ ] 요약 시스템별 성능 대시보드 구축
- [ ] 자동화된 품질 비교 테스트 도구 개발
- [ ] 사용자 피드백 기반 품질 개선 프로세스

### 장기 (6개월)
- [ ] 머신러닝 기반 품질 예측 모델 도입
- [ ] 실시간 A/B 테스트 프레임워크 구축
- [ ] 다언어 요약 품질 최적화

## 📝 결론

**실시간 요약과 유사티켓/지식베이스 요약의 분리는 절대적으로 필요하며**, 각각의 고유한 목적과 품질 기준을 유지해야 합니다. 이러한 분리를 통해:

1. **실시간 요약**: 최고 품질의 즉시 활용 가능한 분석 제공
2. **유사티켓 요약**: 효율적인 관련 정보 검색 지원  
3. **지식베이스 요약**: 정확한 기술 문서 이해 지원

각 시스템이 독립적으로 최적화되어야만 전체적인 고객 서비스 품질을 극대화할 수 있습니다.
