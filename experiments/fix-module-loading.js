/**
 * 모듈 중복 로드 수정 패치
 * 
 * 문제: "모듈 로드 완료" 메시지가 4번 반복되는 문제
 * 원인: 페이지가 여러 컨텍스트에서 로드되며 스크립트가 재실행됨
 * 해결: 더 강력한 중복 방지 메커니즘 구현
 */

// globals.js의 registerModule 함수를 패치
if (window.ModuleDependencyManager) {
  const originalRegisterModule = window.ModuleDependencyManager.registerModule;
  
  // 더 강력한 중복 방지를 위한 전역 추적기
  if (!window.GLOBAL_MODULE_REGISTRY) {
    window.GLOBAL_MODULE_REGISTRY = {
      registered: new Set(),
      registrationCounts: {},
      maxRegistrations: 1 // 각 모듈당 최대 1번만 등록 허용
    };
  }
  
  window.ModuleDependencyManager.registerModule = function(moduleName, exportCount = 0, dependencies = []) {
    const registry = window.GLOBAL_MODULE_REGISTRY;
    const moduleKey = `${moduleName}_${window.location.pathname}`;
    
    // 등록 횟수 추적
    if (!registry.registrationCounts[moduleName]) {
      registry.registrationCounts[moduleName] = 0;
    }
    
    // 이미 등록된 모듈은 무시
    if (registry.registered.has(moduleKey)) {
      console.warn(`⚠️ [${moduleName}] 모듈이 이미 등록됨. 중복 등록 차단.`);
      return;
    }
    
    // 최대 등록 횟수 초과 체크
    if (registry.registrationCounts[moduleName] >= registry.maxRegistrations) {
      console.warn(`⚠️ [${moduleName}] 최대 등록 횟수(${registry.maxRegistrations}) 초과. 등록 차단.`);
      return;
    }
    
    // 등록 진행
    registry.registered.add(moduleKey);
    registry.registrationCounts[moduleName]++;
    
    // 원본 함수 호출
    originalRegisterModule.call(this, moduleName, exportCount, dependencies);
  };
  
  console.log('✅ 모듈 중복 로드 방지 패치 적용 완료');
}

// MODULE_LOAD_TRACKER도 개선
if (window.MODULE_LOAD_TRACKER) {
  // 로그 출력을 한 번만 하도록 수정
  const originalCheckAllModulesLoaded = window.MODULE_LOAD_TRACKER.checkAllModulesLoaded;
  
  window.MODULE_LOAD_TRACKER.checkAllModulesLoaded = function() {
    // 이미 체크했으면 무시
    if (this.allModulesChecked) {
      return;
    }
    
    this.allModulesChecked = true;
    originalCheckAllModulesLoaded.call(this);
  };
}

// 디버깅 헬퍼 함수
window.debugModuleLoading = function() {
  const registry = window.GLOBAL_MODULE_REGISTRY;
  console.log('📊 모듈 등록 현황:');
  console.log('- 등록된 모듈:', Array.from(registry.registered));
  console.log('- 등록 횟수:', registry.registrationCounts);
  console.log('- 로드된 모듈:', Array.from(window.MODULE_LOAD_TRACKER.loaded));
};

// 페이지 로드 시 자동으로 패치 적용
document.addEventListener('DOMContentLoaded', function() {
  console.log('🔧 모듈 시스템 패치 검증 중...');
  setTimeout(() => {
    window.debugModuleLoading();
  }, 2000);
});