# 티켓 분석 성능 최적화 - 구현 가이드

## Quick Start

이 최적화는 **프론트엔드만** 수정하여 티켓 분석 응답 시간을 대폭 단축합니다.

### 주요 변경사항
```javascript
// 1. Conversations 데이터 재사용
const payload = {
  // ... 기타 필드
  conversations: minimalTicket.conversations || []
};

// 2. 폴링 지수 백오프
const getDelay = (attempt) => {
  if (attempt === 0) return 500;   // 0.5초
  if (attempt < 3) return 800;     // 0.8초
  if (attempt < 6) return 1200;    // 1.2초
  return 2000;                     // 2초
};

// 3. 페이로드 경량화
const truncatedBody = bodyText.length > 2000 
  ? bodyText.substring(0, 2000) + '...[truncated]'
  : bodyText;
```

## 성능 개선 예상치

### Before & After
| 측정 항목 | 개선 전 | 개선 후 | 개선 |
|----------|---------|---------|------|
| SSE 모드 | 5-10초 | 2-3초 | **60-70%** |
| 폴링 모드 | 40-60초 | 8-15초 | **62-75%** |
| 전체 평균 | ~60초 | 3-15초 | **75-95%** |

### 개선 메커니즘
1. **Conversations 재조회 방지**: 2-4초 절약
2. **폴링 초기 대기 단축**: 5-10초 절약
3. **페이로드 크기 감소**: 0.5-1초 절약
4. **타임아웃 최적화**: 빠른 fallback

## 테스트 방법

### 1. 로컬 환경 테스트
```bash
cd frontend
fdk run
```

브라우저 콘솔에서 다음 로그 확인:
- `[Analyze] Sending payload: N conversations, XKB`
- `[StreamUtils] Analysis completed in Xms`
- `[PollAnalyze] Completed after N attempts`

### 2. 성능 측정
브라우저 DevTools → Network 탭에서:
- `/api/assist/analyze` 요청 시간 확인
- SSE 스트림 모드 vs 폴링 모드 비교

### 3. 시나리오별 테스트
- **짧은 티켓** (conversations < 10): 2-3초 예상
- **긴 티켓** (conversations > 50): 3-5초 예상
- **재분석**: 캐시 효과 확인 (백엔드 지원 필요)

## 설정 커스터마이징

### 폴링 지연 시간 조정
```javascript
// frontend/app/scripts/stream-utils.js
const CONFIG = {
  POLLING: {
    INITIAL_DELAY_MS: 500,   // 더 빠르게: 300
    EARLY_DELAY_MS: 800,     // 더 빠르게: 500
    // ...
  }
};
```

### Conversation 텍스트 제한 조정
```javascript
// frontend/app/scripts/app.js
const PERFORMANCE_CONFIG = {
  MAX_CONVERSATION_CHARS: 2000  // 더 길게: 3000, 더 짧게: 1500
};
```

### 타임아웃 조정
```javascript
// frontend/app/scripts/stream-utils.js
const CONFIG = {
  SSE_TIMEOUT_MS: 30000  // 더 길게: 60000, 더 짧게: 20000
};
```

## 백엔드 요구사항

### 필수 지원
백엔드는 다음 필드를 payload로 받아야 합니다:
```json
{
  "ticket_id": "12345",
  "subject": "...",
  "description": "...",
  "ticket_fields": [...],
  "conversations": [
    {
      "body_text": "...",
      "incoming": true,
      "private": false,
      "created_at": "...",
      "user_id": 123
    }
  ]
}
```

### 권장 사항
1. **Conversations 우선 사용**: payload에 있으면 Freshdesk API 호출 생략
2. **캐싱**: 동일 티켓 재분석 시 30-60초 TTL 캐시 사용
3. **Summary Sections**: 2-3개 섹션 구조로 반환

## 모니터링

### 프론트엔드 로그
```javascript
// 페이로드 크기
[Analyze] Sending payload: 45 conversations, 23KB

// 완료 시간
[StreamUtils] Analysis completed in 3500ms

// 폴링 시도
[PollAnalyze] Completed after 3 attempts
```

### 성능 메트릭
- **P50 응답 시간**: < 5초 목표
- **P95 응답 시간**: < 15초 목표
- **타임아웃 비율**: < 5% 목표

## 트러블슈팅

### "Conversations 데이터가 전달되지 않음"
```javascript
// loadTicketData()에서 확인
console.log('Ticket conversations:', ticketData.conversations?.length);
```

### "폴링 모드로 계속 진입함"
- SSE 엔드포인트 응답 Content-Type 확인
- 백엔드가 `text/event-stream` 헤더 반환하는지 확인

### "타임아웃 발생"
- 백엔드 처리 시간이 30초 초과하는 경우
- CONFIG.SSE_TIMEOUT_MS 값 증가 고려

## 추가 최적화 아이디어

### 단기 (1-2주)
- [ ] 분석 결과 프론트엔드 캐싱 (재분석 시 즉시 표시)
- [ ] 프리로딩 (티켓 열람 시 백그라운드 분석)
- [ ] 진행률 바 추가 (0% → 100%)

### 중기 (1개월)
- [ ] WebSocket 연결로 SSE 대체
- [ ] 분석 우선순위 큐 (긴급 티켓 우선)
- [ ] 점진적 렌더링 (요약 → 필드 제안 순차 표시)

### 장기 (3개월)
- [ ] Edge caching (CDN)
- [ ] Service Worker (오프라인 지원)
- [ ] 예측 프리페칭 (다음 티켓 분석 미리 시작)

## 관련 문서
- `PERFORMANCE_OPTIMIZATION.md` - 상세 최적화 내역
- `specs/003-ticket-analysis-speed/` - 기획 문서
- `frontend/app/scripts/app.js` - 주요 변경 코드
- `frontend/app/scripts/stream-utils.js` - SSE 및 폴링 로직
