# 🛠️ 개발 환경 가이드 (2025-06-28 업데이트)

## ⭐ 최신 아키텍처 변경사항

### 🚀 순차 실행 패턴 적용
**변경 배경**: 기존 병렬 처리(InitParallelChain) 구조가 복잡하고 불필요함을 확인
**적용 결과**: 순차 실행으로 단순화하여 3~4초 내외 성능 달성

```python
# 새로운 순차 실행 패턴
async def execute_init_sequential(ticket_id, tenant_id):
    # 1단계: 실시간 요약 생성 (Freshdesk API)
    summary = await generate_realtime_summary(ticket_id)
    
    # 2단계: 벡터 검색 (Qdrant)
    similar_tickets = await search_similar_tickets(summary)
    kb_results = await search_knowledge_base(summary)
    
    return {
        "summary": summary,
        "similar_tickets": similar_tickets,
        "kb_documents": kb_results
    }
```

### 🔍 벡터 검색 개선
- **doc_type 코드 레벨 필터링 완전 제거**
- **Qdrant 쿼리 레벨 필터링만 사용**
- **실시간 요약과 벡터 검색 명확히 분리**

### 🧪 테스트 완료
실제 데이터로 end-to-end 테스트 완료:
```bash
cd backend
python test_e2e_real_data.py
# 결과: 모든 테스트 통과 (5/5)
```

---

## 자동 재수집 문제 해결

### 문제 설명
개발 중 데이터 수집이 완료된 후 자동으로 다시 시작되는 현상이 발생할 수 있습니다.

### 주요 원인
1. **FastAPI `--reload` 모드**: 파일 변경 감지 시 서버 자동 재시작
2. **체크포인트 자동 복구**: 중단된 작업의 자동 재개
3. **백그라운드 작업 중복**: Job Manager의 동시 실행

### 해결 방법

#### 1. 프로덕션 모드로 백엔드 실행
```bash
# --reload 없이 실행 (권장)
cd backend && source venv/bin/activate && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# 또는 gunicorn 사용
cd backend && source venv/bin/activate && gunicorn -w 1 -k uvicorn.workers.UvicornWorker api.main:app --bind 0.0.0.0:8000
```

#### 2. VS Code 태스크 수정
현재 태스크를 다음과 같이 수정하세요:

```json
{
    "label": "🚀 Start Backend Production",
    "type": "shell",
    "command": "cd backend && source venv/bin/activate && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000",
    "group": "build",
    "isBackground": true
}
```

#### 3. 자동 재수집 방지 기능 활용
시스템에 다음 보호 기능이 추가되었습니다:

- **5분간 재수집 방지**: 같은 회사의 작업이 5분 이내에 완료된 경우 자동 재수집 차단
- **강제 재구축 예외**: `force_rebuild=true` 옵션 사용 시 재수집 방지 무시
- **체크포인트 복구 개선**: 전체 재수집 모드에서는 체크포인트 자동 무시

### 개발 모드 사용 시 주의사항

개발 중 `--reload` 모드를 사용해야 하는 경우:

1. **데이터 수집 완료 후 파일 수정 금지**
2. **체크포인트 수동 정리**:
   ```bash
   rm -rf backend/freshdesk_*_data/checkpoints/
   ```
3. **Job Manager 상태 확인**:
   ```bash
   curl -H "X-Company-ID: your-company" http://localhost:8000/ingest/jobs
   ```

### 모니터링 로그
자동 재수집 방지 로그를 확인하세요:

```
⚠️  자동 재수집 방지: 회사 your-company의 최근 완료된 작업이 있습니다.
최근 완료된 작업: ['job-id-123']
5분 후에 다시 시도하거나 force_rebuild=True를 사용하세요.
```

### 긴급 해결책

자동 재수집이 계속 발생하는 경우:

1. **백엔드 서버 중지**
2. **체크포인트 정리**: `rm -rf backend/freshdesk_*_data/checkpoints/`
3. **프로덕션 모드로 재시작**
4. **Job Manager 초기화**: 서버 재시작으로 메모리 상태 초기화

## 권장 개발 워크플로우

1. **데이터 수집 전**: 프로덕션 모드로 백엔드 실행
2. **수집 완료 후**: 필요시 개발 모드로 전환
3. **코드 수정 중**: 데이터 수집 작업 중지
4. **테스트**: 항상 `max_tickets=10` 등 제한된 수집으로 테스트

이 가이드를 따라하면 자동 재수집 문제를 근본적으로 해결할 수 있습니다.
