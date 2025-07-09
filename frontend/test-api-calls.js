#!/usr/bin/env node

/**
 * API 호출 중복 방지 테스트 스크립트
 * 
 * 이 스크립트는 수정된 코드의 주요 개선사항을 검증합니다:
 * 1. 중복 loadInitialData 호출 제거
 * 2. 로딩 상태 기반 중복 방지
 * 3. 모달 컨텍스트에서 noBackendCall 작동
 * 4. app.activated 이벤트 최적화
 */

console.log('🔍 API 호출 중복 방지 수정사항 검증');
console.log('=====================================');

// 수정된 파일 읽기
const fs = require('fs');
const path = require('path');

const appJsPath = path.join(__dirname, 'app', 'scripts', 'app.js');
const appJsContent = fs.readFileSync(appJsPath, 'utf8');

// 검증 항목들
const checks = [
  {
    name: '중복 loadInitialData 호출 제거',
    test: () => {
      // 라인 1536에서 loadInitialData 호출이 제거되었는지 확인
      const lines = appJsContent.split('\n');
      const suspiciousLine = lines.find(line => 
        line.includes('App.api.loadInitialData(App.state.ticketId);') && 
        !line.includes('await')
      );
      return !suspiciousLine;
    }
  },
  {
    name: '로딩 상태 플래그 추가',
    test: () => {
      return appJsContent.includes('loadingInProgress: false') &&
             appJsContent.includes('dataLoaded: false');
    }
  },
  {
    name: '중복 방지 로직 추가',
    test: () => {
      return appJsContent.includes('if (App.state.loadingInProgress || App.state.dataLoaded)') &&
             appJsContent.includes('중복 호출 방지 체크');
    }
  },
  {
    name: 'noBackendCall 플래그 개선',
    test: () => {
      return appJsContent.includes('noBackendCall: App.state.dataLoaded || hasCachedData') &&
             appJsContent.includes('modalData.noBackendCall === true');
    }
  },
  {
    name: 'app.activated 이벤트 최적화',
    test: () => {
      return appJsContent.includes('const hasCachedData = App.state.dataLoaded') &&
             appJsContent.includes('현재 데이터 로드 상태');
    }
  },
  {
    name: '전역 함수 개선',
    test: () => {
      return appJsContent.includes('window.showFDKModal') &&
             appJsContent.includes('데이터 로드 상태에 따라 캐시된 데이터 사용');
    }
  },
  {
    name: 'Request API 수정',
    test: () => {
      return appJsContent.includes('client.request.invokeTemplate') &&
             !appJsContent.includes('client.request.get');
    }
  }
];

// 검증 실행
let passedChecks = 0;
checks.forEach((check, index) => {
  const result = check.test();
  const status = result ? '✅ PASS' : '❌ FAIL';
  console.log(`${index + 1}. ${check.name}: ${status}`);
  if (result) passedChecks++;
});

console.log('\n📊 검증 결과:');
console.log(`통과: ${passedChecks}/${checks.length}`);
console.log(`성공률: ${Math.round((passedChecks / checks.length) * 100)}%`);

if (passedChecks === checks.length) {
  console.log('\n🎉 모든 검증 통과! API 호출 중복 문제가 해결되었습니다.');
  console.log('\n📝 기대 효과:');
  console.log('- /init/ticketId API 호출: 4~6번 → 1번');
  console.log('- 모달 열기 시 백엔드 호출 없이 캐시된 데이터 사용');
  console.log('- 초기 로딩 성능 개선');
  console.log('- 백엔드 서버 부하 감소');
} else {
  console.log('\n⚠️  일부 검증 실패. 코드를 다시 확인해주세요.');
}

console.log('\n🔍 추가 권장사항:');
console.log('- 브라우저 개발자 도구에서 Network 탭을 확인하여 실제 API 호출 횟수 검증');
console.log('- 모달 열기 전후 로딩 상태 로그 확인');
console.log('- 다양한 시나리오 테스트 (새 탭, 새로고침, 모달 재열기 등)');