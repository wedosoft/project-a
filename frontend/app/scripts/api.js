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
   * 캐싱 지원 백엔드 API 호출 (자동 재시도 제거)
   * 실패 시 사용자에게 수동 재시도를 유도하는 UX 적용
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

    try {
      const result = await this.performAPICall(client, endpoint, data, method, options);

      // 성공한 결과 캐싱 (GET 요청 또는 명시적 허용)
      if ((method === 'GET' || options.useCache) && result && result.ok) {
        const ttl = options.cacheTTL || 300000; // 기본 5분
        window.PerformanceOptimizer.cacheApiResult(cacheKey, result, ttl);
      }

      return result;
    } catch (error) {
      // 자동 재시도 제거: 실패 시 바로 에러를 던져서 사용자가 수동으로 재시도할 수 있도록 함
      console.error(`[API 호출 실패] ${method} /${endpoint} - ${error.message}`);
      
      // 사용자 친화적인 에러 메시지로 변환
      if (error.status === 0 || !error.status) {
        // 네트워크 연결 문제
        error.userMessage = '네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.';
      } else if (error.status >= 500) {
        // 서버 에러
        error.userMessage = '서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
      } else if (error.status === 429) {
        // Rate limit
        error.userMessage = '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
      } else if (error.status >= 400 && error.status < 500) {
        // 클라이언트 에러
        error.userMessage = '요청에 문제가 있습니다. 페이지를 새로고침하고 다시 시도해 주세요.';
      } else {
        // 기타 에러
        error.userMessage = '예상치 못한 문제가 발생했습니다. 페이지를 새로고침하고 다시 시도해 주세요.';
      }

      throw error;
    }
  },

  /**
   * 실제 API 호출 수행
   */
  async performAPICall(client, endpoint, data, method, options = {}) {
    let loadingId = null;

    try {
      console.log(
        `🚀 백엔드 API 호출: ${method} /${endpoint}`
      );

      // 로딩 상태 표시
      if (options.showLoading !== false) {
        const loadingMessage =
          method === 'GET' ? '데이터를 불러오는 중...' : '요청을 처리하는 중...';
        if (window.UI && window.UI.showLoading) {
          window.UI.showLoading(loadingMessage);
          loadingId = 'api-call';
        }
      }

      // iparams에서 Freshdesk 설정값 가져오기
      const config = await getFreshdeskConfigFromIparams(client);

      // 개발 환경에서 iparams가 없는 경우 환경변수 또는 기본값 사용
      let finalConfig = config;
      if (!config || !config.domain || !config.apiKey) {
        console.warn('⚠️ iparams에서 Freshdesk 설정값을 가져올 수 없습니다. 환경변수 폴백 시도...');
        
        // 개발 환경용 기본값 설정 (실제 운영에서는 iparams에서 가져와야 함)
        if (window.location.hostname === 'localhost' || window.location.hostname.includes('10001')) {
          finalConfig = {
            domain: 'wedosoft.freshdesk.com', // 개발용 기본값
            apiKey: 'Ug9H1cKCZZtZ4haamBy', // 개발용 기본값
          };
          console.log('🛠️ 개발 환경: 기본 Freshdesk 설정 사용');
        }
      }

      // 요청 설정
      const requestOptions = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          ...(finalConfig?.domain && { 'X-Freshdesk-Domain': finalConfig.domain }),
          ...(finalConfig?.apiKey && { 'X-Freshdesk-API-Key': finalConfig.apiKey }),
        },
        ...(data && { body: JSON.stringify(data) }),
      };

      // 헤더 로깅 (개발용)
      if (window.location.hostname === 'localhost') {
        console.log('📤 전송할 헤더:', {
          'X-Freshdesk-Domain': finalConfig?.domain,
          'X-Freshdesk-API-Key': finalConfig?.apiKey ? '***' + finalConfig.apiKey.slice(-4) : 'none',
        });
      }

      // 성능 측정
      const performanceKey = `API-${method}-${endpoint}`;
      const startTime = performance.now();

      const response = await fetch(`http://localhost:8000/${endpoint}`, requestOptions);

      const endTime = performance.now();
      console.log(`[성능] ${performanceKey}: ${(endTime - startTime).toFixed(2)}ms`);

      if (!response.ok) {
        const errorBody = await response.text();
        console.error(`❌ HTTP 응답 실패: ${response.status} ${response.statusText}`);
        console.error(`❌ 에러 응답 본문:`, errorBody);
        
        const error = new Error(`API 호출 실패: ${response.status} ${response.statusText}`);
        error.status = response.status;
        error.body = errorBody;
        throw error;
      }

      const result = await response.json();
      
      // 🔍 응답 데이터 상세 디버깅
      console.log(`✅ API 응답 성공 (${response.status})`);
      console.log(`🔍 [DEBUG] API 응답 데이터:`, {
        endpoint: endpoint,
        method: method,
        responseSize: JSON.stringify(result).length,
        hasTicketSummary: !!result.ticket_summary,
        hasSimilarTickets: !!result.similar_tickets,
        hasKbDocuments: !!result.kb_documents,
        dataKeys: Object.keys(result),
        fullData: result
      });

      // 일관된 응답 구조 반환
      return {
        ok: true,
        status: response.status,
        statusText: response.statusText,
        data: result
      };
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
    return await this.callBackendAPIWithCache(client, endpoint, data, method);
  },

  /**
   * 백엔드에서 초기 데이터를 로드하는 함수
   */
  async loadInitData(client, ticketId) {
    return await this.callBackendAPIWithCache(client, `init/${ticketId}`, null, 'GET', {
      cacheTTL: 600000, // 10분 캐시
      loadingContext: '초기 데이터 로드',
    });
  },

  /**
   * 자연어 쿼리 실행
   */
  async executeQuery(client, queryData) {
    return await this.callBackendAPIWithCache(client, 'query', queryData, 'POST', {
      useCache: false, // POST 요청은 기본적으로 캐시하지 않음
      loadingContext: '쿼리 실행',
    });
  },

  /**
   * 모든 티켓 목록 가져오기
   */
  async getAllTickets(client) {
    return await this.callBackendAPIWithCache(client, 'tickets/all', null, 'GET', {
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

if (window.location.hostname === 'localhost') {
  console.log('📡 최적화된 API 모듈 로드 완료 - 향상된 성능 및 캐싱 지원');
}

// 모듈 의존성 시스템에 등록
if (typeof window.ModuleDependencyManager !== 'undefined') {
  window.ModuleDependencyManager.registerModule('api', Object.keys(API).length);
}

// 전역으로 export
window.API = API;
