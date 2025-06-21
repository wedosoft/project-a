# LLM 구조 통합 계획서

## 🎯 목표
기존의 `core/llm`과 `core/langchain` 디렉터리를 통합하여 중복을 제거하고 명확한 책임 분리를 구현합니다.

## 🚨 현재 문제점

### 1. 기능 중복
- **프로바이더 중복**: 
  - `core/llm/clients.py`: AnthropicProvider, OpenAIProvider, GeminiProvider
  - `core/langchain/providers/`: 동일한 프로바이더들
- **모델 중복**: 
  - `core/llm/models.py`와 `core/langchain/models/`에 유사한 정의들

### 2. 불명확한 경계
- `core/llm`: "순수한" LLM 클라이언트인지 불분명
- `core/langchain`: Langchain 래퍼인지, 별도 구현인지 불분명
- 개발자가 어느 것을 사용해야 할지 혼란

### 3. 유지보수 복잡성
- 동일한 기능을 두 곳에서 수정해야 함
- 버그 수정 시 동기화 문제
- 새로운 프로바이더 추가 시 중복 작업

## 🏗️ 제안하는 통합 구조

```
core/llm_unified/
├── __init__.py
├── manager.py                   # 메인 LLM 매니저
├── models/                      # 모든 데이터 모델
│   ├── __init__.py
│   ├── base.py                 # 기본 모델들 (LLMResponse, LLMRequest 등)
│   ├── providers.py            # 프로바이더 관련 모델들
│   └── responses.py            # 응답 관련 모델들
├── providers/                   # LLM 프로바이더 구현체들
│   ├── __init__.py
│   ├── base.py                 # 기본 프로바이더 인터페이스
│   ├── anthropic.py            # Anthropic 구현
│   ├── openai.py               # OpenAI 구현
│   └── gemini.py               # Google Gemini 구현
├── integrations/                # 외부 통합
│   ├── __init__.py
│   ├── langchain/              # Langchain 전용 통합
│   │   ├── __init__.py
│   │   ├── chains/             # 기존 langchain/chains
│   │   ├── callbacks/          # 기존 langchain/callbacks
│   │   ├── embeddings.py       # 기존 langchain/embeddings
│   │   └── vector_store.py     # 기존 langchain/vector_store
│   └── custom/                 # 커스텀 통합들
├── utils/                       # 유틸리티 함수들
│   ├── __init__.py
│   ├── config.py               # 설정 관리
│   ├── patterns.py             # 키워드 패턴
│   ├── routing.py              # 라우팅 로직
│   ├── metrics.py              # 메트릭스
│   └── cache.py                # 캐싱
└── filters/                     # 필터링 로직
    ├── __init__.py
    └── conversation.py          # 대화 필터링
```

## 📋 마이그레이션 단계

### Phase 1: 기본 구조 생성 ✅
- [x] 통합된 디렉터리 구조 생성
- [x] 기본 모델들 정의 (base.py, providers.py)
- [x] 기본 프로바이더 인터페이스 정의

### Phase 2: 프로바이더 통합 (다음 단계)
- [ ] 기존 프로바이더들을 새로운 인터페이스로 마이그레이션
- [ ] AnthropicProvider, OpenAIProvider, GeminiProvider 통합
- [ ] 기존 기능 100% 보존 확인

### Phase 3: 유틸리티 통합
- [ ] 설정 관리 통합 (config.py)
- [ ] 키워드 패턴 통합 (patterns.py) 
- [ ] 메트릭스 시스템 통합 (metrics.py)
- [ ] 라우팅 로직 통합 (routing.py)

### Phase 4: Langchain 통합
- [ ] 기존 langchain 코드를 integrations/langchain으로 이동
- [ ] chains, callbacks, embeddings 보존
- [ ] vector_store 통합

### Phase 5: 메인 매니저 통합
- [ ] 기존 llm_manager.py를 manager.py로 통합
- [ ] 모든 기능 보존 및 테스트
- [ ] 성능 최적화

### Phase 6: 레거시 정리
- [ ] 기존 core/llm, core/langchain 백업
- [ ] 의존성 업데이트
- [ ] 문서 업데이트

## 🎯 기대 효과

### 1. 코드 품질 개선
- **중복 제거**: 동일한 프로바이더를 한 번만 구현
- **명확한 책임**: 각 모듈의 역할이 명확히 정의됨
- **일관성**: 통일된 인터페이스와 패턴

### 2. 유지보수성 향상
- **단일 진실의 원천**: 각 기능이 한 곳에서만 구현됨
- **쉬운 확장**: 새 프로바이더 추가가 단순해짐
- **버그 수정**: 한 곳에서만 수정하면 됨

### 3. 개발자 경험 개선
- **명확한 API**: 어떤 클래스를 사용할지 명확함
- **좋은 문서**: 통합된 구조로 문서화 개선
- **예측 가능성**: 일관된 패턴으로 학습 곡선 감소

## ⚠️ 주의사항

1. **기존 기능 보존**: 모든 기존 기능이 100% 작동해야 함
2. **점진적 마이그레이션**: 한 번에 모든 것을 바꾸지 않고 단계적으로 진행
3. **테스트 강화**: 각 단계마다 철저한 테스트
4. **백워드 호환성**: 기존 코드가 일정 기간 동안 작동해야 함

## 🚀 다음 단계

1. 이 계획에 대한 승인/피드백 받기
2. Phase 2 시작: 프로바이더 통합 작업
3. 테스트 케이스 작성 및 검증

---

**질문이나 피드백이 있으시면 언제든 말씀해 주세요!**
