# 프론트엔드 스트리밍 성능 최적화 가이드

## 개요
이 문서는 Freshdesk Custom App의 프론트엔드 스트리밍 성능을 개선하기 위해 수행한 작업을 정리한 것입니다. 주요 목표는 사용자가 대기 시간을 느끼지 않도록 점진적 렌더링(Progressive Rendering)을 구현하는 것이었습니다.

## 주요 문제점
1. **기존 동작**: 모든 데이터가 100% 로드될 때까지 로딩 바만 표시
2. **사용자 경험**: 긴 대기 시간으로 인한 불편함
3. **모달창 문제**: 메인 페이지와 달리 모달창에서는 스트리밍이 작동하지 않음

## 구현된 솔루션

### 1. API 스트리밍 로직 개선
**파일**: `frontend/app/scripts/api.js`

#### 첫 데이터 도착 감지
```javascript
// 첫 데이터 도착 시 즉시 로딩 오버레이 제거 및 스케일톤 표시
let isFirstDataReceived = false;

await this.processStream(response, (data) => {
  if (!isFirstDataReceived && (
    data.type === 'summary' || 
    data.type === 'similar_tickets' || 
    data.type === 'kb_documents' ||
    data.type === 'ticket_header' ||
    data.type === 'emotion_analysis'
  )) {
    isFirstDataReceived = true;
    window.TicketUI?.hideLoading();
    window.TicketUI?.showSkeletonContent();
  }
  // ... 데이터 처리
});
```

#### 실시간 업데이트 활성화
- 모달뷰에서도 sessionStorage 업데이트 활성화
- 각 섹션별 부분 데이터 전송 구현

### 2. 스케일톤 UI 시스템
**파일**: `frontend/app/scripts/ui.js`

#### 주요 함수
- `showSkeletonContent()`: 모든 섹션에 스케일톤 표시
- `hideSkeletonForSection(section)`: 특정 섹션 스케일톤 제거
- `showSkeletonForHeader()`: 헤더 감정상태만 스케일톤 표시

#### CSS 애니메이션
**파일**: `frontend/app/styles/loading.css`
```css
@keyframes skeleton-pulse {
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
}

.skeleton-line {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  animation: skeleton-pulse 1.5s infinite linear;
}
```

### 3. Core 모듈 상태 관리
**파일**: `frontend/app/scripts/core.js`

#### 추가된 상태
```javascript
state: {
  initialContentShown: false,  // 첫 콘텐츠 표시 상태
  firstDataReceived: false,    // 첫 데이터 수신 상태
  streamingActive: false,      // 스트리밍 진행 상태
  // ...
}
```

### 4. 헤더 점진적 렌더링
**파일**: `frontend/app/scripts/ui.js`

#### 특징
- FDK에서 5개 항목 즉시 표시 (요청자, 우선순위, 담당자, 그룹, 상태)
- 감정상태만 백엔드에서 나중에 도착 → 스케일톤으로 표시
- 감정분석 데이터 도착 시 스케일톤을 실제 데이터로 교체

```javascript
async updateTicketHeader(optimizedData, emotionData = null) {
  // 감정분석 데이터만 업데이트하는 경우 (점진적 렌더링)
  if (emotionData && emotionData.emotion && !optimizedData) {
    const emotionSkeleton = metaRow1.querySelector('.emotion-skeleton');
    if (emotionSkeleton) {
      const emotion = emotionMap[emotionData.emotion] || `❓ ${emotionData.emotion}`;
      emotionSkeleton.outerHTML = `<span class="meta-item">${emotion}</span>`;
    }
    return;
  }
  // ... 전체 헤더 업데이트 로직
}
```

### 5. Modal Bridge 확장
**파일**: `frontend/app/scripts/modal-bridge.js`

#### 새로운 기능
- `sendStreamingStateToModal()`: 스트리밍 상태 전송
- `sendPartialDataToModal()`: 부분 데이터 전송
- `handleStreamingState()`: 스트리밍 상태 수신 처리
- `handlePartialData()`: 부분 데이터 수신 및 렌더링

#### 메시지 타입
- `TICKET_ANALYSIS_DATA`: 완전한 데이터 (기존)
- `STREAMING_STATE_UPDATE`: 스트리밍 상태 (신규)
- `PARTIAL_DATA_UPDATE`: 부분 데이터 (신규)

### 6. 모달창 스트리밍 문제 해결

#### 문제 원인
1. **modal-bridge.js 누락**: index.html에 스크립트가 포함되지 않음
2. **isModalView 조건**: 모달에서 스트리밍 상태 전송이 차단됨
3. **중복 메시지 리스너**: app.js와 modal-bridge.js에서 중복 처리

#### 해결 방법
1. **index.html 수정**
```html
<script src="scripts/modal-bridge.js"></script>
<script src="scripts/app.js"></script>
```

2. **api.js 수정**
- `isModalView` 조건 제거/수정
- 모달에서도 실시간 업데이트 활성화

3. **app.js 수정**
- 중복 메시지 리스너 제거
- ModalBridge 활용하도록 변경

## 성능 개선 결과

### 예상 효과
- **체감 로딩 시간**: 3-5초 → 0.5초 이내
- **첫 콘텐츠 표시**: 즉시 (스케일톤 UI)
- **점진적 렌더링**: 각 섹션 독립적으로 표시
- **모달창 동기화**: 메인 페이지와 동일한 경험

### 성능 측정
**파일**: `frontend/app/scripts/app.js`
- PerformanceMonitor 구현
- 각 섹션별 렌더링 시간 측정
- 메모리 사용량 추적

## 주의사항

### 테스트 시
1. 브라우저 캐시 반드시 삭제
2. 콘솔 로그 확인하여 에러 체크
3. 네트워크 탭에서 SSE 스트리밍 확인

### 알려진 이슈
1. **Lint 에러**: 수정 완료
   - async 함수에 await 없음
   - 사용하지 않는 변수 제거

2. **잠재적 문제**
   - 메모리 누수 가능성 (이벤트 리스너 정리 필요)
   - DOM 조작 최적화 여지 있음
   - 캐시 관리 개선 필요

## 향후 개선사항

### 단기
- [ ] 메모리 누수 방지 (이벤트 리스너 정리)
- [ ] DOM 조작 최적화 (Virtual DOM 패턴)
- [ ] 에러 핸들링 강화

### 중장기
- [ ] Virtual Scrolling 구현
- [ ] Web Worker 활용
- [ ] TypeScript 마이그레이션
- [ ] 성능 모니터링 시스템 구축

## 디버깅 가이드

### 모달창이 빈 화면일 때
1. modal-bridge.js가 로드되었는지 확인
2. 콘솔에서 `window.ModalBridge` 확인
3. 네트워크 탭에서 API 호출 확인
4. sessionStorage 데이터 확인

### 스트리밍이 작동하지 않을 때
1. isModalView 값 확인
2. EventSource 연결 상태 확인
3. 백엔드 SSE 응답 확인
4. CORS 설정 확인

## 코드 컨벤션

### 로깅 규칙
- 🚀 시작/초기화
- ✅ 성공/완료
- ❌ 에러/실패
- 🎯 중요 이벤트
- 📝 데이터 업데이트
- 🦴 스케일톤 관련
- 🌊 스트리밍 관련

### 함수 명명
- `show*`: UI 표시
- `hide*`: UI 숨김
- `update*`: 데이터 업데이트
- `render*`: 렌더링
- `handle*`: 이벤트 처리

## 참고 자료
- [Server-Sent Events (SSE) MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [Progressive Rendering](https://developers.google.com/web/fundamentals/performance/critical-rendering-path)
- [Skeleton Screens](https://uxdesign.cc/what-you-should-know-about-skeleton-screens-a820c45a571a)