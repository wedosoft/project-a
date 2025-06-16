/**
 * @fileoverview Optimized API module for Freshdesk Custom App backend communication
 * @description 🚀 최적화된 API 모듈 (api.js) - Freshdesk Custom App 백엔드 API 통신 및 성능 최적화
 *
 * Main features:
 * 주요 기능:
 * - Caching and memoization support / 캐싱 및 메모이제이션 지원
 * - Batch API call processing / 배치 API 호출 처리
 * - Retry logic with exponential backoff / 재시도 로직 및 지수적 백오프
 * - Performance monitoring and metrics collection / 성능 모니터링 및 메트릭 수집
 * - Smart loading state management / 스마트 로딩 상태 관리
 *
 * @author We Do Soft Inc.
 * @since 2025.06.16
 * @version 3.0.0 (성능 최적화 및 캐싱 강화)
 * @namespace API
 */

/**
 * 🔗 iparams에서 Freshdesk 설정값을 가져오는 함수
 * 고객사별로 다른 도메인과 API 키를 동적으로 로드하여 멀티테넌트 환경 지원
 */
async function getFreshdeskConfigFromIparams(client) {
  try {
    console.log('📋 iparams에서 Freshdesk 설정값 로드 중...');

    const iparams = await client.iparams.get();

    if (iparams && iparams.freshdesk_domain && iparams.freshdesk_api_key) {
      console.log(`✅ iparams 로드 성공: 도메인 ${iparams.freshdesk_domain}`);
      return {
        domain: iparams.freshdesk_domain,
        apiKey: iparams.freshdesk_api_key,
      };
    }

    console.warn('⚠️ iparams에서 필수 설정값이 누락됨');
    return null;
  } catch (error) {
    console.error('❌ iparams 로드 실패:', error);
    return null;
  }
}

/**
 * 최적화된 API 모듈
 */
const API = {
  /**
   * 모듈 가용성 확인
   */
  isAvailable() {
    const dependencies = ['GlobalState', 'PerformanceOptimizer'];
    const missing = dependencies.filter((dep) => !window[dep]);

    if (missing.length > 0) {
      console.warn('[API] 누락된 의존성:', missing);
      return false;
    }

    console.log('[API] 최적화된 모듈 초기화 완료 (캐싱, 배치 처리, 재시도 지원)');
    return true;
  },

  /**
   * 캐시 키 생성
   */
  generateCacheKey(endpoint, data, method) {
    const base = `${method}:${endpoint}`;
    if (data) {
      const dataHash = this.hashObject(data);
      return `${base}:${dataHash}`;
    }
    return base;
  },

  /**
   * 객체 해시 생성 (간단한 캐시 키용)
   */
  hashObject(obj) {
    const str = JSON.stringify(obj);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // 32bit 정수로 변환
    }
    return hash.toString(36);
  },

  /**
   * 지연 함수
   */
  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  },

  /**
   * 배치 API 호출 지원
   * 여러 API 호출을 효율적으로 처리
   */
  async batchAPICall(client, requests, options = {}) {
    const { concurrency = 3, delay = 100 } = options;
    const results = [];

    console.log(`[API 배치] ${requests.length}개 요청을 ${concurrency}개씩 처리`);

    for (let i = 0; i < requests.length; i += concurrency) {
      const batch = requests.slice(i, i + concurrency);

      const batchPromises = batch.map(async (request, index) => {
        try {
          // 지연 처리로 서버 부하 분산
          if (index > 0) {
            await this.delay(delay);
          }

          const result = await this.callBackendAPIWithCache(
            client,
            request.endpoint,
            request.data,
            request.method,
            { ...request.options, showLoading: false }
          );

          return { index: i + index, success: true, data: result };
        } catch (error) {
          return {
            index: i + index,
            success: false,
            error: error.message,
            request: request,
          };
        }
      });

      const batchResults = await Promise.allSettled(batchPromises);
      results.push(...batchResults.map((r) => r.value || r.reason));

      // 배치 간 지연
      if (i + concurrency < requests.length) {
        await this.delay(delay * 2);
      }
    }

    const successful = results.filter((r) => r.success).length;
    const failed = results.filter((r) => !r.success).length;

    console.log(`[API 배치] 완료: 성공 ${successful}개, 실패 ${failed}개`);

    return results;
  },

  /**
   * 캐싱 지원 백엔드 API 호출
   */
  async callBackendAPIWithCache(client, endpoint, data = null, method = 'GET', options = {}) {
    const cacheKey = this.generateCacheKey(endpoint, data, method);

    // GET 요청과 명시적으로 캐시를 허용한 경우만 캐시 확인
    if ((method === 'GET' || options.useCache) && options.bypassCache !== true) {
      const cached = window.PerformanceOptimizer.getCachedApiResult(cacheKey);
      if (cached) {
        console.log(`[API 캐시] ${method} /${endpoint} - 캐시 적중`);
        return cached;
      }
    }

    // 재시도 로직
    const maxRetries = options.maxRetries || 2;
    let lastError;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const result = await this.performAPICall(client, endpoint, data, method, {
          ...options,
          attempt: attempt + 1,
          maxRetries: maxRetries + 1,
        });

        // 성공한 결과 캐싱 (GET 요청 또는 명시적 허용)
        if ((method === 'GET' || options.useCache) && result.ok) {
          const ttl = options.cacheTTL || 300000; // 기본 5분
          window.PerformanceOptimizer.cacheApiResult(cacheKey, result, ttl);
        }

        return result;
      } catch (error) {
        lastError = error;

        // 4xx 에러는 재시도하지 않음
        if (error.status >= 400 && error.status < 500) {
          break;
        }

        // 마지막 시도가 아니면 재시도
        if (attempt < maxRetries) {
          const delayTime = 1000 * Math.pow(2, attempt); // 지수적 백오프
          console.warn(
            `[API 재시도] ${method} /${endpoint} - ${error.message}, ${delayTime}ms 후 재시도`
          );
          await this.delay(delayTime);
          continue;
        }
      }
    }

    throw lastError;
  },

  /**
   * 실제 API 호출 수행
   */
  async performAPICall(client, endpoint, data, method, options = {}) {
    let loadingId = null;

    try {
      console.log(
        `🚀 백엔드 API 호출: ${method} /${endpoint} ${options.attempt ? `(${options.attempt}/${options.maxRetries})` : ''}`
      );

      // 로딩 상태 표시
      if (options.showLoading !== false) {
        const loadingMessage =
          method === 'GET' ? '데이터를 불러오는 중...' : '요청을 처리하는 중...';
        const retryText = options.attempt > 1 ? ` (재시도 ${options.attempt - 1})` : '';
        if (window.UI && window.UI.showLoading) {
          window.UI.showLoading(`${loadingMessage}${retryText}`);
          loadingId = 'api-call';
        }
      }

      // iparams에서 Freshdesk 설정값 가져오기
      const config = await getFreshdeskConfigFromIparams(client);

      if (!config || !config.domain || !config.apiKey) {
        console.warn('⚠️ iparams에서 Freshdesk 설정값을 가져올 수 없습니다. 환경변수 폴백 시도...');
      }

      // 요청 설정
      const requestOptions = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          ...(config?.domain && { 'X-Freshdesk-Domain': config.domain }),
          ...(config?.apiKey && { 'X-Freshdesk-API-Key': config.apiKey }),
        },
        ...(data && { body: JSON.stringify(data) }),
      };

      // 성능 측정
      const performanceKey = `API-${method}-${endpoint}`;
      const startTime = performance.now();

      const response = await fetch(`http://localhost:8000/${endpoint}`, requestOptions);

      const endTime = performance.now();
      console.log(`[성능] ${performanceKey}: ${(endTime - startTime).toFixed(2)}ms`);

      if (!response.ok) {
        const errorBody = await response.text();
        const error = new Error(`API 호출 실패: ${response.status} ${response.statusText}`);
        error.status = response.status;
        error.body = errorBody;
        throw error;
      }

      const result = await response.json();

      return result;
    } catch (error) {
      if (window.GlobalState && window.GlobalState.ErrorHandler) {
        window.GlobalState.ErrorHandler.handleError(error, {
          module: 'api',
          function: 'performAPICall',
          context: `${method} /${endpoint}`,
          severity: 'error',
          userMessage: '서버와의 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        });
      }

      throw error;
    } finally {
      // 로딩 상태 해제
      if (loadingId && options.showLoading !== false && window.UI && window.UI.hideLoading) {
        window.UI.hideLoading();
      }
    }
  },

  /**
   * 기존 호환성을 위한 래퍼 함수
   */
  async callBackendAPI(client, endpoint, data = null, method = 'GET') {
    return this.callBackendAPIWithCache(client, endpoint, data, method);
  },

  /**
   * 백엔드에서 초기 데이터를 로드하는 함수
   */
  async loadInitData(client, ticketId) {
    return this.callBackendAPIWithCache(client, `init/${ticketId}`, null, 'GET', {
      cacheTTL: 600000, // 10분 캐시
      loadingContext: '초기 데이터 로드',
    });
  },

  /**
   * 자연어 쿼리 실행
   */
  async executeQuery(client, queryData) {
    return this.callBackendAPIWithCache(client, 'query', queryData, 'POST', {
      useCache: false, // POST 요청은 기본적으로 캐시하지 않음
      loadingContext: '쿼리 실행',
    });
  },

  /**
   * 모든 티켓 목록 가져오기
   */
  async getAllTickets(client) {
    return this.callBackendAPIWithCache(client, 'tickets/all', null, 'GET', {
      cacheTTL: 900000, // 15분 캐시
      loadingContext: '티켓 목록 조회',
    });
  },

  /**
   * 캐시 관리 함수들
   */
  clearCache() {
    if (window.PerformanceOptimizer) {
      window.PerformanceOptimizer.resultCache.clear();
      console.log('[API] 캐시가 초기화되었습니다.');
    }
  },

  getCacheStats() {
    return window.PerformanceOptimizer ? window.PerformanceOptimizer.getMemoryStats() : {};
  },

  /**
   * 프리플라이트 체크 - API 서버 상태 확인
   */
  async healthCheck() {
    try {
      const response = await fetch('http://localhost:8000/health', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      return response.ok;
    } catch (error) {
      console.warn('[API] 서버 상태 확인 실패:', error.message);
      return false;
    }
  },
};

// 의존성 확인 함수
API.isAvailable = function () {
  const dependencies = ['GlobalState'];
  const missing = dependencies.filter((dep) => typeof window[dep] === 'undefined');

  if (missing.length > 0) {
    console.warn('[API] 누락된 의존성:', missing);
    return false;
  }

  return true;
};

console.log('📡 최적화된 API 모듈 로드 완료 - 향상된 성능 및 캐싱 지원');

// 모듈 의존성 시스템에 등록
if (typeof window.ModuleDependencyManager !== 'undefined') {
  window.ModuleDependencyManager.registerModule('api', Object.keys(API).length);
}

// 전역으로 export
window.API = API;
