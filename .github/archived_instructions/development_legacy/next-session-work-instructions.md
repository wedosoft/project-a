# Next Session Work Instructions

## 🎯 즉시 수행할 작업

### 1. 현재 상황 확인
- 데이터베이스: `/backend/core/data/wedosoft_freshdesk_data_simplified.db` 사용
- 기존 ID 체계 유지 (freshdesk_id 없음, 기존 id/original_id 유지)
- 테스트 데이터이므로 전체 재시작 가능

### 2. 스키마 최종 결정 필요
**옵션 A: 현재 simplified 스키마 유지**
```sql
-- attachments 테이블 (현재 방식)
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    conversation_id INTEGER,
    freshdesk_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    -- ... 기타 필드들
);
```

**옵션 B: 첨부파일 구조 개선**
```sql
-- attachments 테이블 (개선된 방식)
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_type TEXT NOT NULL, -- 'ticket', 'conversation', 'knowledge_base'
    parent_id INTEGER NOT NULL,
    original_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    -- ... 기타 필드들
);
```

### 3. 백엔드 코드 업데이트 순서
1. **database.py** - 스키마 반영
2. **data_processor.py** - 데이터 처리 로직
3. **API 엔드포인트들** - 새 스키마 적용
4. **batch_summarizer.py** - 요약 처리 최적화

## 🚫 주의사항

### 절대 하지 말 것
- **ID 체계 변경 금지** - 기존 id, original_id 유지
- **freshdesk_id 추가 금지** - 존재하지 않는 필드
- **새 파일 생성 지양** - 기존 파일 최대한 활용
- **기존 구조 대폭 변경 금지** - 점진적 업데이트만

### 반드시 확인할 것
- 기존 코드의 ID 참조 방식
- 데이터베이스 연결 부분
- API 엔드포인트의 응답 형식

## 📋 작업 체크리스트

### Phase 1: 스키마 적용
- [ ] 현재 simplified 스키마 구조 확인
- [ ] 기존 database.py 파일 분석
- [ ] 새 스키마에 맞춰 쿼리 업데이트
- [ ] 첨부파일 처리 로직 확인

### Phase 2: 코드 업데이트
- [ ] data_processor.py 스키마 반영
- [ ] API 엔드포인트 수정
- [ ] 배치 처리 로직 업데이트
- [ ] 에러 처리 및 로깅 개선

### Phase 3: 테스트 및 검증
- [ ] 기본 CRUD 작동 확인
- [ ] 요약 기능 테스트
- [ ] 성능 테스트
- [ ] 첨부파일 처리 테스트

## 🔧 기술적 고려사항

### 현재 스키마 특징
- 비정규화된 구조 (성능 최적화)
- conversation_count, attachment_count 등 집계 필드
- 단순한 테이블 구조 (companies, agents 테이블 없음)

### 성능 최적화 포인트
- 인덱스 최적화
- 배치 처리 개선
- 메모리 사용량 최적화
- 대용량 데이터 처리 최적화

## 💡 추천 시작 방식

```python
# 1. 현재 스키마 확인
import sqlite3
conn = sqlite3.connect('/backend/core/data/wedosoft_freshdesk_data_simplified.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("현재 테이블:", tables)

# 2. 각 테이블 구조 확인
for table in tables:
    cursor.execute(f"PRAGMA table_info({table[0]});")
    columns = cursor.fetchall()
    print(f"{table[0]} 테이블 구조:", columns)
```

## 🎪 프로젝트 컨텍스트
- **Freshdesk 멀티테넌트 SaaS**
- **LLM 기반 티켓 요약 시스템**
- **대용량 데이터 처리 (1M+ 레코드)**
- **FastAPI 백엔드 + FDK 프론트엔드**

이 지침서를 바탕으로 다음 세션에서 체계적으로 작업을 진행하세요!
