/**
 * config.js
 * 설정 및 환경 관련 함수
 * 앱의 설정, 환경 변수, Freshdesk 설정 관리 함수들이 포함됩니다.
 */

// 설정 상수
const CONFIG = {
  CACHE_DURATION: 5 * 60 * 1000, // 5분
  API_TIMEOUT: 30000, // 30초
  MAX_RETRIES: 3, // 최대 재시도 횟수
  DEFAULT_LOCALE: "ko-KR",
  DEBUG_MODE: false, // 개발 중 디버그 메시지 활성화
};

// 환경별 백엔드 설정 (로컬 개발용 하드코딩 값)
const DEVELOPMENT_CONFIG = {
  backendUrl: "https://eb73-61-73-3-53.ngrok-free.app",
  freshdeskDomain: "wedosoft.freshdesk.com", 
  freshdeskApiKey: "Ug9H1cKCZZtZ4haamBy",
  companyId: "wedosoft"
};

// 현재 환경 감지 (ngrok 터널링 고려)
const ENVIRONMENT = (() => {
  // FDK 로컬 개발 환경 감지 (ngrok 사용)
  if (window.location.href.includes("ngrok-free.app") ||
      window.location.href.includes("ngrok.io") ||
      window.location.href.includes("dev=true") ||
      window.location.port === "10001") {
    return "development";
  }
  return "production";
})();

// iparams에서 설정값 불러오기 (프로덕션 환경에서만)
async function loadIparams(client) {
  try {
    console.log(`⏳ 환경: ${ENVIRONMENT} - 설정값 조회 중...`);
    
    // 개발 환경에서는 하드코딩된 설정 사용
    if (ENVIRONMENT === "development") {
      console.log("🔧 개발 환경: 하드코딩된 설정 사용");
      return {
        domain: DEVELOPMENT_CONFIG.freshdeskDomain,
        apiKey: DEVELOPMENT_CONFIG.freshdeskApiKey,
        backendUrl: DEVELOPMENT_CONFIG.backendUrl,
        companyId: DEVELOPMENT_CONFIG.companyId,
      };
    }
    
    // 프로덕션 환경에서는 iparams 사용
    if (!client) {
      throw new Error("Freshdesk client가 초기화되지 않았습니다.");
    }
    
    console.log("🔍 Client 객체 확인:", {
      client: !!client,
      iparams: !!client.iparams,
      get: !!client.iparams?.get
    });
    
    const iparams = await client.iparams.get();
    
    console.log("🔍 Raw iparams 데이터:", iparams);

    // 필수 설정값 확인
    const config = {
      domain: iparams.freshdesk_domain,
      apiKey: iparams.freshdesk_api_key,
      backendUrl: iparams.backend_url,
      companyId: iparams.company_id,
    };

    console.log("✅ iparams 설정값 조회 완료:", {
      domain: config.domain ? "✓ " + config.domain : "✗ 미설정",
      apiKey: config.apiKey ? "✓ ***설정됨***" : "✗ 미설정",
      backendUrl: config.backendUrl ? "✓ " + config.backendUrl : "✗ 미설정",
      companyId: config.companyId ? "✓ " + config.companyId : "✗ 미설정",
    });

    return config;
  } catch (error) {
    console.error("❌ iparams 설정값 조회 실패:", error);
    
    // 프로덕션에서 iparams 실패 시에도 개발 설정 폴백 사용
    console.warn("⚠️ iparams 실패 - 개발 설정으로 폴백");
    return {
      domain: DEVELOPMENT_CONFIG.freshdeskDomain,
      apiKey: DEVELOPMENT_CONFIG.freshdeskApiKey,
      backendUrl: DEVELOPMENT_CONFIG.backendUrl,
      companyId: DEVELOPMENT_CONFIG.companyId,
    };
  }
}

// 현재 백엔드 URL 가져오기 (환경별 설정 적용)
function getBackendUrl(iparams) {
  // 개발 환경에서는 하드코딩된 URL 사용
  if (ENVIRONMENT === "development") {
    return DEVELOPMENT_CONFIG.backendUrl;
  }
  
  // 프로덕션 환경에서는 iparams에서 백엔드 URL 사용
  if (iparams && iparams.backendUrl) {
    return iparams.backendUrl;
  }
  
  // 폴백: 개발 설정 사용
  return DEVELOPMENT_CONFIG.backendUrl;
}

// 환경 정보 조회 함수 (디버깅용)
function getEnvironmentInfo() {
  return {
    environment: ENVIRONMENT,
    hostname: window.location.hostname,
    href: window.location.href,
    port: window.location.port,
    isNgrokTunnel: window.location.hostname.includes("ngrok"),
    isDevelopment: ENVIRONMENT === "development",
    isProduction: ENVIRONMENT === "production"
  };
}

// 시스템 설정 초기화
async function initializeConfig(client) {
  console.log("🔧 시스템 설정 초기화:", getEnvironmentInfo());
  
  // iparams 설정값 불러오기 (환경에 따라 다르게 처리)
  const iparams = await loadIparams(client);
  
  if (!iparams) {
    console.error("❌ 설정 로드 실패 - 앱을 사용할 수 없습니다.");
    throw new Error("설정을 불러올 수 없습니다. 관리자에게 문의하세요.");
  }
  
  console.log("✅ 최종 설정:", {
    environment: ENVIRONMENT,
    domain: iparams.domain ? "✓ " + iparams.domain : "✗ 미설정",
    apiKey: iparams.apiKey ? "✓ ***설정됨***" : "✗ 미설정",
    backendUrl: iparams.backendUrl ? "✓ " + iparams.backendUrl : "✗ 미설정",
    companyId: iparams.companyId ? "✓ " + iparams.companyId : "✗ 미설정",
  });
  
  // 설정 값 반환 - API에서 직접 사용할 수 있는 구조로 수정
  return {
    ...CONFIG,
    environment: ENVIRONMENT,
    // API에서 직접 사용할 수 있는 플랫 구조
    domain: iparams.domain,
    apiKey: iparams.apiKey,
    backendUrl: iparams.backendUrl,
    companyId: iparams.companyId,
    // 기존 구조도 유지 (하위 호환성)
    freshdesk: {
      domain: iparams.domain,
      apiKey: iparams.apiKey,
      companyId: iparams.companyId,
    }
  };
}

// 디버그 모드 활성화/비활성화
function setDebugMode(enabled) {
  CONFIG.DEBUG_MODE = enabled;
  
  if (enabled) {
    console.log("🛠️ 디버그 모드 활성화");
  } else {
    console.log("🔒 디버그 모드 비활성화");
  }
}

// 전역 네임스페이스로 내보내기  
window.config = {
  CONFIG,
  ENVIRONMENT,
  DEVELOPMENT_CONFIG,
  loadIparams,
  getBackendUrl,
  getEnvironmentInfo,
  initializeConfig,
  setDebugMode,
};
