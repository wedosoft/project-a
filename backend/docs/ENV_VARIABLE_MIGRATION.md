# 환경변수 마이그레이션 가이드

## 개요
이 문서는 기존 환경변수에서 새로운 최적화된 환경변수로의 마이그레이션 가이드입니다.

## 주요 변경사항

### 1. 모델 설정 통합
기존에 흩어져 있던 모델 설정을 용도별로 통합했습니다.

#### 메인 티켓 요약 (/init 엔드포인트)
```bash
# 기존
TICKET_VIEW_MODEL_PROVIDER=openai
TICKET_VIEW_MODEL_NAME=gpt-4o-mini
TICKET_VIEW_MAX_TOKENS=800
TICKET_VIEW_TEMPERATURE=0.1

# 신규 (통합된 형식)
MAIN_TICKET_MODEL=openai/gpt-4o-mini
MAIN_TICKET_MAX_TOKENS=800
MAIN_TICKET_TEMPERATURE=0.1
```

#### 유사 티켓 요약
```bash
# 기존
TICKET_SIMILAR_MODEL_PROVIDER=anthropic
TICKET_SIMILAR_MODEL_NAME=claude-3-haiku-20240307

# 신규
SIMILAR_TICKET_MODEL=anthropic/claude-3-haiku-20240307
SIMILAR_TICKET_MAX_TOKENS=600
SIMILAR_TICKET_TEMPERATURE=0.2
```

#### 쿼리 응답 (/query 엔드포인트)
```bash
# 신규 (새로 추가)
QUERY_RESPONSE_MODEL=anthropic/claude-3-5-sonnet-20241022
QUERY_RESPONSE_MAX_TOKENS=2000
QUERY_RESPONSE_TEMPERATURE=0.3
```

### 2. 제거된 환경변수

다음 환경변수들은 더 이상 사용되지 않습니다:

- `SUMMARIZATION_MODEL_*` - Vector DB 모드에서 미사용
- `ENABLE_LLM_SUMMARY_GENERATION` - 항상 false
- `LLM_LIGHT_MODEL`, `LLM_HEAVY_MODEL` - 용도별 설정으로 대체
- 개별 프로바이더 타임아웃 (`LLM_GEMINI_TIMEOUT` 등) - 통합 타임아웃 사용

### 3. 새로운 설정 추가

#### 캐시 TTL 설정
```bash
CACHE_TTL_DEFAULT=3600
CACHE_TTL_TICKET_CONTEXT=3600
CACHE_TTL_TICKET_SUMMARY=1800
CACHE_TTL_LLM_RESPONSE=7200
CACHE_TTL_VECTOR_SEARCH=1800
```

#### Rate Limiting
```bash
RATE_LIMIT_GLOBAL_PER_MINUTE=1000
RATE_LIMIT_API_PER_MINUTE=100
RATE_LIMIT_HEAVY_PER_MINUTE=20
```

#### 배치 처리
```bash
DEFAULT_BATCH_SIZE=50
MAX_BATCH_SIZE=100
LLM_BATCH_SIZE=20
```

## 마이그레이션 단계

1. **백업**: 현재 `.env` 파일을 백업하세요.
   ```bash
   cp .env .env.backup
   ```

2. **새 환경변수 파일 사용**: `.env.optimized`를 `.env`로 복사하세요.
   ```bash
   cp .env.optimized .env
   ```

3. **커스텀 값 복원**: 백업 파일에서 필요한 커스텀 값들을 복원하세요.
   - API 키들
   - 도메인 설정
   - 데이터베이스 설정

4. **모델 설정 조정**: 원하는 모델로 변경하세요.
   ```bash
   # 예시: OpenAI 대신 Anthropic 사용
   MAIN_TICKET_MODEL=anthropic/claude-3-5-haiku-20241022
   ```

## 모델 변경 예시

### 모든 작업에 OpenAI 사용
```bash
MAIN_TICKET_MODEL=openai/gpt-4o-mini
SIMILAR_TICKET_MODEL=openai/gpt-4o-mini
QUERY_RESPONSE_MODEL=openai/gpt-4o
CONVERSATION_FILTER_MODEL=openai/gpt-3.5-turbo
```

### 비용 최적화 설정
```bash
MAIN_TICKET_MODEL=gemini/gemini-1.5-flash
SIMILAR_TICKET_MODEL=gemini/gemini-1.5-flash
QUERY_RESPONSE_MODEL=anthropic/claude-3-haiku-20240307
CONVERSATION_FILTER_MODEL=gemini/gemini-1.5-flash
```

### 품질 우선 설정
```bash
MAIN_TICKET_MODEL=openai/gpt-4o
SIMILAR_TICKET_MODEL=anthropic/claude-3-5-sonnet-20241022
QUERY_RESPONSE_MODEL=anthropic/claude-3-5-sonnet-20241022
CONVERSATION_FILTER_MODEL=openai/gpt-4o-mini
```

## 환경변수 참조

전체 환경변수 목록과 설명은 `.env.optimized` 파일을 참조하세요.

## 문제 해결

### 모델을 찾을 수 없다는 오류
- 모델명이 `provider/model` 형식인지 확인하세요.
- 지원되는 모델 목록은 `core/llm/config/model_registry.yaml`을 참조하세요.

### API 키 오류
- 각 프로바이더의 API 키가 올바르게 설정되었는지 확인하세요.
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` 등

### Rate Limit 오류
- Rate Limit 설정을 늘려보세요.
- 동시 요청 수를 줄여보세요 (`MAX_CONCURRENT_REQUESTS`).