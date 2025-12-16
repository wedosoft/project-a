/**
 * 백엔드 URL 설정
 * FDK invokeTemplate을 우회하여 직접 fetch로 SSE 스트리밍을 사용하기 위한 설정
 */

(function() {
  'use strict';

  const BACKEND_HOSTS = {
    production: 'api.wedosoft.net',
    development: 'ameer-timberless-paragogically.ngrok-free.dev',
    local: 'localhost:8000'
  };

  /**
   * 현재 환경 감지
   */
  function detectEnvironment() {
    const hostname = window.location.hostname;
    
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      // 로컬 FDK 개발 환경에서도 프로덕션 백엔드 사용
      return 'development';
    }
    
    if (hostname.includes('freshdesk.com')) {
      return 'production';
    }
    
    return 'development';
  }

  /**
   * 백엔드 설정 초기화
   */
  function initBackendConfig() {
    const environment = detectEnvironment();
    const host = BACKEND_HOSTS[environment];
    const useHttps = environment !== 'local';

    window.BACKEND_CONFIG = {
      host: host,
      protocol: useHttps ? 'https' : 'http',
      environment: environment,

      /**
       * 전체 URL 생성
       * @param {string} path - API 경로 (예: 'api/assist/analyze')
       * @returns {string} 전체 URL
       */
      getUrl: function(path) {
        if (!path.startsWith('/')) path = '/' + path;
        return `${this.protocol}://${this.host}${path}`;
      },

      /**
       * API 키 및 테넌트 정보가 포함된 헤더 생성
       * @returns {Object} HTTP 헤더 객체
       */
      getHeaders: function() {
        const config = window.APP_CONFIG || {};
        return {
          'Content-Type': 'application/json',
          'X-Tenant-ID': config.tenantId || '',
          'X-Platform': 'freshdesk',
          // Backward/compat headers (some backends may read these)
          'X-Domain': config.domain || '',
          'X-API-Key': config.apiKey || '',
          // Agent-platform assist routes expect these for Freshdesk enrichment
          'X-Freshdesk-Domain': config.domain || '',
          'X-Freshdesk-API-Key': config.apiKey || '',
          'ngrok-skip-browser-warning': 'true'
        };
      }
    };

    console.log(`[BackendConfig] Initialized: ${environment} → ${host}`);
  }

  // 즉시 초기화
  initBackendConfig();

})();
