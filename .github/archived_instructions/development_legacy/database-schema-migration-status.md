# Database Schema Migration and Optimization Instructions

## 현재 상황 (2025-06-23)

### 완료된 작업
1. **기존 데이터베이스 분석 완료**
   - 원본: `/backend/core/data/wedosoft_freshdesk_data.db`
   - 비효율적인 구조와 중복 데이터 확인

2. **새로운 스키마 설계 및 구현**
   - 단순화된 스키마: `/backend/core/data/wedosoft_freshdesk_data_simplified.db`
   - 스키마 생성 스크립트: `/backend/create_simplified_schema.py`
   - 데이터 마이그레이션 스크립트: `/backend/collect_simplified_data.py`

3. **성공적인 데이터 마이그레이션 완료**
   - 티켓: 4,611건
   - 대화: 18,160건  
   - 요약: 305건
   - 첨부파일: 마이그레이션 시도 (이슈 있음)

### 현재 작업 중단 지점
- **첨부파일 스키마 최적화 논의 중**
- 기존 방식: `ticket_id`, `conversation_id` 별도 컬럼
- 제안된 방식: `parent_type` + `parent_id` 통합 방식
- **사용자 확인**: 테스트 데이터이므로 전체 재시작 가능

## 권장 다음 단계

### 1. 스키마 최종 결정
```sql
-- 현재 simplified 스키마의 attachments 테이블
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    conversation_id INTEGER,
    freshdesk_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER,
    attachment_url TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets (id),
    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
);

-- 제안된 개선 방식
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_type TEXT NOT NULL, -- 'ticket', 'conversation', 'knowledge_base'
    parent_id INTEGER NOT NULL,
    original_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER,
    attachment_url TEXT,
    created_at TEXT,
    updated_at TEXT,
    CHECK (parent_type IN ('ticket', 'conversation', 'knowledge_base'))
);
```

### 2. 백엔드 코드 업데이트 필요 파일들
- `/backend/core/data/database.py` - 데이터베이스 연결 및 쿼리
- `/backend/api/main.py` - API 엔드포인트
- `/backend/api/summarization.py` - 요약 관련 API
- `/backend/core/llm/batch_summarizer.py` - 배치 요약 처리
- `/backend/core/data/data_processor.py` - 데이터 처리 로직

### 3. 데이터 수집 전략
- 새로운 스키마 확정 후
- 기존 마이그레이션 스크립트 개선 또는
- 새로운 수집 스크립트 작성

## 주요 원칙

### 기존 코드 활용
- **새 파일 생성 최소화**
- **기존 파일 구조 최대한 유지**
- **점진적 업데이트 방식**
- **ID 체계 변경 금지** (기존 `id`, `original_id` 등 유지)

### 스키마 최적화 목표
1. **첨부파일 처리 유연성** - parent_type/parent_id 방식으로 확장성 확보
2. **성능 최적화** - 인덱스 및 쿼리 효율성
3. **LLM 요약 지원** - 대용량 데이터 처리 최적화
4. **멀티테넌트 지원** - 향후 확장성 고려

## 현재 데이터베이스 현황

### 사용 가능한 데이터베이스
- `wedosoft_freshdesk_data.db` - 원본 데이터
- `wedosoft_freshdesk_data_simplified.db` - 단순화된 스키마 (현재 작업 대상)
- `wedosoft_freshdesk_data_optimized.db` - 최적화된 스키마 (더 복잡한 구조)

### 테스트 데이터 상태
- **현재 데이터는 모두 테스트용**
- **전체 삭제 후 재시작 가능**
- **스키마 변경에 제약 없음**

## 중요 참고사항

### 첨부파일 스키마 이슈
- 현재 `ticket_id`/`conversation_id` 방식 사용 중
- `parent_type`/`parent_id` 방식으로 개선 제안됨
- 향후 knowledge_base 첨부파일 지원 고려

### 성능 고려사항
- 1M+ 레코드 처리 목표
- 배치 요약 처리 최적화
- 인덱스 전략 중요

## 다음 세션 시작 시 확인사항

1. **스키마 방향성 최종 결정**
   - 현재 simplified 스키마 유지 vs 첨부파일 구조 개선
   
2. **백엔드 코드 업데이트 우선순위**
   - 어떤 파일부터 시작할지
   
3. **데이터 수집 전략**
   - 기존 데이터 유지 vs 전체 재수집

## 코드 파일 현황

### 스키마 관련
- `create_simplified_schema.py` - 단순화된 스키마 생성
- `collect_simplified_data.py` - 데이터 마이그레이션 (이슈 있음)
- `create_clean_schema.py` - 새로운 깔끔한 스키마 (미사용)

### 처리 스크립트
- `batch_summarizer.py` - 배치 요약 처리
- `optimized_large_scale_summarization.py` - 대용량 요약 처리
- `optimized_monitor.py` - 모니터링

## 권장 접근 방식

1. **스키마 확정** - simplified vs clean 결정
2. **기존 코드 점진적 업데이트** - 새 파일 생성 지양
3. **테스트 데이터로 검증** - 안정성 확인 후 진행
4. **성능 테스트** - 대용량 데이터 처리 확인
