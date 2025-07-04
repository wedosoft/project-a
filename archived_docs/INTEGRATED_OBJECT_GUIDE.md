# 통합 객체 저장 및 활용 가이드

## 개요

이 문서는 FastAPI 기반 RAG 시스템에서 Freshdesk 티켓/KB 데이터를 "통합 객체"로 저장하고 활용하는 패턴을 설명합니다. 통합 객체는 티켓+대화+첨부파일 또는 문서+첨부파일을 하나의 완전한 JSON 구조로 결합하여 저장함으로써, 요약/임베딩/검색 등 downstream 작업의 효율성을 극대화합니다.

## 통합 객체 구조

### 1. 통합 티켓 객체 (Integrated Ticket Object)

```json
{
  "id": 12345,
  "subject": "로그인 문제 해결 요청",
  "description": "사용자가 로그인할 수 없습니다...",
  "description_text": "사용자가 로그인할 수 없습니다...",
  "status": "open",
  "priority": 2,
  "requester_id": 67890,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-16T14:20:00Z",
  
  // 통합된 대화내역
  "conversations": [
    {
      "id": 98765,
      "body": "안녕하세요, 로그인 문제에 대해 도움을 드리겠습니다...",
      "body_text": "안녕하세요, 로그인 문제에 대해 도움을 드리겠습니다...",
      "incoming": false,
      "private": false,
      "user_id": 11111,
      "created_at": "2024-01-15T11:00:00Z",
      "attachments": [...]
    }
  ],
  
  // 통합된 첨부파일 (티켓 + 모든 대화의 첨부파일)
  "all_attachments": [
    {
      "id": 54321,
      "name": "screenshot.png",
      "content_type": "image/png",
      "size": 12345,
      "attachment_url": "https://...",
      "ticket_id": 12345,
      "conversation_id": null  // 티켓 직접 첨부
    },
    {
      "id": 54322,
      "name": "log_file.txt",
      "content_type": "text/plain",
      "size": 6789,
      "attachment_url": "https://...",
      "ticket_id": 12345,
      "conversation_id": 98765  // 대화에서 첨부
    }
  ],
  
  // 메타 정보
  "has_conversations": true,
  "has_attachments": true,
  "conversation_count": 3,
  "attachment_count": 2,
  "integration_timestamp": "2024-01-16T15:30:00Z",
  "object_type": "integrated_ticket",
  
  // 요약/임베딩용 통합 텍스트
  "integrated_text": "제목: 로그인 문제 해결 요청\n\n설명: 사용자가 로그인할 수 없습니다...\n\n대화: 안녕하세요, 로그인 문제에 대해 도움을 드리겠습니다...\n\n첨부파일: screenshot.png, log_file.txt"
}
```

### 2. 통합 문서 객체 (Integrated Article Object)

```json
{
  "id": 67890,
  "title": "로그인 문제 해결 방법",
  "description": "로그인 관련 문제를 해결하는 방법을 설명합니다...",
  "status": "published",
  "folder_id": 123,
  "category_id": 456,
  "created_at": "2024-01-10T09:00:00Z",
  "updated_at": "2024-01-15T16:00:00Z",
  
  // 통합된 첨부파일
  "attachments": [
    {
      "id": 78901,
      "name": "login_guide.pdf",
      "content_type": "application/pdf",
      "size": 98765,
      "attachment_url": "https://...",
      "article_id": 67890,
      "folder_id": 123,
      "category_id": 456
    }
  ],
  
  // 메타 정보
  "has_attachments": true,
  "attachment_count": 1,
  "integration_timestamp": "2024-01-16T15:30:00Z",
  "object_type": "integrated_article",
  
  // 요약/임베딩용 통합 텍스트
  "integrated_text": "제목: 로그인 문제 해결 방법\n\n설명: 로그인 관련 문제를 해결하는 방법을 설명합니다...\n\n첨부파일: login_guide.pdf"
}
```

## 구현 패턴

### 1. 통합 객체 생성

```python
# 티켓 통합 객체 생성
integrated_ticket = create_integrated_ticket_object(
    ticket=ticket_data,
    conversations=conversation_list,
    attachments=attachment_list
)

# 문서 통합 객체 생성
integrated_article = create_integrated_article_object(
    article=article_data,
    attachments=attachment_list
)
```

### 2. SQLite 저장

```python
# 통합 객체를 SQLite에 저장 (raw_data 필드에 완전한 JSON)
success = store_integrated_object_to_sqlite(
    db=db,
    integrated_object=integrated_ticket,
    company_id=company_id,
    platform='freshdesk'
)
```

### 3. 통합 객체 조회

```python
# 특정 통합 객체 조회
integrated_object = get_integrated_object_from_sqlite(
    db=db,
    doc_type="ticket",  # "ticket" 또는 "kb"
    object_id="12345",
    company_id=company_id
)

# 통합 객체 검색
results = search_integrated_objects_from_sqlite(
    db=db,
    query="로그인 문제",
    company_id=company_id,
    doc_type=None,  # 모든 타입 검색
    limit=10
)
```

## Downstream 활용

### 1. 요약 생성

```python
# 요약에 적합한 텍스트 추출 (길이 제한 포함)
summary_text = extract_integrated_text_for_summary(
    integrated_object=integrated_ticket,
    max_length=5000
)

# AI 모델로 요약 생성
summary = ai_model.summarize(summary_text)
```

### 2. 임베딩 생성

```python
# 임베딩에 적합한 텍스트 추출
embedding_text = extract_integrated_text_for_embedding(
    integrated_object=integrated_ticket
)

# 벡터 임베딩 생성
embedding = embedding_model.encode(embedding_text)
```

### 3. Qdrant 저장 (통합 텍스트 활용)

```python
# Qdrant에 저장할 문서 구조 생성
doc = {
    "id": f"ticket-{ticket_id}",
    "text": integrated_ticket.get("integrated_text", ""),  # 통합 텍스트 사용
    "metadata": {
        **integrated_ticket,
        "original_id": ticket_id,
        "doc_type": "ticket",
        "company_id": company_id
    }
}
```

## 장점

### 1. 완전성 (Completeness)
- 티켓+대화+첨부파일이 하나의 완전한 컨텍스트로 저장
- 데이터 손실 없이 전체 상황 파악 가능
- 분산된 정보의 일관성 보장

### 2. 효율성 (Efficiency)
- 단일 쿼리로 모든 관련 정보 조회
- 복잡한 JOIN 연산 불필요
- 캐싱 및 성능 최적화 용이

### 3. 활용성 (Usability)
- 요약/임베딩 작업에 최적화된 텍스트 제공
- 검색 정확도 향상 (컨텍스트 풍부)
- 다양한 AI 모델 입력에 적합

### 4. 유지보수성 (Maintainability)
- 단일 구조로 데이터 관리 단순화
- 스키마 변경에 유연하게 대응
- 디버깅 및 모니터링 용이

## 설정 및 사용법

### 1. 환경변수 설정

```bash
# .env 파일
FRESHDESK_DOMAIN=your-company.freshdesk.com
FRESHDESK_API_KEY=your_api_key
```

### 2. 데이터 수집 및 통합 객체 저장

```bash
# 백엔드 실행
cd backend
source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 수집 API 호출
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: your-company" \
  -d '{"incremental": true, "include_kb": true}'
```

### 3. 통합 객체 조회

```bash
# 특정 티켓 조회
curl "http://localhost:8000/tickets/12345" \
  -H "X-Company-ID: your-company"

# 검색
curl "http://localhost:8000/search?q=로그인+문제&limit=10" \
  -H "X-Company-ID: your-company"
```

## 모니터링 및 로깅

### 1. 수집 현황 모니터링

```bash
# 수집 작업 상태 확인
curl "http://localhost:8000/ingest/jobs" \
  -H "X-Company-ID: your-company"

# 수집 통계 확인
curl "http://localhost:8000/ingest/stats" \
  -H "X-Company-ID: your-company"
```

### 2. 로그 확인

```bash
# 수집 로그 확인
curl "http://localhost:8000/ingest/logs?limit=100" \
  -H "X-Company-ID: your-company"
```

## 확장 가능성

### 1. 다른 플랫폼 지원
- `platform` 필드로 구분하여 멀티 플랫폼 데이터 관리

### 2. 고급 기능
- 통합 객체 기반 자동 태깅
- 유사도 기반 문서 그룹핑
- 시계열 분석을 위한 버전 관리

### 3. 성능 최적화
- 통합 객체 압축 저장
- 부분 업데이트 메커니즘
- 병렬 처리 확장

## 주의사항

1. **저장 공간**: 통합 객체는 중복 데이터를 포함할 수 있어 저장 공간이 증가할 수 있습니다.
2. **동기화**: 원본 데이터 변경 시 통합 객체 업데이트 필요합니다.
3. **버전 관리**: 스키마 변경 시 기존 통합 객체와의 호환성을 고려해야 합니다.

## 결론

통합 객체 패턴은 RAG 시스템에서 Freshdesk 데이터의 완전성과 활용성을 극대화하는 핵심 아키텍처입니다. 이를 통해 더 정확한 검색, 효과적인 요약, 그리고 강력한 AI 기반 분석이 가능해집니다.
